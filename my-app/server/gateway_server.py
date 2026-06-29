#!/usr/bin/env python3
"""
苗绣·识裳 — API 网关 (K1 多容器架构)
========================================================
路由：
  /              前端 SPA
  /detect        → yolo:8000
  /asr           → asr:8001
  /tts           → tts:8002
  /chat          → Ollama (宿主机)
  /chat/stream   → Ollama (宿主机) SSE
  /health        全服务健康检查
  /stats         性能监控
"""
import os, json, logging
from pathlib import Path

import requests as http_requests
from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("gateway")

# ---- 配置 ----
STATIC_DIR = Path(__file__).resolve().parent.parent / "build"
if not STATIC_DIR.exists():
    STATIC_DIR = Path(__file__).resolve().parent / "build"

OLLAMA_HOST  = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-instruct")

# 后端微服务地址（host 网络模式下用 localhost）
YOLO_URL = os.environ.get("YOLO_URL", "http://127.0.0.1:8000")
ASR_URL  = os.environ.get("ASR_URL",  "http://127.0.0.1:8001")
TTS_URL  = os.environ.get("TTS_URL",  "http://127.0.0.1:8002")

_ARCH = os.uname().machine

SYSTEM_PROMPT = """你是"苗族阿妹"，苗族服饰文化专家。
你精通苗族银饰、刺绣（苗绣）、蜡染、百鸟衣、
银角头饰、银项圈、绣花围腰等传统服饰知识。
请用亲切专业的口吻，适当引用苗族传说、历史、
习俗回答用户问题。字数控制在200-500字。"""

# ---- 性能监控（复用 perf.py 模块）----
import time
from perf import monitor, LatencyTracker, ConcurrencyGuard

# 网关代理延迟追踪 & 各服务独立追踪
yolo_latency  = LatencyTracker(window_size=100)
llm_latency   = LatencyTracker(window_size=50)
proxy_latency = LatencyTracker(window_size=100)

# 请求队列守卫（与 board_server 保持一致，供前端面板展示）
yolo_guard = ConcurrencyGuard(max_concurrent=2, timeout=120)
llm_guard  = ConcurrencyGuard(max_concurrent=1, timeout=180)

# ---- 服务代理 ----
def _proxy_post(url: str, files: dict = None, json_data: dict = None, stream: bool = False, timeout: int = 120):
    """统一后端代理调用"""
    try:
        if files:
            return http_requests.post(url, files=files, timeout=timeout)
        elif stream:
            return http_requests.post(url, json=json_data, stream=True, timeout=timeout)
        else:
            return http_requests.post(url, json=json_data, timeout=timeout)
    except http_requests.ConnectionError:
        raise HTTPException(503, f"后端服务不可达: {url}")
    except http_requests.Timeout:
        raise HTTPException(504, f"后端服务超时: {url}")

# ============================================================
app = FastAPI(title="苗绣·识裳 K1 网关", version="5.0.0", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

_SPA_INDEX = STATIC_DIR / "index.html"

# ---- SPA 回退 ----
@app.middleware("http")
async def spa_fallback(request: Request, call_next):
    path = request.url.path
    api_prefixes = ("/detect", "/chat", "/health", "/stats", "/asr", "/tts", "/voice")
    if path.startswith(api_prefixes):
        return await call_next(request)
    fp = STATIC_DIR / path.lstrip("/")
    if fp.is_file():
        return FileResponse(fp)
    if _SPA_INDEX.exists():
        return FileResponse(_SPA_INDEX)
    return JSONResponse({"error": "SPA not found"}, status_code=404)

# ---- /health ----
@app.get("/health")
async def health():
    svc = {}
    for name, url in [("yolo", f"{YOLO_URL}/health"), ("asr", f"{ASR_URL}/health"), ("tts", f"{TTS_URL}/health")]:
        try:
            r = http_requests.get(url, timeout=3)
            svc[name] = "✓" if r.status_code == 200 else f"✗({r.status_code})"
        except Exception:
            svc[name] = "✗"
    ollama_ok = False
    try:
        r = http_requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        ollama_ok = r.status_code == 200
    except: pass
    return {
        "status": "ok",
        "platform": _ARCH,
        "services": svc,
        "ollama": "✓" if ollama_ok else "✗",
        "memory_mb": monitor.memory_used_mb(),
    }

# ---- /stats ----
@app.get("/stats")
async def stats():
    snap = monitor.snapshot()
    # 尝试从 YOLO 服务拉取健康信息（获取后端实际状态）
    yolo_backend = "unknown"
    yolo_models = {"silver": "N/A", "clothes": "N/A"}
    try:
        r = http_requests.get(f"{YOLO_URL}/health", timeout=2)
        if r.status_code == 200:
            data = r.json()
            yolo_backend = "onnxruntime"
            yolo_models = data.get("models", yolo_models)
    except Exception:
        pass

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
        "yolo_backend": yolo_backend,
        "yolo_models": yolo_models,
        "ollama_model": OLLAMA_MODEL,
        "proxy_latency": proxy_latency.stats(),
    }

