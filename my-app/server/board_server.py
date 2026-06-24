#!/usr/bin/env python3
"""
苗绣·识裳 — K1 板一体化服务器
========================================================
单文件部署：前端 SPA + 苗族服饰检测 + LLM 对话
无需 Docker / Nginx，一个 Python 进程搞定

启动：
  python3 server/board_server.py
  python3 server/board_server.py --port 80

API：
  /             前端 SPA (build/)
  /detect       苗族服饰/银饰检测 (spacemit-ort ONNX)
  /chat         LLM 对话 (Ollama代理 → 知识库兜底)
  /chat/stream  LLM 流式对话 (SSE)
  /health       健康检查 + 功能清单
  /stats        性能监控 (CPU/内存/延迟/队列)

LLM 三模式自动切换：
  1. 外部 Ollama (OLLAMA_HOST=http://PC_IP:11434)  → 代理转发
  2. 本地 Ollama (ollama 容器)                       → 代理转发
  3. 无 Ollama                                       → 内置苗族文化知识库

环境依赖（K1 板已预装）：
  Python 3.10+, fastapi, uvicorn, requests, Pillow
额外安装：
  pip install ultralytics
"""

import io
import os
import sys
import json
import time
import logging
import requests as http_requests
from pathlib import Path
from contextlib import asynccontextmanager
from argparse import ArgumentParser

import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException, Request

# ---------- 性能管理模块 ----------
from perf import (
    monitor, yolo_latency, llm_latency,
    yolo_guard, llm_guard, ModelWarmup,
)

# ---------- SpacemiT ASR / TTS（K1 板预装）----------
SPACEMIT_NLP_DIR = os.environ.get(
    "SPACEMIT_NLP_DIR", "/home/bainbu/spacemit-demo/examples/NLP"
)
_asr_available = os.path.isdir(SPACEMIT_NLP_DIR)
_tts_available = _asr_available

if _asr_available and SPACEMIT_NLP_DIR not in sys.path:
    sys.path.insert(0, SPACEMIT_NLP_DIR)

asr_model = None   # 懒加载
tts_model = None
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("board-server")

# ---------- 配置 ----------
STATIC_DIR = Path(__file__).resolve().parent.parent / "build"
# 容器内 build/ 可能在 /app/build
if not STATIC_DIR.exists():
    STATIC_DIR = Path(__file__).resolve().parent / "build"
# 双模型配置
CLOTHES_MODEL = os.environ.get("CLOTHES_MODEL", "clothesfp16.onnx")
SILVER_MODEL  = os.environ.get("SILVER_MODEL",  "best_fp16.onnx")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-instruct")

# ---------- K1 平台检测与优化 ----------
_ARCH = os.uname().machine
IS_RISCV = "riscv" in _ARCH
IS_K1 = IS_RISCV and os.path.exists("/proc/device-tree/model")  # K1 特有

# K1 内存优化：限制 ONNX 推理线程数（避免争抢）
if IS_K1:
    _cores = os.cpu_count() or 4
    os.environ.setdefault("OMP_NUM_THREADS", str(min(_cores, 2)))
    os.environ.setdefault("OPENBLAS_NUM_THREADS", str(min(_cores, 2)))
    logger.info(f"K1 平台检测: {_ARCH} | ONNX 线程数: {os.environ['OMP_NUM_THREADS']}")

# YOLO 模型路径自动发现
def _resolve_model(filename: str) -> str:
    """按优先级查找模型文件：ONNX > PT"""
    _server_dir = os.path.dirname(__file__)                       # server/
    _project_dir = os.path.dirname(_server_dir)                   # miao-xiu-k1/
    candidates = [
        os.path.join(_server_dir, filename),
        os.path.join(_project_dir, filename),
        "/app/models/" + filename,
        "/app/models/" + filename.replace(".onnx", ".pt"),
    ]
    for c in candidates:
        if os.path.exists(c):
            logger.info(f"找到模型: {c}")
            return c
    logger.warning(f"模型 {filename} 未找到，请确保模型文件存在于上述路径之一")
    return filename  # 返回原始路径，由 YOLODetector 自行兜底

