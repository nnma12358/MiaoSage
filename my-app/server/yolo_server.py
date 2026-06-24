#!/usr/bin/env python3
"""苗绣·识裳 — 苗族服饰/银饰检测微服务 (K1/riscv64, spacemit-ort)"""
import io, os, time, logging
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("yolo-server")

# 默认使用训练的苗族银饰检测模型（8类）
# 也可通过环境变量切换: export YOLO_MODEL="/app/clothesfp16.onnx"（服装2类）
YOLO_MODEL = os.environ.get("YOLO_MODEL", "/app/best_fp16.onnx")

# 苗族服饰/银饰检测类别（根据数据集 CV/dataset.yaml 和 CV/clothes.yaml）
_MIAO_SILVER_CLASSES = {  # best_fp16.onnx — 苗族银饰（8 类）
    0: "流苏帽 (tassel_hat)",
    1: "苗族牛角银头饰 (miao_ox_horn_silver_headwear)",
    2: "苗族银发簪 (miao_silver_hairpin)",
    3: "苗族银冠 (miao_silver_crown)",
    4: "苗族银胸饰 (miao_silver_chest_ornament)",
    5: "苗族银锁 (miao_silver_lock)",
    6: "苗族银项链 (miao_silver_necklace)",
    7: "银头饰 (silver_headdress)",
}
_MIAO_CLOTHES_CLASSES = {  # clothesfp16.onnx — 苗族服装（2 类）
    0: "苗族便装 (Miao casual wear)",
    1: "苗族盛装 (Miao ceremonial dress)",
}

# 根据加载的模型自动选择类别映射
MIAO_CLASSES = _MIAO_CLOTHES_CLASSES if "clothes" in YOLO_MODEL else _MIAO_SILVER_CLASSES

class YOLODetector:
    def __init__(self, model_path: str):
        import onnxruntime as ort
        self._session = ort.InferenceSession(model_path, providers=ort.get_available_providers())
        _, _, h, w = self._session.get_inputs()[0].shape
        self._input_shape = (w, h)
        self._in_name = self._session.get_inputs()[0].name
        logger.info(f"苗族服饰检测模型加载: {model_path} ({self._input_shape})")

    def detect(self, img: Image.Image) -> list:
        w_in, h_in = self._input_shape
        img_w, img_h = img.size
        arr = np.array(img.resize((w_in, h_in), Image.BILINEAR), dtype=np.float32) / 255.0
        arr = np.expand_dims(arr.transpose(2, 0, 1), axis=0)
        preds = np.squeeze(self._session.run(None, {self._in_name: arr})[0])

        bbox_raw, scores = preds[:4, :], preds[4:, :]
        class_ids = np.argmax(scores, axis=0)
        confs = np.max(scores, axis=0)
        mask = confs > 0.25
        if not mask.any():
            return []

        bbox_raw, class_ids, confs = bbox_raw[:, mask], class_ids[mask], confs[mask]
        cx, cy, w, h = bbox_raw[0], bbox_raw[1], bbox_raw[2], bbox_raw[3]
        x1 = (cx - w / 2) * img_w / w_in
        y1 = (cy - h / 2) * img_h / h_in
        x2 = (cx + w / 2) * img_w / w_in
        y2 = (cy + h / 2) * img_h / h_in

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
            dets.append({
                "class": MIAO_CLASSES.get(int(class_ids[i]), f"cls_{int(class_ids[i])}"),
                "confidence": round(float(confs[i]), 4),
                "bbox": {"x1": round(float(x1[i]), 1), "y1": round(float(y1[i]), 1),
                         "x2": round(float(x2[i]), 1), "y2": round(float(y2[i]), 1)},
            })
        return sorted(dets, key=lambda d: d["confidence"], reverse=True)

app = FastAPI(title="YOLO Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

detector = None

@app.on_event("startup")
def startup():
    global detector
    detector = YOLODetector(YOLO_MODEL)
    logger.info("YOLO 服务就绪")

@app.get("/health")
def health():
    return {"status": "ok", "model": YOLO_MODEL}

@app.post("/detect")
async def detect(image: UploadFile = File(...)):
    t0 = time.perf_counter()
    contents = await image.read()
    img = Image.open(io.BytesIO(contents)).convert("RGB")
    dets = detector.detect(img)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    return {"success": True, "detections": dets, "count": len(dets), "latency_ms": ms}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
