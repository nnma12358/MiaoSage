#!/usr/bin/env python3
"""
苗绣·识裳 — TTS 语音合成（PC 端 · 轻量化）
========================================================
默认使用 edge-tts（微软免费 TTS，无需模型下载，中文音质优秀）。
可通过环境变量切换后端：
  TTS_BACKEND=edge-tts    (默认，需联网)
  TTS_BACKEND=piper        (离线，需下载语音模型)

edge-tts 中文推荐音色：
  zh-CN-XiaoxiaoNeural   — 女声，甜美自然（默认）
  zh-CN-YunxiNeural      — 男声，温润
  zh-CN-XiaoyiNeural     — 女声，活泼
"""
import os, sys, logging, tempfile, asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tts-pc")

# ---- 配置 ----
TTS_BACKEND = os.environ.get("TTS_BACKEND", "edge-tts")
TTS_VOICE = os.environ.get("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
TTS_RATE = os.environ.get("TTS_RATE", "+0%")    # 语速调整
TTS_MAX_LEN = int(os.environ.get("TTS_MAX_LEN", "300"))  # PC 端可处理更长文本


class TTSEngine:
    """统一 TTS 接口，根据 TTS_BACKEND 选择实现"""

    def __init__(self):
        self._backend = TTS_BACKEND
        self._tmp_dir = tempfile.gettempdir()
        os.makedirs(self._tmp_dir, exist_ok=True)
        logger.info(f"TTS 后端: {self._backend}, 音色: {TTS_VOICE}")

    def synthesize(self, text: str) -> str:
        text = text.strip()
        if not text:
            raise ValueError("文本为空")

        if len(text) > TTS_MAX_LEN:
            logger.warning(f"文本过长 ({len(text)} → {TTS_MAX_LEN})，已截断")
            text = text[:TTS_MAX_LEN]

        logger.info(f"TTS 合成 (len={len(text)}): {text[:50]}...")

        if self._backend == "edge-tts":
            return asyncio.run(self._synthesize_edge(text))
        elif self._backend == "piper":
            return self._synthesize_piper(text)
        else:
            raise ValueError(f"未知 TTS 后端: {self._backend}")

    async def _synthesize_edge(self, text: str) -> str:
        """edge-tts: 微软免费 TTS，音质极佳（需联网）"""
        import edge_tts

        out_path = os.path.join(self._tmp_dir, f"tts_{os.getpid()}_{hash(text) & 0x7FFFFFFF}.mp3")
        communicate = edge_tts.Communicate(text, TTS_VOICE, rate=TTS_RATE)
        await communicate.save(out_path)

        size_kb = os.path.getsize(out_path) / 1024
        logger.info(f"edge-tts 合成完成: {out_path} ({size_kb:.1f} KB)")
        return out_path

    def _synthesize_piper(self, text: str) -> str:
        """Piper TTS: 离线轻量 TTS（需预下载模型）"""
        import subprocess

        # Piper 模型路径（通过环境变量配置）
        piper_model = os.environ.get("PIPER_MODEL", "/opt/piper/zh_CN-huayan-medium.onnx")
        piper_config = os.environ.get("PIPER_CONFIG", "/opt/piper/zh_CN-huayan-medium.onnx.json")

        out_path = os.path.join(self._tmp_dir, f"tts_{os.getpid()}_{hash(text) & 0x7FFFFFFF}.wav")

        result = subprocess.run(
            ["piper", "-m", piper_model, "-c", piper_config,
             "-f", out_path, "--output-raw"],
            input=text.encode("utf-8"),
            capture_output=True, timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Piper TTS 失败: {result.stderr.decode()}")

        # Piper --output-raw 生成 raw 16-bit 16kHz PCM，需转 WAV 头
        wav_out = out_path + ".wav"
        subprocess.run([
            "ffmpeg", "-y",
            "-f", "s16le", "-ar", "22050", "-ac", "1",
            "-i", out_path, wav_out
        ], check=True, capture_output=True, timeout=10)
        os.unlink(out_path)

        size_kb = os.path.getsize(wav_out) / 1024
        logger.info(f"Piper TTS 合成完成: {wav_out} ({size_kb:.1f} KB)")
        return wav_out


# ---- FastAPI ----
app = FastAPI(title="TTS PC Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

engine: TTSEngine = None


@app.on_event("startup")
def startup():
    global engine
    engine = TTSEngine()
    # 预热
    try:
        if TTS_BACKEND == "piper":
            engine.synthesize("预热")
            logger.info("TTS 预热完成 ✓")
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
        audio_path = engine.synthesize(text)

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
