#!/usr/bin/env python3
"""苗绣·识裳 — YOLOv8n 检测微服务 (K1/riscv64, spacemit-ort)"""
import io, os, time, logging
import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("yolo-server")

YOLO_MODEL = os.environ.get("YOLO_MODEL", "/app/yolov8n.onnx")

COCO_NAMES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane",
    5: "bus", 6: "train", 7: "truck", 8: "boat", 9: "traffic light",
    10: "fire hydrant", 11: "stop sign", 12: "parking meter", 13: "bench",
    14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
    20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack",
    25: "umbrella", 26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee",
    30: "skis", 31: "snowboard", 32: "sports ball", 33: "kite",
    34: "baseball bat", 35: "baseball glove", 36: "skateboard",
    37: "surfboard", 38: "tennis racket", 39: "bottle", 40: "wine glass",
    41: "cup", 42: "fork", 43: "knife", 44: "spoon", 45: "bowl",
    46: "banana", 47: "apple", 48: "sandwich", 49: "orange",
    50: "broccoli", 51: "carrot", 52: "hot dog", 53: "pizza", 54: "donut",
    55: "cake", 56: "chair", 57: "couch", 58: "potted plant", 59: "bed",
    60: "dining table", 61: "toilet", 62: "tv", 63: "laptop", 64: "mouse",
    65: "remote", 66: "keyboard", 67: "cell phone", 68: "microwave",
    69: "oven", 70: "toaster", 71: "sink", 72: "refrigerator", 73: "book",
    74: "clock", 75: "vase", 76: "scissors", 77: "teddy bear",
    78: "hair drier", 79: "toothbrush",
}

class YOLODetector:
    def __init__(self, model_path: str):
        import onnxruntime as ort
        self._session = ort.InferenceSession(model_path, providers=ort.get_available_providers())
        _, _, h, w = self._session.get_inputs()[0].shape
        self._input_shape = (w, h)
        self._in_name = self._session.get_inputs()[0].name
        logger.info(f"YOLO 模型加载: {model_path} ({self._input_shape})")

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
                "class": COCO_NAMES.get(int(class_ids[i]), f"cls_{int(class_ids[i])}"),
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
