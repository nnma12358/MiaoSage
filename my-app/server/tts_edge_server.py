#!/usr/bin/env python3
"""苗绣·识裳 — TTS 语音合成（x86_64 边缘优化 · edge-tts）
========================================================
边缘优化: 纯 Python ~100MB，调用微软免费 TTS API
对比 MeloTTS (~2GB PyTorch)，释放内存给 YOLO + LLM
"""
import os, tempfile, logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tts-edge")

VOICE = os.environ.get("TTS_VOICE", "zh-CN-XiaoxiaoNeural")
RATE = os.environ.get("TTS_RATE", "+0%")


class TTSEngine:
    def __init__(self):
        import edge_tts
        self._communicate = edge_tts.Communicate
        self._tmp_dir = tempfile.gettempdir()
        os.makedirs(self._tmp_dir, exist_ok=True)
        logger.info(f"TTS 引擎就绪 (voice={VOICE})")

    async def synthesize(self, text: str) -> str:
        text = text.strip()
        if not text:
            raise ValueError("文本为空")
        max_len = 300
        if len(text) > max_len:
            text = text[:max_len]
        output = os.path.join(self._tmp_dir, f"tts_{os.getpid()}_{hash(text) & 0x7FFFFFFF}.mp3")
        try:
            comm = self._communicate(text, VOICE, rate=RATE)
            await comm.save(output)
            size_kb = os.path.getsize(output) / 1024
            logger.info(f"TTS 合成完成: {size_kb:.1f} KB")
            return output
        except Exception as e:
            logger.error(f"TTS 合成失败: {e}")
            raise RuntimeError(f"TTS 合成失败: {e}")


app = FastAPI(title="TTS Edge Service (x86)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

engine = None


@app.on_event("startup")
def startup():
    global engine
    engine = TTSEngine()
    logger.info("TTS 边缘服务就绪")


@app.get("/health")
def health():
    return {"status": "ok", "backend": "edge-tts", "voice": VOICE}


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
        audio_path = await engine.synthesize(text)

        async def cleanup():
            try:
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
            except OSError:
                pass

        return FileResponse(
            audio_path, media_type="audio/mpeg",
            filename="speech.mp3",
            background=cleanup,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