# ---------- 苗族系统提示 ----------
SYSTEM_PROMPT = """你是"苗族阿妹"，苗族服饰文化专家。
你精通苗族银饰、刺绣（苗绣）、蜡染、百鸟衣、
银角头饰、银项圈、绣花围腰等传统服饰知识。
请用亲切专业的口吻，适当引用苗族传说、历史、
习俗回答用户问题。字数控制在200-500字。"""

# ============================================================
# YOLO 检测器（三后端自适应：onnxruntime → onnx-numpy → ultralytics）
# ============================================================
class YOLODetector:
    """
    苗族服饰/银饰检测器，自动选择后端：
      1. onnxruntime（最快，需编译/预装）
      2. onnx + numpy（纯 Python，riscv64 通用，免编译）
      3. ultralytics（兜底，需 .pt 模型 + PyTorch）
    """

    # 苗族银饰类别（best_fp16.onnx，8 类）
    MIAO_SILVER_CLASSES = {
        0: "流苏帽", 1: "苗族牛角银头饰", 2: "苗族银发簪",
        3: "苗族银冠", 4: "苗族银胸饰", 5: "苗族银锁",
        6: "苗族银项链", 7: "银头饰",
    }

    # 苗族服装类别（clothesfp16.onnx，2 类）
    MIAO_CLOTHES_CLASSES = {
        0: "苗族便装", 1: "苗族盛装",
    }

    def __init__(self, model_path: str):
        # 根据模型文件名自动选择类别映射
        if "clothes" in model_path:
            self.names = self.MIAO_CLOTHES_CLASSES
        else:
            self.names = self.MIAO_SILVER_CLASSES
        self.backend = "unknown"
        self._ort_session = None      # onnxruntime
        self._onnx_ref = None         # onnx.reference (numpy)
        self._ultra_model = None      # ultralytics
        self._input_shape = (640, 640)

        # 1. 优先：onnxruntime（C++ 加速，最快）
        if model_path.endswith(".onnx") and os.path.exists(model_path):
            if self._try_onnxruntime(model_path):
                return

        # 2. 备选：onnx + numpy（纯 Python，riscv64 免编译）
        if model_path.endswith(".onnx") and os.path.exists(model_path):
            if self._try_numpy_onnx(model_path):
                return

        # 3. 兜底：ultralytics + PyTorch（需 .pt 模型）
        if self._try_ultralytics(model_path):
            return

        raise RuntimeError(
            "无可用 YOLO 后端！请执行以下之一：\n"
            "  1. pip install onnxruntime   (x86_64/arm64 预编译)\n"
            "  2. pip install onnx          (riscv64 纯 Python，免编译)\n"
            "  3. pip install ultralytics   (.pt 模型兜底)\n"
        )

    # ---- 后端尝试 ----
    def _try_onnxruntime(self, model_path: str) -> bool:
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            self._ort_session = ort.InferenceSession(model_path, providers=providers)
            _, _, h, w = self._ort_session.get_inputs()[0].shape
            self._input_shape = (w, h)
            self.backend = f"onnxruntime ({providers[0]})"
            logger.info(f"✓ onnxruntime: {model_path} ({self.backend})")
            return True
        except ImportError:
            logger.info("onnxruntime 未安装，尝试 numpy ONNX...")
        except Exception as e:
            logger.warning(f"onnxruntime 加载失败: {e}")
        return False

    def _try_numpy_onnx(self, model_path: str) -> bool:
        """使用 onnx.reference 纯 numpy 推理（riscv64 通用方案）"""
        try:
            import onnx
            from onnx.reference import ReferenceEvaluator
            model = onnx.load(model_path)
            # 从输入节点推断尺寸
            for inp in model.graph.input:
                dims = [d.dim_value for d in inp.type.tensor_type.shape.dim]
                if len(dims) == 4:
                    self._input_shape = (dims[3], dims[2])  # (W, H)
                    break
            self._onnx_ref = ReferenceEvaluator(model)
            self.backend = "onnx+numpy (纯Python)"
            logger.info(f"✓ onnx+numpy: {model_path} (riscv64 兼容)")
            return True
        except ImportError:
            logger.info("onnx 包未安装，尝试 ultralytics...")
        except Exception as e:
            logger.warning(f"onnx+numpy 加载失败: {e}")
        return False

    def _try_ultralytics(self, model_path: str) -> bool:
        try:
            from ultralytics import YOLO
            self._ultra_model = YOLO(model_path, verbose=False)
            self.names = self._ultra_model.names
            self.backend = "ultralytics"
            logger.info(f"✓ ultralytics: {model_path}")
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"ultralytics 加载失败: {e}")
        return False

    def detect(self, img: Image.Image) -> list:
        if self._ort_session:
            return self._detect_onnx_ort(img)
        elif self._onnx_ref:
            return self._detect_onnx_numpy(img)
        elif self._ultra_model:
            return self._detect_ultralytics(img)
        return []

    # ---------- ONNX Runtime 推理 ----------
    def _detect_onnx_ort(self, img: Image.Image) -> list:
        ort_sess = self._ort_session
        in_name = ort_sess.get_inputs()[0].name
        w_in, h_in = self._input_shape
        img_w, img_h = img.size

        arr = self._preprocess(img, w_in, h_in)
        outputs = ort_sess.run(None, {in_name: arr})
        return self._postprocess_onnx(outputs[0], img_w, img_h, w_in, h_in)

    # ---------- ONNX + numpy 推理（riscv64 免编译）----------
    def _detect_onnx_numpy(self, img: Image.Image) -> list:
        ref = self._onnx_ref
        w_in, h_in = self._input_shape
        img_w, img_h = img.size

        arr = self._preprocess(img, w_in, h_in)
        # onnx.reference 输入需要是 named dict
        in_name = ref.input_names[0]
        outputs = ref.run(None, {in_name: arr})
        return self._postprocess_onnx(outputs[0], img_w, img_h, w_in, h_in)

    @staticmethod
    def _preprocess(img: Image.Image, w_in: int, h_in: int) -> np.ndarray:
        img_resized = img.resize((w_in, h_in), Image.BILINEAR)
        arr = np.array(img_resized, dtype=np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)
        arr = np.expand_dims(arr, axis=0)
        return arr

    def _postprocess_onnx(self, preds, img_w, img_h, in_w, in_h,
                          conf_thresh=0.25, iou_thresh=0.45) -> list:
        """ONNX 输出 → 苗族服饰检测结果列表"""
        preds = np.squeeze(preds)  # (84, 8400)

        # 分割 bbox 和 class scores
        bbox_raw = preds[:4, :]    # (4, 8400)  cx,cy,w,h (归一化)
        scores = preds[4:, :]       # (80, 8400)

        # 每列取最大置信度
        class_ids = np.argmax(scores, axis=0)           # (8400,)
        confs = np.max(scores, axis=0)                   # (8400,)

        # 过滤低置信度
        mask = confs > conf_thresh
        bbox_raw = bbox_raw[:, mask]
        class_ids = class_ids[mask]
        confs = confs[mask]

        if len(confs) == 0:
            return []

        # cx,cy,w,h → x1,y1,x2,y2（640 空间）
        cx, cy, w, h = bbox_raw[0], bbox_raw[1], bbox_raw[2], bbox_raw[3]
        x1 = cx - w / 2
        y1 = cy - h / 2
        x2 = cx + w / 2
        y2 = cy + h / 2

        # 缩放到原图尺寸
        scale_x = img_w / in_w
        scale_y = img_h / in_h
        x1 *= scale_x; y1 *= scale_y
        x2 *= scale_x; y2 *= scale_y

        # NMS（简单实现）
        keep = self._nms(x1, y1, x2, y2, confs, iou_thresh)

        dets = []
        for i in keep:
            cls_id = int(class_ids[i])
            dets.append({
                "class": self.names.get(cls_id, f"cls_{cls_id}"),
                "confidence": round(float(confs[i]), 4),
                "bbox": {
                    "x1": round(float(x1[i]), 1),
                    "y1": round(float(y1[i]), 1),
                    "x2": round(float(x2[i]), 1),
                    "y2": round(float(y2[i]), 1),
                },
            })
        dets.sort(key=lambda d: d["confidence"], reverse=True)
        return dets

    @staticmethod
    def _nms(x1, y1, x2, y2, confs, thresh):
        """简单 NMS，保留不重叠的高置信度框"""
        areas = (x2 - x1) * (y2 - y1)
        order = np.argsort(confs)[::-1]
        keep = []
        while len(order) > 0:
            i = order[0]
            keep.append(i)
            if len(order) == 1:
                break
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
            ovr = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
            order = order[1:][ovr < thresh]
        return keep

    # ---------- ultralytics 推理 ----------
    def _detect_ultralytics(self, img: Image.Image) -> list:
        results = self._ultra_model(img, verbose=False)
        dets = []
        r = results[0]
        if r.boxes is not None:
            boxes = r.boxes.xyxy.cpu().numpy()
            confs = r.boxes.conf.cpu().numpy()
            clss = r.boxes.cls.cpu().numpy()
            for i in range(len(boxes)):
                dets.append({
                    "class": self.names.get(int(clss[i]), f"cls_{int(clss[i])}"),
                    "confidence": round(float(confs[i]), 4),
                    "bbox": {
                        "x1": round(float(boxes[i][0]), 1),
                        "y1": round(float(boxes[i][1]), 1),
                        "x2": round(float(boxes[i][2]), 1),
                        "y2": round(float(boxes[i][3]), 1),
                    },
                })
            dets.sort(key=lambda d: d["confidence"], reverse=True)
        return dets