# ---- /detect → yolo:8000 ----
@app.post("/detect")
async def detect(image: UploadFile = File(...)):
    contents = await image.read()
    yolo_guard.enter()
    t0 = time.perf_counter()
    try:
        await yolo_guard.acquire()
        r = http_requests.post(f"{YOLO_URL}/detect",
            files={"image": (image.filename or "img.jpg", contents, image.content_type or "image/jpeg")},
            timeout=60)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        yolo_latency.record(elapsed)
        proxy_latency.record(elapsed)
        if r.status_code != 200:
            raise HTTPException(502, f"YOLO 返回 {r.status_code}")
        return r.json()
    except http_requests.ConnectionError:
        yolo_guard.error()
        raise HTTPException(503, "YOLO 服务不可用")
    except Exception as e:
        yolo_guard.error()
        raise e
    finally:
        yolo_guard.release()
        yolo_guard.exit()

# ---- /asr → asr:8001 ----
@app.post("/asr")
async def asr_transcribe(audio: UploadFile = File(...)):
    contents = await audio.read()
    t0 = time.perf_counter()
    try:
        r = http_requests.post(f"{ASR_URL}/asr",
            files={"audio": (audio.filename or "audio.wav", contents, audio.content_type or "audio/wav")},
            timeout=120)
        proxy_latency.record(round((time.perf_counter() - t0) * 1000, 1))
        if r.status_code != 200:
            raise HTTPException(502, f"ASR 返回 {r.status_code}")
        return r.json()
    except http_requests.ConnectionError:
        raise HTTPException(503, "ASR 服务不可用")

# ---- /tts → tts:8002 ----
@app.post("/tts")
async def tts_synthesize(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "无效 JSON")
    t0 = time.perf_counter()
    try:
        r = http_requests.post(f"{TTS_URL}/tts", json=body, timeout=120)
        proxy_latency.record(round((time.perf_counter() - t0) * 1000, 1))
        if r.status_code != 200:
            raise HTTPException(502, f"TTS 返回 {r.status_code}")
        # 显式设置音频响应头，确保浏览器能解码播放
        return Response(
            content=r.content,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline; filename=speech.wav",
                "Accept-Ranges": "bytes",
                "Content-Length": str(len(r.content)),
            },
        )
    except http_requests.ConnectionError:
        raise HTTPException(503, "TTS 服务不可用")

# ---- /chat (Ollama 代理) ----
@app.post("/chat")
async def chat(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "无效 JSON")
    messages = body.get("messages", [])
    ollama_msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    payload = {"model": OLLAMA_MODEL, "messages": ollama_msgs, "stream": False,
               "options": {"temperature": 0.7, "top_p": 0.9}}
    llm_guard.enter()
    t0 = time.perf_counter()
    try:
        await llm_guard.acquire()
        r = http_requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=120)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        llm_latency.record(elapsed)
        if r.status_code != 200:
            raise HTTPException(502, f"Ollama 返回 {r.status_code}: {r.text[:200]}")
        content = r.json().get("message", {}).get("content", "")
        return {"role": "assistant", "content": content}
    except http_requests.ConnectionError:
        llm_guard.error()
        raise HTTPException(503, "OLLAMA_UNAVAILABLE")
    except Exception as e:
        llm_guard.error()
        raise e
    finally:
        llm_guard.release()
        llm_guard.exit()

# ---- /chat/stream (SSE) ----
@app.post("/chat/stream")
async def chat_stream(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "无效 JSON")
    messages = body.get("messages", [])
    ollama_msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + messages
    payload = {"model": OLLAMA_MODEL, "messages": ollama_msgs, "stream": True,
               "options": {"temperature": 0.7, "top_p": 0.9}}

    async def generate():
        yield f"data: {json.dumps({'status': 'thinking'})}\n\n"
        try:
            r = http_requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, stream=True, timeout=120)
            for line in r.iter_lines(decode_unicode=True):
                if not line: continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "message" in d and "content" in d["message"]:
                    yield f"data: {json.dumps({'content': d['message']['content']})}\n\n"
                if d.get("done"): break
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")

# ============================================================
if __name__ == "__main__":
    import uvicorn
    from argparse import ArgumentParser
    p = ArgumentParser()
    p.add_argument("--port", type=int, default=443)
    p.add_argument("--host", type=str, default="0.0.0.0")
    p.add_argument("--ssl-keyfile", type=str, default=None)
    p.add_argument("--ssl-certfile", type=str, default=None)
    args = p.parse_args()
    if not _SPA_INDEX.exists():
        logger.error(f"前端不存在: {_SPA_INDEX}")
    logger.info(f"网关启动: {args.host}:{args.port} | YOLO={YOLO_URL} ASR={ASR_URL} TTS={TTS_URL} Ollama={OLLAMA_HOST}")
    uvicorn.run(app, host=args.host, port=args.port,
                ssl_keyfile=args.ssl_keyfile, ssl_certfile=args.ssl_certfile,
                workers=1, log_level="info")
