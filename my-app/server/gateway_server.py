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
import os, json, logging, time
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

# ---- Ollama 模型自动发现（懒加载 + 缓存 + 可重试）----
# 优先级: 环境变量 OLLAMA_MODEL > 关键字匹配(miao/qwen/...) > 首个可用 > 兜底
# 缓存 60s，Ollama 未就绪时自动重试，避免启动顺序依赖

_OLLAMA_MODEL_CACHE = None
_OLLAMA_MODEL_CACHE_TIME = 0.0
_MODEL_CACHE_TTL = 60.0  # 缓存有效期（秒）

def _discover_ollama_model(host: str, force: bool = False) -> str:
    """懒加载 Ollama 模型名，失败时自动重试"""
    global _OLLAMA_MODEL_CACHE, _OLLAMA_MODEL_CACHE_TIME

    # 1) 环境变量始终优先（不走缓存）
    env_model = os.environ.get("OLLAMA_MODEL", "").strip()
    if env_model:
        logger.info(f"Ollama 模型: {env_model} (环境变量 OLLAMA_MODEL)")
        return env_model

    # 2) 命中缓存直接返回
    now = time.time()
    if not force and _OLLAMA_MODEL_CACHE and (now - _OLLAMA_MODEL_CACHE_TIME) < _MODEL_CACHE_TTL:
        return _OLLAMA_MODEL_CACHE

    # 3) 查询 Ollama 已注册模型
    try:
        r = http_requests.get(f"{host}/api/tags", timeout=5)
        if r.status_code != 200:
            raise ConnectionError(f"HTTP {r.status_code}")
        models = [m["name"] for m in r.json().get("models", [])]
        if not models:
            raise ValueError("无已注册模型")

        logger.info(f"Ollama 可用模型 ({len(models)}): {', '.join(models[:8])}{'...' if len(models) > 8 else ''}")

        # 4) 按关键字优先级匹配（可通过 OLLAMA_MODEL_KEYWORDS 自定义）
        keywords = os.environ.get("OLLAMA_MODEL_KEYWORDS", "miao,qwen").split(",")
        for kw in keywords:
            kw = kw.strip()
            if not kw:
                continue
            matching = [m for m in models if kw.lower() in m.lower()]
            if matching:
                # 优先选不含 :latest 标签的
                custom = [m for m in matching if ":latest" not in m]
                selected = (custom or matching)[0]
                logger.info(f"Ollama 模型: {selected} (匹配 '{kw}')")
                _OLLAMA_MODEL_CACHE = selected
                _OLLAMA_MODEL_CACHE_TIME = now
                return selected

        # 5) 无关键字匹配 → 返回首个可用模型
        selected = models[0]
        logger.info(f"Ollama 模型: {selected} (首个可用, 无关键字匹配)")
        _OLLAMA_MODEL_CACHE = selected
        _OLLAMA_MODEL_CACHE_TIME = now
        return selected

    except Exception as e:
        logger.warning(f"无法查询 Ollama 模型列表: {e}")
        # 6) 返回缓存旧值或兜底
        fallback = _OLLAMA_MODEL_CACHE or "miao-qwen"
        logger.warning(f"Ollama 模型: {fallback} (兜底)")
        return fallback

def get_ollama_model() -> str:
    """获取当前 Ollama 模型名（线程安全懒加载）"""
    return _discover_ollama_model(OLLAMA_HOST)

def refresh_ollama_model() -> str:
    """强制刷新模型发现缓存"""
    return _discover_ollama_model(OLLAMA_HOST, force=True)

OLLAMA_MODEL = get_ollama_model()  # 启动时尝试一次，失败不阻塞

# 后端微服务地址（host 网络模式下用 localhost）
YOLO_URL = os.environ.get("YOLO_URL", "http://127.0.0.1:8000")
ASR_URL  = os.environ.get("ASR_URL",  "http://127.0.0.1:8001")
TTS_URL  = os.environ.get("TTS_URL",  "http://127.0.0.1:8002")

_ARCH = os.uname().machine

# 不再注入 system prompt — 由 Modelfile 的 SYSTEM 指令统一管理
# 如需覆盖，设置环境变量 OLLAMA_SYSTEM_PROMPT
_SYSTEM_PROMPT = os.environ.get("OLLAMA_SYSTEM_PROMPT", None)