# ============================================================
# 双模型 Pipeline 包装器
# ============================================================
class MiaoPipelineDetector:
    """包装两个 YOLODetector，提供统一 detect(img, mode) 接口"""

    def __init__(self, silver_det: YOLODetector, clothes_det: YOLODetector):
        self.silver = silver_det
        self.clothes = clothes_det
        self.backend = f"双模型 ({silver_det.backend})"

    def detect(self, img: Image.Image, mode: str = "silver",
               use_person_filter: bool = True) -> dict:
        """
        :param mode: 'silver' | 'clothes' | 'pipeline'
        :param use_person_filter: pipeline 下用人物框过滤银饰误报
        """
        result = {"mode": mode, "clothes": [], "silver": [], "silver_filtered": [],
                  "triggered": False, "cost_ms": {}}

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
            t0 = time.perf_counter()
            result["clothes"] = self.clothes.detect(img)
            result["cost_ms"]["clothes"] = round((time.perf_counter() - t0) * 1000, 1)
            has_trigger = any(d.get("cls_id") == 1 for d in result["clothes"])
            result["triggered"] = has_trigger

            if has_trigger or len(result["clothes"]) == 0:
                t0 = time.perf_counter()
                silver_raw = self.silver.detect(img)
                result["silver"] = silver_raw
                result["cost_ms"]["silver"] = round((time.perf_counter() - t0) * 1000, 1)
                result["silver_filtered"] = self._filter_by_person(
                    silver_raw, result["clothes"]) if use_person_filter and result["clothes"] else silver_raw

        result["cost_ms"]["total"] = round(
            sum(v for v in result["cost_ms"].values() if isinstance(v, (int, float))), 1)
        return result

    @staticmethod
    def _filter_by_person(silver_dets, clothes_dets):
        filtered = []
        for s in silver_dets:
            scx = (s["bbox"]["x1"] + s["bbox"]["x2"]) / 2
            scy = (s["bbox"]["y1"] + s["bbox"]["y2"]) / 2
            for c in clothes_dets:
                if (c["bbox"]["x1"] <= scx <= c["bbox"]["x2"] and
                    c["bbox"]["y1"] <= scy <= c["bbox"]["y2"]):
                    filtered.append(s)
                    break
        return filtered


