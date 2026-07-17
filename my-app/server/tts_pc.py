#!/usr/bin/env python3
"""
苗绣·识裳 — TTS 语音合成（PC 端 · MeloTTS 容器化）
========================================================
MeloTTS: 开源高音质中文 TTS，本地推理，无需联网。
  - 默认中文女声 (ZH, speaker_id=0)
  - CPU 推理，无需 GPU
  - 自动下载模型到 /app/models（首次启动）

环境变量：
  TTS_LANGUAGE=ZH         # 语言代码
  TTS_SPEAKER=0           # 说话人 ID
  TTS_SPEED=1.0           # 语速 (0.5-2.0)
  TTS_MAX_LEN=300         # 最大文本长度
"""
import os, sys, logging, tempfile, asyncio, concurrent.futures
from pathlib import Path

# 确保 torch/torchaudio 共享库可被加载
_torch_lib = Path(__file__).resolve().parent / ".torch_libs"
# 在容器中 torch 库位于 site-packages/torch/lib/
import site
for _sp in site.getsitepackages():
    _candidate = Path(_sp) / "torch" / "lib"
    if _candidate.is_dir():
        os.environ.setdefault("LD_LIBRARY_PATH", "")
        if str(_candidate) not in os.environ["LD_LIBRARY_PATH"]:
            os.environ["LD_LIBRARY_PATH"] = str(_candidate) + ":" + os.environ["LD_LIBRARY_PATH"]
        break

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tts-melo")


def _detect_device() -> str:
    """自动检测最优推理设备：CUDA > MPS > CPU"""
    try:
        import torch
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            logger.info(f"GPU detected: {gpu_name} (CUDA)")
            return "cuda"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            logger.info("GPU detected: Apple MPS")
            return "mps"
    except ImportError:
        logger.info("torch not installed, falling back to CPU")
    except Exception as e:
        logger.warning(f"GPU detection failed ({e}), falling back to CPU")
    logger.info("No GPU detected, using CPU")
    return "cpu"

# ---- 配置 ----
TTS_LANGUAGE = os.environ.get("TTS_LANGUAGE", "ZH")
TTS_SPEAKER  = int(os.environ.get("TTS_SPEAKER", "0"))
TTS_SPEED    = float(os.environ.get("TTS_SPEED", "1.0"))
TTS_MAX_LEN  = int(os.environ.get("TTS_MAX_LEN", "300"))

# 模型缓存目录（挂载卷可复用）
MODEL_DIR = Path(os.environ.get("MELO_MODEL_DIR", "/app/models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)
os.environ["MELO_DIR"] = str(MODEL_DIR)

_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)


class MeloTTS:
    """MeloTTS 封装 — 惰性加载、线程安全、自动 GPU 检测"""

    def __init__(self):
        self._model = None
        self._device = _detect_device()
        self._tmp_dir = tempfile.gettempdir()
        logger.info(f"MeloTTS init: lang={TTS_LANGUAGE} speaker={TTS_SPEAKER} speed={TTS_SPEED} device={self._device}")

    def _load_model(self):
        """惰性加载 MeloTTS 模型（首次推理触发，含自动下载）"""
        if self._model is not None:
            return
        logger.info(f"Loading MeloTTS model (lang={TTS_LANGUAGE}, device={self._device})...")
        from melo.api import TTS
        self._model = TTS(language=TTS_LANGUAGE, device=self._device)
        try:
            n_speakers = self._model.hps.data.n_speakers if hasattr(self._model, 'hps') else '?'
        except Exception:
            n_speakers = '?'
        logger.info(f"MeloTTS model loaded (device={self._device}, speakers={n_speakers})")

    async def synthesize(self, text: str) -> str:
        """异步合成入口，返回 WAV 文件路径"""
        text = text.strip()
        if not text:
            raise ValueError("text is empty")

        if len(text) > TTS_MAX_LEN:
            logger.warning(f"Text truncated ({len(text)} -> {TTS_MAX_LEN})")
            text = text[:TTS_MAX_LEN]

        logger.info(f"TTS [MeloTTS] len={len(text)}: {text[:60]}...")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(_thread_pool, self._synthesize_sync, text)

    def _synthesize_sync(self, text: str) -> str:
        """同步合成（在线程池中运行，避免阻塞事件循环）"""
        self._load_model()

        out_path = os.path.join(
            self._tmp_dir,
            f"tts_melo_{os.getpid()}_{hash(text) & 0x7FFFFFFF}.wav"
        )

        # MeloTTS API: tts_to_file(text, speaker_id, output_path, speed=1.0)
        self._model.tts_to_file(
            text=text,
            speaker_id=TTS_SPEAKER,
            output_path=out_path,
            speed=TTS_SPEED,
        )

        size_kb = os.path.getsize(out_path) / 1024
        logger.info(f"MeloTTS done: {out_path} ({size_kb:.1f} KB)")
        return out_path


# ---- FastAPI ----
app = FastAPI(title="TTS MeloTTS Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

engine: MeloTTS = None


@app.on_event("startup")
async def startup():
    global engine
    engine = MeloTTS()
    # 预热：触发模型下载 + 首次推理
    try:
        logger.info("MeloTTS warmup...")
        await engine.synthesize("预热")
        logger.info("MeloTTS warmup done")
    except Exception as e:
        logger.warning(f"MeloTTS warmup skipped: {e}")
    logger.info("TTS MeloTTS Service ready")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "backend": "melotts",
        "language": TTS_LANGUAGE,
        "speaker": TTS_SPEAKER,
        "speed": TTS_SPEED,
        "device": engine._device if engine else "unknown",
    }


@app.post("/tts")
async def synthesize(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "invalid JSON")

    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(400, "text is empty")

    try:
        audio_path = await engine.synthesize(text)

        # 读取全部音频字节后立即删除临时文件，避免 FileResponse 后台清理截断问题
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        try:
            os.unlink(audio_path)
        except OSError:
            pass

        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Content-Disposition": "inline; filename=speech.wav"},
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("TTS synthesis failed")
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="info")
