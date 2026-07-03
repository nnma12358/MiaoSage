#!/usr/bin/env python3
"""
苗绣·识裳 — ASR 语音识别（PC 端 · 轻量化 Whisper）
========================================================
使用 faster-whisper (CTranslate2 后端)，比 openai-whisper 快 4 倍、省一半内存。
默认使用 tiny 模型（~1GB 显存/内存），适合 CPU 实时推理。

首次启动会自动下载模型到 ~/.cache/huggingface/。
"""
import os, sys, tempfile, logging, subprocess
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("asr-whisper")

# ---- 配置 ----
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "tiny")  # tiny / base / small
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")  # cpu / cuda
WHISPER_COMPUTE = os.environ.get("WHISPER_COMPUTE", "int8")  # int8 / float16
WHISPER_LANG = os.environ.get("WHISPER_LANG", "zh")  # 默认中文

# ---- Whisper 引擎 ----
class WhisperEngine:
    def __init__(self):
        from faster_whisper import WhisperModel
        logger.info(f"加载 Whisper 模型: {WHISPER_MODEL} (device={WHISPER_DEVICE}, compute={WHISPER_COMPUTE})")
        self._model = WhisperModel(
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE,
            cpu_threads=int(os.environ.get("OMP_NUM_THREADS", "4")),
            num_workers=1,
        )
        logger.info("Whisper 模型就绪 ✓")

    def transcribe(self, audio_path: str, language: str = None) -> dict:
        lang = language or WHISPER_LANG
        segments, info = self._model.transcribe(
            audio_path,
            language=lang,
            beam_size=3,
            vad_filter=True,          # 静音过滤，减少误识别
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
            without_timestamps=True,   # PC 端只取纯文本
        )
        text = " ".join(s.text.strip() for s in segments)
        return {
            "text": text,
            "language": info.language,
            "duration_s": round(info.duration, 1),
        }


# ---- FastAPI ----
app = FastAPI(title="ASR Whisper Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

engine: WhisperEngine = None


@app.on_event("startup")
def startup():
    global engine
    engine = WhisperEngine()
    # 预热
    try:
        import numpy as np
        import soundfile as sf
        fd, tmp = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        dummy = np.zeros((16000,), dtype=np.float32)
        sf.write(tmp, dummy, 16000)
        engine.transcribe(tmp)
        os.unlink(tmp)
        logger.info("Whisper 预热完成 ✓")
    except Exception as e:
        logger.warning(f"预热跳过: {e}")


@app.get("/health")
def health():
    return {"status": "ok", "model": WHISPER_MODEL, "device": WHISPER_DEVICE}


@app.post("/asr")
async def transcribe(audio: UploadFile = File(...)):
    # 1. 保存上传音频
    suffix = ".wav"
    if audio.filename and audio.filename.endswith(".webm"):
        suffix = ".webm"
    fd, raw_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    with open(raw_path, "wb") as f:
        f.write(await audio.read())

    # 2. 非 WAV 格式 → 转码为 16kHz mono WAV
    wav_path = raw_path
    need_cleanup = [raw_path]
    if not suffix.endswith(".wav"):
        fd2, wav_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd2)
        need_cleanup.append(wav_path)
        try:
            subprocess.run([
                "sox", raw_path,
                "-r", "16000", "-c", "1", "-b", "16",
                wav_path
            ], check=True, capture_output=True, timeout=30)
        except subprocess.CalledProcessError as e:
            for p in need_cleanup:
                try: os.unlink(p)
                except OSError: pass
            raise HTTPException(400, f"音频转码失败: {e.stderr.decode()[:200]}")

    # 3. Whisper 推理
    try:
        result = engine.transcribe(wav_path)
        logger.info(f"ASR 完成: lang={result['language']}, dur={result['duration_s']}s, text={result['text'][:50]}...")
        return {"success": True, "text": result["text"], "language": result["language"]}
    except Exception as e:
        logger.error(f"Whisper 推理失败: {e}")
        raise HTTPException(500, f"ASR 推理失败: {e}")
    finally:
        for p in need_cleanup:
            try: os.unlink(p)
            except OSError: pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