# ============================================================
# FastAPI 应用
# ============================================================
yolo_detector: MiaoPipelineDetector = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global yolo_detector, asr_model, tts_model
    logger.info("加载双 YOLO 模型...")
    _silver_path = _resolve_model(SILVER_MODEL)
    _clothes_path = _resolve_model(CLOTHES_MODEL)
    silver_det = YOLODetector(_silver_path)
    clothes_det = YOLODetector(_clothes_path)
    yolo_detector = MiaoPipelineDetector(silver_det, clothes_det)

    # ---- 加载 ASR / TTS 模型 ----
    if _asr_available:
        try:
            from spacemit_asr import ASRModel
            from spacemit_asr.models.postprocess_utils import rich_transcription_postprocess
            asr_model = ASRModel()
            logger.info(f"✓ ASR 就绪 (SenseVoice)")
        except Exception as e:
            logger.warning(f"ASR 加载失败: {e}")
    if _tts_available:
        try:
            from spacemit_tts import TTSModel
            tts_model = TTSModel()
            logger.info(f"✓ TTS 就绪 (spacemit_tts)")
        except Exception as e:
            logger.warning(f"TTS 加载失败: {e}")

    logger.info("服务就绪 ✓")

    # ---- 模型预热：首次推理前触发 JIT / 内核缓存 ----
    try:
        await ModelWarmup.warmup_yolo(yolo_detector)
        logger.info("✓ YOLO 预热完成")
    except Exception as e:
        logger.warning(f"YOLO 预热跳过: {e}")

    # Ollama 预热仅在外部服务可用时执行
    _ollama_available = False
    try:
        r = http_requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        _ollama_available = r.status_code == 200
    except Exception:
        pass

    if _ollama_available:
        try:
            await ModelWarmup.warmup_ollama(OLLAMA_HOST, OLLAMA_MODEL)
            logger.info("✓ Ollama 预热完成")
        except Exception as e:
            logger.warning(f"Ollama 预热跳过: {e}")
    else:
        logger.info("ℹ 单板独立模式 — 使用内置苗族文化知识库应答")

    # ---- 启动功能清单 ----
    logger.info("=" * 50)
    logger.info(f"  平台:     {_ARCH} {'(K1 优化)' if IS_K1 else ''}")
    logger.info(f"  YOLO:     {yolo_detector.backend}")
    logger.info(f"  知识库:   苗族银饰/刺绣/蜡染/百鸟衣（内置）")
    logger.info(f"  语音:     ASR={'✓' if asr_model else '✗'} TTS={'✓' if tts_model else '✗'}")
    logger.info(f"  外部LLM:  {'✓' if _ollama_available else '✗（使用内置知识库）'}")
    logger.info(f"  内存:     {monitor.memory_used_mb()} MB / {monitor.memory_total_mb()} MB")
    logger.info("=" * 50)

    yield
    # 可在此释放 ASR/TTS 资源

