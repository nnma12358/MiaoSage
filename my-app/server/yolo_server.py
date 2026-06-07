"""
苗绣·识裳 — YOLOv8n 图像检测后端服务
使用 FastAPI + ultralytics YOLOv8n 提供苗族服饰目标检测 API

启动方式：
  pip install -r server/requirements.txt
  python server/yolo_server.py

API 端点：
  POST /detect  — 上传图像，返回 YOLOv8n 检测结果
  GET  /health  — 健康检查
"""

import io
import time
import logging
from contextlib import asynccontextmanager

import numpy as np
from PIL import Image
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from ultralytics import YOLO

# ---------- 性能管理 ----------
from perf import monitor, yolo_latency, yolo_guard

# ---------- 日志 ----------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("yolo-server")

# ---------- 全局模型 ----------
model: YOLO | None = None
MODEL_NAME = "yolov8n.pt"  # 可替换为自定义训练的苗族服饰模型路径


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时加载模型，关闭时释放资源。"""
    global model
    logger.info(f"正在加载 YOLO 模型: {MODEL_NAME} ...")
    model = YOLO(MODEL_NAME)
    logger.info("YOLO 模型加载完成 ✓")
    yield
    # 清理（可选）
    logger.info("服务关闭")


app = FastAPI(
    title="苗绣·识裳 YOLOv8n 检测服务",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------- CORS（允许前端跨域访问） ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 生产环境请限制为前端域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "model_loaded": model is not None,
    }


@app.get("/stats")
async def system_stats():
    """返回服务端实时性能指标"""
    snap = monitor.snapshot()
    return {
        "cpu_percent": snap["cpu_percent"],
        "cpu_count": snap["cpu_count"],
        "cpu_temp": snap["cpu_temp"],
        "mem_percent": snap["mem_percent"],
        "mem_used_mb": snap["mem_used_mb"],
        "process_rss_mb": snap["process_rss_mb"],
        "yolo_latency": yolo_latency.stats(),
        "yolo_queue": yolo_guard.stats(),
        "model": MODEL_NAME,
        "model_loaded": model is not None,
    }


@app.post("/detect")
async def detect_objects(image: UploadFile = File(...)):
    """
    图像目标检测接口

    - 接受 multipart/form-data 上传的图片（jpg/png/webp 等）
    - 使用 YOLOv8n 进行推理
    - 返回检测到的物体类别、置信度与边界框
    """
    global model
    if model is None:
        raise HTTPException(status_code=503, detail="模型尚未加载完成，请稍后重试")

    # 1. 校验文件类型
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"}
    if image.content_type and image.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {image.content_type}，请上传 jpg/png/webp 图片",
        )

    yolo_guard.enter()
    t0 = time.perf_counter()
    try:
        await yolo_guard.acquire()
        # 2. 读取上传的图片
        contents = await image.read()
        img = Image.open(io.BytesIO(contents)).convert("RGB")
        logger.info(f"收到图片: {image.filename}, 尺寸: {img.size}")

        # 3. YOLOv8n 推理
        results = model(img, verbose=False)  # verbose=False 减少控制台输出
        yolo_latency.record(round((time.perf_counter() - t0) * 1000, 1))
        result = results[0]  # 单张图片取第一个结果

        # 4. 提取检测信息
        detections = []
        if result.boxes is not None:
            boxes = result.boxes.xyxy.cpu().numpy()      # [N, 4] 边界框坐标
            confidences = result.boxes.conf.cpu().numpy() # [N]   置信度
            class_ids = result.boxes.cls.cpu().numpy()    # [N]   类别 ID

            for i in range(len(boxes)):
                class_id = int(class_ids[i])
                class_name = model.names.get(class_id, f"class_{class_id}")
                detections.append({
                    "class": class_name,
                    "confidence": round(float(confidences[i]), 4),
                    "bbox": {
                        "x1": round(float(boxes[i][0]), 2),
                        "y1": round(float(boxes[i][1]), 2),
                        "x2": round(float(boxes[i][2]), 2),
                        "y2": round(float(boxes[i][3]), 2),
                    },
                })

            # 按置信度降序排列
            detections.sort(key=lambda d: d["confidence"], reverse=True)

        logger.info(f"检测完成: {len(detections)} 个目标 → {[d['class'] for d in detections[:5]]}")

        return JSONResponse(content={
            "success": True,
            "detections": detections,
            "count": len(detections),
            "image_size": {"width": img.width, "height": img.height},
        })

    except RuntimeError as e:
        yolo_guard.error()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        yolo_guard.error()
        logger.error(f"推理失败: {e}")
        raise HTTPException(status_code=500, detail=f"YOLO 推理异常: {str(e)}")
    finally:
        yolo_guard.release()
        yolo_guard.exit()


# ---------- 直接运行 ----------
if __name__ == "__main__":
    import uvicorn
    logger.info("启动 YOLOv8n 检测服务 (http://localhost:8000) ...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
