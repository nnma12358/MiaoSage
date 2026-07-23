#!/usr/bin/env python3
"""苗绣·识裳 — ASR 语音识别（x86_64 边缘优化 · faster-whisper）
========================================================
边缘优化: tiny 模型 (~75MB), int8 量化, beam_size=3 降延迟
"""
import os, tempfile, subprocess, logging
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("asr-edge")

MODEL_SIZE = os.environ.get("WHISPER_MODEL", "tiny")
DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")


class ASREngine:
    def __init__(self):
        from faster_whisper import WhisperModel
        logger.info(f"加载 Whisper 模型: {MODEL_SIZE} (device={DEVICE}, compute={COMPUTE_TYPE}) ...")
        self._model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        logger.info("ASR 模型就绪 ✓")

    def transcribe(self, audio_path: str) -> str:
        segments, info = self._model.transcribe(audio_path, beam_size=3, language="zh")
        text = " ".join(seg.text.strip() for seg in segments)
        logger.info(f"ASR 结果 (lang={info.language}): {text[:60]}...")
        return text


app = FastAPI(title="ASR Edge Service (x86)")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

engine = None


@app.on_event("startup")
def startup():
    global engine
    engine = ASREngine()
    logger.info("ASR 边缘服务就绪")


@app.get("/health")
def health():
    return {"status": "ok", "backend": "faster-whisper", "model": MODEL_SIZE}


@app.post("/asr")
async def transcribe(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(await audio.read())
        raw_path = f.name

    def _is_wav(path):
        with open(path, 'rb') as f:
            return f.read(4) == b'RIFF'

    if _is_wav(raw_path):
        audio_path = raw_path
    else:
        wav_fd, wav_path = tempfile.mkstemp(suffix='.wav')
        os.close(wav_fd)
        try:
            subprocess.run(['ffmpeg', '-i', raw_path, '-acodec', 'pcm_s16le',
                '-ar', '16000', '-ac', '1', '-y', wav_path],
                check=True, capture_output=True, timeout=30)
        except Exception as e:
            os.unlink(raw_path)
            raise HTTPException(400, f"音频转码失败: {e}")
        os.unlink(raw_path)
        audio_path = wav_path

    try:
        text = engine.transcribe(audio_path)
        return {"success": True, "text": text}
    except Exception as e:
        raise HTTPException(500, f"ASR 推理失败: {e}")
    finally:
        try:
            os.unlink(audio_path)
        except OSError:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