app = FastAPI(title="苗绣·识裳 K1", version="4.0.0", lifespan=lifespan,
              docs_url=None, redoc_url=None)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_SPA_INDEX = STATIC_DIR / "index.html"

# ---------- 静态文件 + SPA 回退 ----------
@app.middleware("http")
async def spa_fallback(request: Request, call_next):
    path = request.url.path
    if path.startswith(("/detect", "/chat", "/health", "/stats", "/asr", "/tts", "/voice")):
        return await call_next(request)
    fp = STATIC_DIR / path.lstrip("/")
    if fp.is_file():
        return FileResponse(fp)
    return FileResponse(_SPA_INDEX)

# ---------- /health ----------
@app.get("/health")
async def health():
    # 检测 Ollama 可用性
    ollama_ok = False
    try:
        if OLLAMA_HOST and "none" not in OLLAMA_MODEL:
            r = http_requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    return {
        "status": "ok",
        "mode": "standalone" if not ollama_ok else "connected",
        "platform": _ARCH,
        "features": {
            "frontend": "✓",
            "yolo": f"✓ ({yolo_detector.backend if yolo_detector else 'loading'})",
            "knowledge_base": "✓ (苗族银饰/刺绣/蜡染/百鸟衣)",
            "llm_external": "✓" if ollama_ok else "✗（使用内置知识库）",
            "voice_asr": "✓" if asr_model else "✗",
            "voice_tts": "✓" if tts_model else "✗",
        },
        "yolo_models": {"silver": SILVER_MODEL, "clothes": CLOTHES_MODEL},
        "modes": ["silver", "clothes", "pipeline"],
        "memory_mb": monitor.memory_used_mb(),
    }


