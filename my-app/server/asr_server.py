#!/usr/bin/env python3
"""苗绣·识裳 — ASR 语音识别微服务"""
import os, sys, tempfile, subprocess, logging
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("asr-server")

NLP_DIR = os.environ.get("SPACEMIT_NLP_DIR", "/opt/spacemit/nlp")
if NLP_DIR not in sys.path:
    sys.path.insert(0, NLP_DIR)

class ASREngine:
    def __init__(self):
        from spacemit_asr import ASRModel
        from spacemit_asr.models.postprocess_utils import rich_transcription_postprocess
        self._postprocess = rich_transcription_postprocess
        logger.info("加载 ASR 模型...")
        self._model = ASRModel()
        logger.info("ASR 模型就绪")

    def transcribe(self, audio_path: str) -> str:
        result = self._model.generate(audio_path)
        if isinstance(result, list) and result:
            raw = result[0]
            raw_text = raw[0] if isinstance(raw, list) else raw
        elif isinstance(result, str):
            raw_text = result
        else:
            raw_text = str(result)
        return self._postprocess(raw_text)

app = FastAPI(title="ASR Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

engine = None

@app.on_event("startup")
def startup():
    global engine
    engine = ASREngine()
    logger.info("ASR 服务就绪")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/asr")
async def transcribe(audio: UploadFile = File(...)):
    # 保存为临时文件
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(await audio.read())
        raw_path = f.name

    # 检查是否有效 WAV
    def _is_wav(path):
        with open(path, 'rb') as f:
            return f.read(4) == b'RIFF'

    if _is_wav(raw_path):
        audio_path = raw_path
        need_cleanup = True
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
        need_cleanup = True

    try:
        text = engine.transcribe(audio_path)
        return {"success": True, "text": text}
    except Exception as e:
        raise HTTPException(500, f"ASR 推理失败: {e}")
    finally:
        if need_cleanup:
            try: os.unlink(audio_path)
            except OSError: pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
