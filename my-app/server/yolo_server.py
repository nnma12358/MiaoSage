#!/usr/bin/env python3
"""苗绣·识裳 — 双模型 YOLO 检测微服务 (K1/riscv64, spacemit-ort)

支持三种检测模式：
  ?mode=silver   仅银饰检测（8类，默认，最快）
  ?mode=clothes  仅服装检测（2类）
  ?mode=pipeline 串行检测：服装→银饰，带人物框空间过滤（精度最高）
"""
import io, os, time, logging
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("yolo-server")

# ---------- 模型路径 ----------
CLOTHES_MODEL = os.environ.get("CLOTHES_MODEL", "/app/clothesfp16.onnx")
SILVER_MODEL  = os.environ.get("SILVER_MODEL",  "/app/best_fp16.onnx")

# ---------- 类别映射 ----------
_MIAO_SILVER_CLASSES = {
    0: "流苏帽 (tassel_hat)",
    1: "苗族牛角银头饰 (miao_ox_horn_silver_headwear)",
    2: "苗族银发簪 (miao_silver_hairpin)",
    3: "苗族银冠 (miao_silver_crown)",
    4: "苗族银胸饰 (miao_silver_chest_ornament)",
    5: "苗族银锁 (miao_silver_lock)",
    6: "苗族银项链 (miao_silver_necklace)",
    7: "银头饰 (silver_headdress)",
}

_MIAO_CLOTHES_CLASSES = {
    0: "苗族便装 (Miao casual wear)",
    1: "苗族盛装 (Miao ceremonial dress)",
}


# ============================================================
# ONNX 推理引擎（单模型）
# ============================================================
class ONNXDetector:
    """加载单个 ONNX 模型并执行推理 + NMS"""

    def __init__(self, model_path: str, class_names: dict):
        import onnxruntime as ort
        self._session = ort.InferenceSession(model_path, providers=ort.get_available_providers())
        self.names = class_names
        _, _, h, w = self._session.get_inputs()[0].shape
        self._input_shape = (w, h)
        self._in_name = self._session.get_inputs()[0].name
        logger.info(f"  模型加载: {os.path.basename(model_path)} ({self._input_shape})")

    def detect(self, img: Image.Image, conf_thresh: float = 0.25) -> list:
        w_in, h_in = self._input_shape
        img_w, img_h = img.size

        # 预处理
        arr = np.array(img.resize((w_in, h_in), Image.BILINEAR), dtype=np.float32) / 255.0
        arr = np.expand_dims(arr.transpose(2, 0, 1), axis=0)

        # 推理
        preds = np.squeeze(self._session.run(None, {self._in_name: arr})[0])

        # 后处理
        return self._postprocess(preds, img_w, img_h, w_in, h_in, conf_thresh)

    def _postprocess(self, preds, img_w, img_h, in_w, in_h, conf_thresh):
        bbox_raw, scores = preds[:4, :], preds[4:, :]
        class_ids = np.argmax(scores, axis=0)
        confs = np.max(scores, axis=0)
        mask = confs > conf_thresh
        if not mask.any():
            return []

        bbox_raw, class_ids, confs = bbox_raw[:, mask], class_ids[mask], confs[mask]
        cx, cy, w, h = bbox_raw[0], bbox_raw[1], bbox_raw[2], bbox_raw[3]
        x1 = (cx - w / 2) * img_w / in_w
        y1 = (cy - h / 2) * img_h / in_h
        x2 = (cx + w / 2) * img_w / in_w
        y2 = (cy + h / 2) * img_h / in_h

        # NMS
        areas = (x2 - x1) * (y2 - y1)
        order = np.argsort(confs)[::-1]
        keep = []
        while len(order) > 0:
            i = order[0]; keep.append(i)
            if len(order) == 1: break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            order = order[1:][inter / (areas[i] + areas[order[1:]] - inter + 1e-6) < 0.45]

        dets = []
        for i in keep:
            cls_id = int(class_ids[i])
            dets.append({
                "class": self.names.get(cls_id, f"cls_{cls_id}"),
                "cls_id": cls_id,
                "confidence": round(float(confs[i]), 4),
                "bbox": {"x1": round(float(x1[i]), 1), "y1": round(float(y1[i]), 1),
                         "x2": round(float(x2[i]), 1), "y2": round(float(y2[i]), 1)},
            })
        return sorted(dets, key=lambda d: d["confidence"], reverse=True)