# ---------- /stats ----------
@app.get("/stats")
async def system_stats():
    """
    返回服务端实时性能指标，供前端性能面板轮询。
    包含：CPU/内存/温度、推理延迟百分位、请求队列、后端状态。
    """
    snap = monitor.snapshot()
    return {
        "cpu_percent": snap["cpu_percent"],
        "cpu_count": snap["cpu_count"],
        "cpu_temp": snap["cpu_temp"],
        "mem_percent": snap["mem_percent"],
        "mem_used_mb": snap["mem_used_mb"],
        "mem_total_mb": snap["mem_total_mb"],
        "process_rss_mb": snap["process_rss_mb"],
        "yolo_latency": yolo_latency.stats(),
        "llm_latency": llm_latency.stats(),
        "yolo_queue": yolo_guard.stats(),
        "llm_queue": llm_guard.stats(),
        "yolo_backend": yolo_detector.backend if yolo_detector else "none",
        "yolo_models": {"silver": SILVER_MODEL, "clothes": CLOTHES_MODEL},
        "ollama_model": OLLAMA_MODEL,
    }

# ---------- /detect ----------
from fastapi import Query
@app.post("/detect")
async def detect(
    image: UploadFile = File(...),
    mode: str = Query("silver", description="silver | clothes | pipeline"),
    person_filter: bool = Query(True, description="pipeline 下启用人物框过滤"),
):
    if yolo_detector is None:
        raise HTTPException(status_code=503, detail="YOLO 未就绪")
    if mode not in ("silver", "clothes", "pipeline"):
        raise HTTPException(status_code=400, detail=f"无效模式: {mode}")
    allowed = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"}
    if image.content_type not in allowed:
        raise HTTPException(status_code=400, detail=f"不支持: {image.content_type}")

    yolo_guard.enter()
    t0 = time.perf_counter()
    try:
        await yolo_guard.acquire()
        contents = await image.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
        result = yolo_detector.detect(img, mode=mode, use_person_filter=person_filter)
        yolo_latency.record(round((time.perf_counter() - t0) * 1000, 1))
        result["success"] = True
        return JSONResponse(content=result)
    except RuntimeError as e:
        yolo_guard.error()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        yolo_guard.error()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        yolo_guard.release()
        yolo_guard.exit()

