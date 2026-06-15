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

# ---- 简易性能统计 ----
class PerfStats:
    def __init__(self):
        self._mem = {}
    def memory_used_mb(self):
        try:
            with open("/proc/self/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) // 1024
        except: pass
        return 0
    def memory_total_mb(self):
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        return int(line.split()[1]) // 1024
        except: pass
        return 0
    def snapshot(self):
        return {
            "cpu_percent": 0, "cpu_count": os.cpu_count() or 4,
            "cpu_temp": None, "mem_percent": 0,
            "mem_used_mb": self.memory_used_mb(),
            "mem_total_mb": self.memory_total_mb(),
            "process_rss_mb": self.memory_used_mb(),
        }

perf = PerfStats()

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
        "memory_mb": perf.memory_used_mb(),
    }

# ---- /stats ----
@app.get("/stats")
async def stats():
    snap = perf.snapshot()
    return {**snap, "ollama_model": OLLAMA_MODEL}

# ---- /detect → yolo:8000 ----
@app.post("/detect")
async def detect(image: UploadFile = File(...)):
    contents = await image.read()
    try:
        r = http_requests.post(f"{YOLO_URL}/detect",
            files={"image": (image.filename or "img.jpg", contents, image.content_type or "image/jpeg")},
            timeout=60)
        if r.status_code != 200:
            raise HTTPException(502, f"YOLO 返回 {r.status_code}")
        return r.json()
    except http_requests.ConnectionError:
        raise HTTPException(503, "YOLO 服务不可用")

# ---- /asr → asr:8001 ----
@app.post("/asr")
async def asr_transcribe(audio: UploadFile = File(...)):
    contents = await audio.read()
    try:
        r = http_requests.post(f"{ASR_URL}/asr",
            files={"audio": (audio.filename or "audio.wav", contents, audio.content_type or "audio/wav")},
            timeout=120)
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
    try:
        r = http_requests.post(f"{TTS_URL}/tts", json=body, timeout=120)
        if r.status_code != 200:
            raise HTTPException(502, f"TTS 返回 {r.status_code}")
        return Response(content=r.content, media_type="audio/wav")
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
    try:
        r = http_requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=120)
        if r.status_code != 200:
            raise HTTPException(502, f"Ollama 返回 {r.status_code}: {r.text[:200]}")
        content = r.json().get("message", {}).get("content", "")
        return {"role": "assistant", "content": content}
    except http_requests.ConnectionError:
        raise HTTPException(503, "OLLAMA_UNAVAILABLE")

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
