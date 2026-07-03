#!/usr/bin/env python3
"""
苗绣·识裳 — TTS 语音合成（PC 端 · edge-tts 轻量）
========================================================
默认 edge-tts（微软免费，纯 pip，音质最佳，中文自然）。
可选后端：
  TTS_BACKEND=edge-tts  (默认，需联网，纯 pip)
  TTS_BACKEND=piper     (离线高音质，需预下载 piper+模型)
  TTS_BACKEND=espeak    (离线，需 apt espeak-ng)
"""
import os, sys, logging, tempfile, asyncio, concurrent.futures
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tts-pc")

# ---- 配置 ----
TTS_BACKEND = os.environ.get("TTS_BACKEND", "edge-tts")
TTS_VOICE = os.environ.get("TTS_VOICE", "zh-CN-XiaoxiaoNeural")  # edge-tts 中文甜美女声
TTS_RATE = os.environ.get("TTS_RATE", "+0%")    # edge-tts 语速百分比 / piper length-scale / espeak wpm
TTS_MAX_LEN = int(os.environ.get("TTS_MAX_LEN", "300"))  # PC 端可处理更长文本

# 线程池用于运行同步代码（piper 后端）
_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class TTSEngine:
    """统一 TTS 接口，根据 TTS_BACKEND 选择实现"""

    def __init__(self):
        self._backend = TTS_BACKEND
        self._tmp_dir = tempfile.gettempdir()
        os.makedirs(self._tmp_dir, exist_ok=True)
        logger.info(f"TTS 后端: {self._backend}, 音色: {TTS_VOICE}")

    async def synthesize(self, text: str) -> str:
        """异步合成入口"""
        text = text.strip()
        if not text:
            raise ValueError("文本为空")

        if len(text) > TTS_MAX_LEN:
            logger.warning(f"文本过长 ({len(text)} → {TTS_MAX_LEN})，已截断")
            text = text[:TTS_MAX_LEN]

        logger.info(f"TTS 合成 [{self._backend}] (len={len(text)}): {text[:50]}...")

        if self._backend == "piper":
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(_thread_pool, self._synthesize_piper, text)
        elif self._backend == "espeak":
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(_thread_pool, self._synthesize_espeak, text)
        elif self._backend == "edge-tts":
            return await self._synthesize_edge(text)
        else:
            raise ValueError(f"未知 TTS 后端: {self._backend}")

    def _synthesize_espeak(self, text: str) -> str:
        """espeak-ng: 离线本地 TTS，支持中文，零模型 (~10MB)"""
        import subprocess
        out_path = os.path.join(self._tmp_dir, f"tts_{os.getpid()}_{hash(text) & 0x7FFFFFFF}.wav")
        # -v zh: 中文  -s speed: 语速 (80-450)  -w: 输出 WAV
        cmd = ["espeak-ng", "-v", TTS_VOICE, "-s", TTS_RATE, "-w", out_path, text]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode != 0:
            err = result.stderr.decode()
            raise RuntimeError(f"espeak-ng 失败: {err}")
        size_kb = os.path.getsize(out_path) / 1024
        logger.info(f"espeak-ng 合成完成: {out_path} ({size_kb:.1f} KB)")
        return out_path

    async def _synthesize_edge(self, text: str) -> str:
        """edge-tts: 微软免费 TTS，通过 CLI 子进程调用（隔离事件循环）"""
        import subprocess, json

        out_path = os.path.join(self._tmp_dir, f"tts_{os.getpid()}_{hash(text) & 0x7FFFFFFF}.mp3")
        voice = TTS_VOICE
        rate = TTS_RATE

        def _run():
            result = subprocess.run(
                ["edge-tts", "--voice", voice, "--rate", rate, "--text", text, "--write-media", out_path],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                raise RuntimeError(f"edge-tts CLI failed: {result.stderr[:200]}")
            return out_path

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(_thread_pool, _run)

        size_kb = os.path.getsize(result) / 1024
        logger.info(f"edge-tts 合成完成: {result} ({size_kb:.1f} KB)")
        return result

    def _synthesize_piper(self, text: str) -> str:
        """Piper TTS: 离线高音质中文（需预下载模型）"""
        import subprocess

        piper_model = os.environ.get("PIPER_MODEL", "/opt/piper/zh_CN-huayan-medium.onnx")
        piper_config = os.environ.get("PIPER_CONFIG", "/opt/piper/zh_CN-huayan-medium.onnx.json")

        out_path = os.path.join(self._tmp_dir, f"tts_{os.getpid()}_{hash(text) & 0x7FFFFFFF}.wav")

        # Piper 直接输出 WAV（--output_file 指定 .wav 即可，无需 ffmpeg）
        cmd = [
            "piper", "-m", piper_model, "-c", piper_config,
            "-f", out_path,
            "--length-scale", TTS_RATE,   # 语速 0.5-2.0
        ]
        result = subprocess.run(cmd, input=text.encode("utf-8"),
                                capture_output=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"Piper TTS 失败: {result.stderr.decode()}")

        size_kb = os.path.getsize(out_path) / 1024
        logger.info(f"Piper TTS 合成完成: {out_path} ({size_kb:.1f} KB)")
        return out_path


# ---- FastAPI ----
app = FastAPI(title="TTS PC Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

engine: TTSEngine = None


@app.on_event("startup")
async def startup():
    global engine
    engine = TTSEngine()
    # 预热（Piper 首次推理较慢）
    try:
        if TTS_BACKEND == "piper":
            await engine.synthesize("预热")
            logger.info("TTS Piper 预热完成 ✓")
    except Exception as e:
        logger.warning(f"TTS 预热跳过: {e}")
    logger.info("TTS PC 服务就绪 ✓")


@app.get("/health")
def health():
    return {"status": "ok", "backend": TTS_BACKEND, "voice": TTS_VOICE}


@app.post("/tts")
async def synthesize(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "无效 JSON")

    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "text 为空")

    try:
        logger.info(f"TTS request: text={repr(text[:80])}")
        audio_path = await engine.synthesize(text)

        # 根据后端决定 MIME 类型
        ext = os.path.splitext(audio_path)[1].lower()
        mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav"}
        media_type = mime_map.get(ext, "audio/wav")

        async def cleanup():
            try:
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
            except OSError:
                pass

        return FileResponse(
            audio_path,
            media_type=media_type,
            filename=f"speech{ext}",
            background=cleanup,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