# ---------- /chat (Ollama 代理，格式翻译) ----------
@app.post("/chat")
async def chat_proxy(request: Request):
    """
    前端格式 → Ollama 格式 → 返回前端格式
    前端: {messages:[{role,content}], stream:bool}
    Ollama: {model, messages, stream, options}
    返回: {role:"assistant", content:"..."}
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效 JSON")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(status_code=400, detail="消息为空")

    # 注入系统提示
    ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    payload = {
        "model": OLLAMA_MODEL,
        "messages": ollama_messages,
        "stream": False,
        "options": {"temperature": 0.7, "top_p": 0.9},
    }

    llm_guard.enter()
    t0 = time.perf_counter()
    try:
        await llm_guard.acquire()
        resp = http_requests.post(
            f"{OLLAMA_HOST}/api/chat", json=payload, timeout=120
        )
        if resp.status_code != 200:
            logger.error(f"Ollama 错误: {resp.status_code} {resp.text[:200]}")
            raise HTTPException(status_code=502, detail=f"Ollama 返回 {resp.status_code}")
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        llm_latency.record(round((time.perf_counter() - t0) * 1000, 1))
        return JSONResponse(content={"role": "assistant", "content": content})
    except RuntimeError as e:
        llm_guard.error()
        raise HTTPException(status_code=503, detail=str(e))
    except http_requests.ConnectionError:
        llm_guard.error()
        # 无法连接 Ollama → 返回 503，前端自动切换内置知识库
        raise HTTPException(status_code=503, detail="OLLAMA_UNAVAILABLE")
    except Exception as e:
        llm_guard.error()
        logger.error(f"/chat 异常: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        llm_guard.release()
        llm_guard.exit()

# ---------- /chat/stream (SSE 流式) ----------
@app.post("/chat/stream")
async def chat_stream(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效 JSON")

    messages = body.get("messages", [])
    ollama_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + messages

    payload = {
        "model": OLLAMA_MODEL,
        "messages": ollama_messages,
        "stream": True,
        "options": {"temperature": 0.7, "top_p": 0.9},
    }

    async def generate():
        # 即时发送"思考中"状态，避免前端长时间白屏等待
        yield f"data: {json.dumps({'status': 'thinking'})}\n\n"
        try:
            resp = http_requests.post(
                f"{OLLAMA_HOST}/api/chat", json=payload, stream=True, timeout=120
            )
            for line in resp.iter_lines(decode_unicode=True):
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "message" in data and "content" in data["message"]:
                    yield f"data: {json.dumps({'content': data['message']['content']})}\n\n"
                if data.get("done"):
                    break
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")

# ============================================================
# ASR / TTS / Voice Chat 语音链路
# ============================================================
import subprocess, tempfile, wave as wav_mod

SPEAKER_DEV = os.environ.get("SPEAKER_CARD", "plughw:2,0")

# ---------- POST /asr ----------
@app.post("/asr")
async def asr_transcribe(audio: UploadFile = File(...)):
    """语音→文字。支持常见音频格式（自动转为 16kHz 单声道 WAV），返回识别文本。"""
    if asr_model is None:
        raise HTTPException(status_code=503, detail="ASR 未就绪")

    # 1. 保存上传的原始音频到临时文件
    with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp_raw:
        content = await audio.read()
        tmp_raw.write(content)
        raw_path = tmp_raw.name

    # 2. 检查是否为真正的 WAV 文件（RIFF 头）
    def _is_wav(filepath: str) -> bool:
        with open(filepath, 'rb') as f:
            return f.read(4) == b'RIFF'

    if _is_wav(raw_path):
        audio_path = raw_path
        need_cleanup = False
    else:
        # 转码为 16kHz 单声道 PCM WAV
        wav_fd, wav_path = tempfile.mkstemp(suffix='.wav')
        os.close(wav_fd)
        cmd = [
            'ffmpeg', '-i', raw_path,
            '-acodec', 'pcm_s16le',
            '-ar', '16000',
            '-ac', '1',
            '-y', wav_path
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
            os.unlink(raw_path)
            if os.path.exists(wav_path):
                os.unlink(wav_path)
            raise HTTPException(status_code=400, detail=f"音频转码失败: {str(e)}")
        os.unlink(raw_path)
        audio_path = wav_path
        need_cleanup = True

    # 3. 调用 ASR 推理
    try:
        from spacemit_asr.models.postprocess_utils import rich_transcription_postprocess
        result = asr_model.generate(audio_path)
        if isinstance(result, list) and result:
            raw = result[0]
            raw_text = raw[0] if isinstance(raw, list) else raw
        elif isinstance(result, str):
            raw_text = result
        else:
            raw_text = str(result)

        text = rich_transcription_postprocess(raw_text)
        return JSONResponse(content={"text": text, "raw": str(raw_text)[:200]})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ASR 推理失败: {str(e)}")
    finally:
        if need_cleanup:
            try: os.unlink(audio_path)
            except OSError: pass
        else:
            try: os.unlink(raw_path)
            except OSError: pass


# ---------- POST /tts ----------
@app.post("/tts")
async def tts_synthesize(request: Request):
    """文字→语音。请求 {"text":"..."}，返回 WAV 音频。"""
    if tts_model is None:
        raise HTTPException(status_code=503, detail="TTS 未就绪")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效 JSON")
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 为空")
    if len(text) > 500:
        text = text[:500]

    audio_file = tts_model.ort_predict(text)
    async def _cleanup():
        if os.path.exists(audio_file):
            os.unlink(audio_file)
    return FileResponse(audio_file, media_type="audio/wav",
                        filename="speech.wav",
                        background=_cleanup)


# ---------- POST /voice/chat ----------
@app.post("/voice/chat")
async def voice_chat(audio: UploadFile = File(...)):
    """
    一站式语音对话：音频→ASR→LLM→TTS→音频返回
    返回: {"text": "识别的文字", "reply": "AI回复", "audio_url": "/voice/audio?id=xxx"}
    """
    if asr_model is None or tts_model is None:
        raise HTTPException(status_code=503, detail="ASR 或 TTS 未就绪")

    try:
        from spacemit_asr.models.postprocess_utils import rich_transcription_postprocess
    except ImportError:
        raise HTTPException(status_code=500, detail="ASR 后处理模块缺失")

    # ---- Step 1: ASR ----
    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    try:
        tmp_wav.write(await audio.read())
        tmp_wav.close()

        result = asr_model.generate(tmp_wav.name)
        if isinstance(result, list) and result:
            raw = result[0]
            raw_text = raw[0] if isinstance(raw, list) else raw
        elif isinstance(result, str):
            raw_text = result
        else:
            raw_text = str(result)
        user_text = rich_transcription_postprocess(raw_text)
    finally:
        try: os.unlink(tmp_wav.name)
        except OSError: pass

    if not user_text:
        return JSONResponse(content={"text": "", "reply": "", "error": "未识别到语音"})

    # ---- Step 2: LLM ----
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "options": {"temperature": 0.7, "top_p": 0.9},
    }
    try:
        resp = http_requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=120)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Ollama: {resp.status_code}")
        reply = resp.json().get("message", {}).get("content", "")
    except http_requests.ConnectionError:
        raise HTTPException(status_code=503, detail="Ollama 连接失败")

    # ---- Step 3: TTS ----
    try:
        audio_path = tts_model.ort_predict(reply[:500])
    except Exception as e:
        logger.error(f"TTS 合成失败: {e}")
        return JSONResponse(content={"text": user_text, "reply": reply, "audio_url": None})

    # 保存到临时持久化文件（供后续下载）
    persist_dir = Path(tempfile.gettempdir()) / "miao_tts"
    persist_dir.mkdir(exist_ok=True)
    persist_path = persist_dir / f"voice_{int(time.time())}.wav"
    os.rename(audio_path, persist_path)

    return JSONResponse(content={
        "text": user_text,
        "reply": reply,
        "audio_url": f"/voice/audio?file={persist_path.name}",
    })


# ---------- GET /voice/audio ----------
@app.get("/voice/audio")
async def get_audio(file: str = ""):
    """下载 TTS 生成的音频文件"""
    if not file or "/" in file:
        raise HTTPException(status_code=400, detail="无效文件名")
    audio_path = Path(tempfile.gettempdir()) / "miao_tts" / file
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="音频已过期")
    return FileResponse(audio_path, media_type="audio/wav")

# ============================================================
if __name__ == "__main__":
    import uvicorn
    parser = ArgumentParser()
    parser.add_argument("--port", type=int, default=80)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()

    if not _SPA_INDEX.exists():
        logger.error(f"前端文件不存在: {_SPA_INDEX}")
        logger.error("请在 PC 上执行 npm run build，然后将 build/ 复制到本目录")
        sys.exit(1)

    logger.info(f"静态目录: {STATIC_DIR}")
    logger.info(f"Ollama: {OLLAMA_HOST} / {OLLAMA_MODEL}")
    logger.info(f"启动 http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