# ============================================================
# 双模型 Pipeline 检测器
# ============================================================
class MiaoPipelineDetector:
    """
    苗族服饰/银饰检测器，支持三种模式：
      - 'silver'   : 仅银饰（最快）
      - 'clothes'  : 仅服装
      - 'pipeline' : 服装→银饰串行，人物框过滤误报（精度最高）
    """

    def __init__(self):
        logger.info("加载检测模型...")
        self.silver = ONNXDetector(SILVER_MODEL, _MIAO_SILVER_CLASSES)
        self.clothes = ONNXDetector(CLOTHES_MODEL, _MIAO_CLOTHES_CLASSES)
        self._loaded = True
        logger.info("双模型就绪 ✓")

    def detect(self, img: Image.Image, mode: str = "silver",
               use_person_filter: bool = True,
               trigger_cls: int = 1) -> dict:
        """
        统一检测接口
        :param mode: 'silver' | 'clothes' | 'pipeline'
        :param use_person_filter: pipeline 模式下是否用人物框过滤银饰误报
        :param trigger_cls: 触发银饰检测的服装类别（1=盛装）
        """
        result = {
            "mode": mode,
            "clothes": [],
            "silver": [],
            "silver_filtered": [],
            "triggered": False,
            "cost_ms": {},
        }

        if mode == "silver":
            t0 = time.perf_counter()
            result["silver"] = self.silver.detect(img)
            result["silver_filtered"] = result["silver"]
            result["cost_ms"]["silver"] = round((time.perf_counter() - t0) * 1000, 1)

        elif mode == "clothes":
            t0 = time.perf_counter()
            result["clothes"] = self.clothes.detect(img)
            result["cost_ms"]["clothes"] = round((time.perf_counter() - t0) * 1000, 1)

        elif mode == "pipeline":
            # 阶段1：服装检测
            t0 = time.perf_counter()
            clothes_dets = self.clothes.detect(img)
            result["clothes"] = clothes_dets
            result["cost_ms"]["clothes"] = round((time.perf_counter() - t0) * 1000, 1)

            # 判断是否触发银饰检测
            has_trigger = any(d["cls_id"] == trigger_cls for d in clothes_dets)
            result["triggered"] = has_trigger

            if has_trigger or len(clothes_dets) == 0:
                # 阶段2：银饰检测
                t0 = time.perf_counter()
                silver_raw = self.silver.detect(img)
                result["silver"] = silver_raw
                result["cost_ms"]["silver"] = round((time.perf_counter() - t0) * 1000, 1)

                # 人物框空间过滤
                if use_person_filter and clothes_dets:
                    result["silver_filtered"] = self._filter_by_person(
                        silver_raw, clothes_dets)
                else:
                    result["silver_filtered"] = silver_raw
            else:
                result["cost_ms"]["silver"] = 0

        # 总耗时
        result["cost_ms"]["total"] = round(
            sum(v for v in result["cost_ms"].values() if isinstance(v, (int, float))), 1)

        return result

    @staticmethod
    def _filter_by_person(silver_dets: list, clothes_dets: list) -> list:
        """用服装检测框（人物区域）过滤银饰误报：银饰中心点需落在人物框内"""
        filtered = []
        for s in silver_dets:
            sx1, sy1, sx2, sy2 = (s["bbox"]["x1"], s["bbox"]["y1"],
                                   s["bbox"]["x2"], s["bbox"]["y2"])
            scx, scy = (sx1 + sx2) / 2, (sy1 + sy2) / 2
            inside = False
            for c in clothes_dets:
                cx1, cy1, cx2, cy2 = (c["bbox"]["x1"], c["bbox"]["y1"],
                                       c["bbox"]["x2"], c["bbox"]["y2"])
                if cx1 <= scx <= cx2 and cy1 <= scy <= cy2:
                    inside = True
                    break
            if inside:
                filtered.append(s)
        logger.info(f"  人物框过滤: {len(silver_dets)} → {len(filtered)} 个银饰")
        return filtered


# ============================================================
# FastAPI 服务
# ============================================================
app = FastAPI(title="Miao YOLO Dual-Model Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

detector: MiaoPipelineDetector = None


@app.on_event("startup")
def startup():
    global detector
    detector = MiaoPipelineDetector()
    logger.info("YOLO 双模型服务就绪 ✓")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "models": {
            "silver": SILVER_MODEL,
            "clothes": CLOTHES_MODEL,
        },
        "modes": ["silver", "clothes", "pipeline"],
    }


@app.post("/detect")
async def detect(
    image: UploadFile = File(...),
    mode: str = Query("silver", description="silver | clothes | pipeline"),
    person_filter: bool = Query(True, description="pipeline 模式下启用人物框过滤"),
):
    if detector is None:
        raise HTTPException(status_code=503, detail="模型未就绪")
    if mode not in ("silver", "clothes", "pipeline"):
        raise HTTPException(status_code=400, detail=f"无效模式: {mode}，可选 silver/clothes/pipeline")

    contents = await image.read()
    img = Image.open(io.BytesIO(contents)).convert("RGB")

    result = detector.detect(img, mode=mode, use_person_filter=person_filter)
    result["success"] = True
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