# ---- 性能监控（复用 perf.py 模块）----
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
    # YOLO + ASR 始终在 K1 本地
    for name, url in [("yolo", f"{YOLO_URL}/health"), ("asr", f"{ASR_URL}/health")]:
        try:
            r = http_requests.get(url, timeout=3)
            svc[name] = "✓" if r.status_code == 200 else f"✗({r.status_code})"
        except Exception:
            svc[name] = "✗"
    # TTS: swarm 模式下在远程 PC，跳过健康检查
    tts_is_remote = "127.0.0.1" not in TTS_URL and "localhost" not in TTS_URL
    if tts_is_remote:
        svc["tts"] = f"→ {TTS_URL}"  # 远程服务，不检查
    else:
        try:
            r = http_requests.get(f"{TTS_URL}/health", timeout=3)
            svc["tts"] = "✓" if r.status_code == 200 else f"✗({r.status_code})"
        except Exception:
            svc["tts"] = "✗"
    ollama_ok = False
    try:
        r = http_requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        ollama_ok = r.status_code == 200
    except: pass
    return {
        "status": "ok",
        "platform": _ARCH,
        "mode": "swarm" if tts_is_remote else "standalone",
        "services": svc,
        "ollama": "✓" if ollama_ok else "✗",
        "memory_mb": monitor.memory_used_mb(),
    }

# ---- /ollama/models ----  列出所有可用模型
@app.get("/ollama/models")
async def list_ollama_models():
    """返回 Ollama 已注册的所有模型 + 当前选用"""
    try:
        r = http_requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if r.status_code != 200:
            raise HTTPException(502, f"Ollama 返回 {r.status_code}")
        all_models = [m["name"] for m in r.json().get("models", [])]
    except http_requests.ConnectionError:
        raise HTTPException(503, "Ollama 服务不可达")
    except Exception as e:
        raise HTTPException(500, str(e))

    return {
        "models": all_models,
        "active": get_ollama_model(),
        "count": len(all_models),
    }

# ---- /ollama/refresh ----  强制刷新模型发现
@app.post("/ollama/refresh")
async def refresh_ollama():
    """强制重新发现 Ollama 模型（Ollama 重启后调用）"""
    new_model = refresh_ollama_model()
    logger.info(f"模型已刷新: {new_model}")
    return {"model": new_model, "status": "refreshed"}

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
        "ollama_model": get_ollama_model(),
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

# ---- /tts → tts:8002 (K1 本地或 Swarm 远程 PC) ----
@app.post("/tts")
async def tts_synthesize(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "无效 JSON")
    t0 = time.perf_counter()
    # Swarm 模式下 TTS 在远程 PC，网络延迟较高，超时放宽到 180s
    tts_is_remote = "127.0.0.1" not in TTS_URL and "localhost" not in TTS_URL
    tts_timeout = 180 if tts_is_remote else 120
    try:
        r = http_requests.post(f"{TTS_URL}/tts", json=body, timeout=tts_timeout)
        proxy_latency.record(round((time.perf_counter() - t0) * 1000, 1))
        if r.status_code != 200:
            raise HTTPException(502, f"TTS 返回 {r.status_code}")
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
        target = f"远程 PC ({TTS_URL})" if tts_is_remote else "本地 TTS"
        raise HTTPException(503, f"{target} 服务不可达")
    except http_requests.Timeout:
        raise HTTPException(504, f"TTS 合成超时 ({tts_timeout}s)")

# ---- /chat (Ollama 代理) ----
@app.post("/chat")
async def chat(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "无效 JSON")
    messages = body.get("messages", [])
    # K1 速优：仅保留最近 6 条消息（3 轮），防 prompt 膨胀
    if len(messages) > 6:
        messages = messages[-6:]
    ollama_msgs = []
    if _SYSTEM_PROMPT:
        ollama_msgs.append({"role": "system", "content": _SYSTEM_PROMPT})
    ollama_msgs += messages
    payload = {"model": get_ollama_model(), "messages": ollama_msgs, "stream": False,
               "options": {"num_ctx": 768, "num_predict": 150, "num_thread": 4}}
    logger.info(f"→ Ollama /api/chat model={payload['model']} msgs={len(ollama_msgs)}")
    llm_guard.enter()
    t0 = time.perf_counter()
    try:
        await llm_guard.acquire()
        r = http_requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=120)
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        llm_latency.record(elapsed)
        if r.status_code != 200:
            detail = r.text[:300]
            logger.error(f"Ollama 错误 {r.status_code}: {detail}")
            if "not found" in detail.lower():
                raise HTTPException(502, f"模型 '{payload['model']}' 不存在。可用: GET /ollama/models")
            raise HTTPException(502, f"Ollama 返回 {r.status_code}: {detail}")
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
    # K1 速优：仅保留最近 6 条消息（3 轮），防 prompt 膨胀
    if len(messages) > 6:
        messages = messages[-6:]
    ollama_msgs_chat = []
    if _SYSTEM_PROMPT:
        ollama_msgs_chat.append({"role": "system", "content": _SYSTEM_PROMPT})
    ollama_msgs_chat += messages
    payload = {"model": get_ollama_model(), "messages": ollama_msgs_chat, "stream": True,
               "options": {"num_ctx": 768, "num_predict": 150, "num_thread": 4}}

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
