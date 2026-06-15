#!/usr/bin/env python3
"""苗绣·识裳 — TTS 语音合成微服务"""
import os, sys, logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tts-server")

NLP_DIR = os.environ.get("SPACEMIT_NLP_DIR", "/opt/spacemit/nlp")
if NLP_DIR not in sys.path:
    sys.path.insert(0, NLP_DIR)

class TTSEngine:
    def __init__(self):
        from spacemit_tts import TTSModel
        logger.info("加载 TTS 模型...")
        self._model = TTSModel()
        logger.info("TTS 模型就绪")

    def synthesize(self, text: str) -> str:
        """返回生成的音频文件路径"""
        return self._model.ort_predict(text[:500])

app = FastAPI(title="TTS Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

engine = None

@app.on_event("startup")
def startup():
    global engine
    engine = TTSEngine()
    logger.info("TTS 服务就绪")

@app.get("/health")
def health():
    return {"status": "ok"}

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
        return FileResponse(audio_path, media_type="audio/wav", filename="speech.wav")
    except Exception as e:
        raise HTTPException(500, str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
