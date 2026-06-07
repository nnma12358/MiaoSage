"""
苗绣·识裳 — LLM 对话服务（Qwen2.5-Instruct）
========================================================
提供苗族文化智能问答 API，支持两种后端：
  1. Ollama 代理模式（推荐，需要 Ollama 运行 Qwen2.5）
  2. Transformers 直接推理模式（备用，独立运行）

启动方式：
  # 模式 1：连接 Ollama
  python server/llm_server.py
  
  # 模式 2：独立推理（自动下载 Qwen2.5-0.5B）
  python server/llm_server.py --direct

API：
  POST /chat          聊天对话
  POST /chat/stream   流式对话（SSE）
  GET  /health        健康检查
"""

import os
import json
import time
import logging
from contextlib import asynccontextmanager
from argparse import ArgumentParser

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# ---------- 性能管理 ----------
from perf import monitor, llm_latency, llm_guard

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("llm-server")

# ---------- 配置 ----------
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:0.5b")  # 0.5B 适合嵌入式
DIRECT_MODE = os.environ.get("DIRECT_MODE", "0") == "1"

# ---------- 数据模型 ----------
class ChatRequest(BaseModel):
    messages: list[dict]  # [{"role":"user","content":"..."}]
    stream: bool = False

# ---------- 苗族文化系统提示词 ----------
SYSTEM_PROMPT = """你是"苗族阿妹"，一位苗族服饰文化专家助手。
你的知识涵盖苗族银饰、刺绣（苗绣）、蜡染、百鸟衣、银角头饰、银项圈、绣花围腰等传统服饰。
请用亲切、专业的口吻回答用户关于苗族文化的问题。
如果用户上传了图片，你已通过 YOLO 视觉模型获得检测结果，请据此解读服饰的文化内涵。
回答时请使用中文，适当引用苗族传说、历史、习俗。字数控制在 200-500 字。"""

# ============================================================
# 后端 1：Ollama 代理
# ============================================================
class OllamaClient:
    def __init__(self, host: str, model: str):
        self.host = host
        self.model = model
        logger.info(f"Ollama 模式: {host} / {model}")

    async def chat(self, messages: list[dict]) -> str:
        import aiohttp
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "stream": False,
            "options": {"temperature": 0.7, "top_p": 0.9},
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.host}/api/chat", json=payload, timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                if resp.status != 200:
                    raise HTTPException(status_code=502, detail=f"Ollama 错误: {resp.status}")
                data = await resp.json()
                return data.get("message", {}).get("content", "")

    async def chat_stream(self, messages: list[dict]):
        import aiohttp
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            "stream": True,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.host}/api/chat", json=payload, timeout=aiohttp.ClientTimeout(total=120)
            ) as resp:
                async for line in resp.content:
                    text = line.decode().strip()
                    if text:
                        try:
                            chunk = json.loads(text)
                            yield chunk.get("message", {}).get("content", "")
                        except json.JSONDecodeError:
                            pass

# ============================================================
# 后端 2：本地 Transformers 直接推理
# ============================================================
class DirectLLM:
    def __init__(self, model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch
        logger.info(f"加载模型 {model_name}（首次需下载 ~1GB，请耐心等待）...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            device_map="cpu",
            trust_remote_code=True,
        )
        logger.info("模型加载完成 ✓")

    async def chat(self, messages: list[dict]) -> str:
        # 构建对话格式
        prompt = self.tokenizer.apply_chat_template(
            [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer(prompt, return_tensors="pt")
        outputs = self.model.generate(
            **inputs,
            max_new_tokens=512,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
        )
        response = self.tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
        )
        return response.strip()

    async def chat_stream(self, messages: list[dict]):
        # 直接模式下不支持流式，返回完整结果
        result = await self.chat(messages)
        # 模拟流式分段输出
        for i in range(0, len(result), 4):
            yield result[i:i+4]
            await __import__('asyncio').sleep(0.05)


# ============================================================
# FastAPI 应用
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    global client
    if DIRECT_MODE:
        client = DirectLLM()
    else:
        client = OllamaClient(OLLAMA_HOST, OLLAMA_MODEL)
    yield
    client = None

app = FastAPI(title="苗绣·识裳 LLM", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
client = None


@app.get("/health")
async def health():
    return {"status": "ok", "mode": "direct" if DIRECT_MODE else "ollama"}


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
        "llm_latency": llm_latency.stats(),
        "llm_queue": llm_guard.stats(),
        "mode": "direct" if DIRECT_MODE else "ollama",
    }


@app.post("/chat")
async def chat(req: ChatRequest):
    """非流式对话"""
    global client
    if not client:
        raise HTTPException(status_code=503, detail="LLM 未就绪")
    if not req.messages:
        raise HTTPException(status_code=400, detail="消息不能为空")

    llm_guard.enter()
    t0 = time.perf_counter()
    try:
        await llm_guard.acquire()
        reply = await client.chat(req.messages)
        llm_latency.record(round((time.perf_counter() - t0) * 1000, 1))
        return JSONResponse(content={"role": "assistant", "content": reply})
    except RuntimeError as e:
        llm_guard.error()
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        llm_guard.error()
        logger.error(f"LLM 错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        llm_guard.release()
        llm_guard.exit()


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """流式对话（SSE）"""
    global client
    if not client:
        raise HTTPException(status_code=503, detail="LLM 未就绪")

    async def generate():
        try:
            async for chunk in client.chat_stream(req.messages):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ============================================================
if __name__ == "__main__":
    import uvicorn
    parser = ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--direct", action="store_true", help="使用本地 Transformers 直接推理")
    args = parser.parse_args()

    if args.direct:
        DIRECT_MODE = True
    logger.info(f"LLM 服务启动 ({'direct' if DIRECT_MODE else 'ollama'}) http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
