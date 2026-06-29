#!/usr/bin/env python3
"""苗绣·识裳 — TTS 语音合成微服务"""
import os, sys, logging, traceback, tempfile, gc
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
        self._tmp_dir = tempfile.gettempdir()
        os.makedirs(self._tmp_dir, exist_ok=True)
        logger.info("TTS 模型就绪")

    def synthesize(self, text: str) -> str:
        text = text.strip()
        if not text:
            raise ValueError("文本为空")

        try:
            mem_line = os.popen("free -m 2>/dev/null | grep Mem").read().strip()
            if mem_line:
                logger.info(f"合成前内存: {mem_line}")
        except Exception:
            pass

        logger.info(f"TTS 合成开始 (len={len(text)}): {text[:50]}...")

        # 截断过长文本，避免 ONNX 推理 OOM
        max_len = 200
        if len(text) > max_len:
            logger.warning(f"文本过长 ({len(text)} → {max_len})，已截断")
            text = text[:max_len]

        try:
            import psutil
            mem_before = psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
            logger.info(f"进程内存(合成前): {mem_before:.1f} MB")
        except ImportError:
            pass

        gc.collect()
        try:
            result = self._model.ort_predict(text)
        except Exception as e:
            logger.error(f"ort_predict 失败: {e}")
            logger.error(traceback.format_exc())
            raise RuntimeError(f"TTS 推理失败: {e}")

        if not result or not os.path.exists(result):
            raise RuntimeError(f"TTS 输出文件缺失: {result}")
        size_kb = os.path.getsize(result) / 1024
        if size_kb < 1:
            raise RuntimeError(f"TTS 音频文件异常 ({size_kb:.1f} KB): {result}")

        logger.info(f"TTS 合成完成: {result} ({size_kb:.1f} KB)")
        return result


app = FastAPI(title="TTS Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

engine = None


@app.on_event("startup")
def startup():
    global engine
    engine = TTSEngine()
    logger.info("预热 TTS 语言模块（首次较慢）...")
    try:
        engine.synthesize("预热")
        logger.info("TTS 预热完成 ✓")
    except Exception as e:
        logger.error(f"TTS 预热失败: {e}")
        logger.error(traceback.format_exc())
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
        async def cleanup():
            try:
                if os.path.exists(audio_path):
                    os.unlink(audio_path)
            except OSError:
                pass
        return FileResponse(
            audio_path, media_type="audio/wav",
            filename="speech.wav",
            background=cleanup,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except RuntimeError as e:
        raise HTTPException(500, str(e))
    except Exception as e:
        logger.error(f"TTS 未知错误: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(500, f"TTS 服务内部错误: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
