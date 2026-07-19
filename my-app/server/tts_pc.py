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
import os, sys, logging, tempfile, asyncio, concurrent.futures, io, wave, struct, re, json
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
TTS_MAX_LEN  = int(os.environ.get("TTS_MAX_LEN", "800"))

# 模型缓存目录（挂载卷可复用）
MODEL_DIR = Path(os.environ.get("MELO_MODEL_DIR", "/app/models"))
MODEL_DIR.mkdir(parents=True, exist_ok=True)
os.environ["MELO_DIR"] = str(MODEL_DIR)

_thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def _normalize_tts_text(text: str) -> str:
    """归一化 TTS 输入文本，清除 MeloTTS 无法发音的特殊字符。

    MeloTTS / VITS 对以下字符可能静默跳过，导致"片段文字丢失"：
      - 《》〈〉「」『』【】〖〗（书名号、括号类）
      - … ‥ （省略号）
      - — – （破折号）
      - ～ 〜 （波浪线）
      - ；：！？ （全角标点 — MeloTTS 无法处理，静默跳过整段）
      - 〝 〞 （着重号）
      - 全角英文字母／数字（归一化为半角）
    """
    # 1. 全角标点 → 逗号（；：会导致 MeloTTS 静默跳过后续整段文字）
    text = re.sub(r'[;；]', '\uff0c', text)   # 分号 → 逗号
    text = re.sub(r'[:：]', '\uff0c', text)   # 冒号 → 逗号
    # 2. 书名号、括号类 → 删除（保留内部文字）
    text = re.sub(r'[《》〈〉「」『』【】〖〗〝〞]', '', text)
    # 3. 省略号 → 句号
    text = re.sub(r'[…‥]', '\u3002', text)
    # 4. 破折号、波浪线 → 逗号
    text = re.sub(r'[—–～〜]', '\uff0c', text)
    # 5. 全角英文字母 → 半角（MeloTTS 对全角英文支持不稳定）
    text = re.sub(r'[Ａ-Ｚ]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
    text = re.sub(r'[ａ-ｚ]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
    # 6. 全角数字 → 半角
    text = re.sub(r'[０-９]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
    # 7. 连续标点去重（超过2个相同标点 → 保留1个）
    text = re.sub(r'([\u3002\uff0c\uff01\uff1f\u3001])\1{2,}', r'\1', text)
    # 8. 清理不可见控制字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    return text


def _trim_wav_leading_silence(wav_bytes: bytes, max_trim_sec: float = 0.20,
                               silence_threshold: int = 50) -> bytes:
    """裁剪 WAV 开头纯静音（仅去除数字零值附近的真正静音帧）。

    策略：从第 0 帧开始扫描，跳过所有幅度 < threshold 的采样点，
    但最多只裁剪 max_trim_sec 秒（防止误删正常低音量语音）。
    阈值降低至 120，避免误切中文辅音（如 l-/m-/n- 声母）。
    """
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
            params = wf.getparams()
            nchannels = params.nchannels
            sampwidth = params.sampwidth
            framerate = params.framerate
            total_frames = wf.getnframes()
            raw = wf.readframes(total_frames)
    except Exception:
        return wav_bytes  # 无法解析，原样返回

    # 将原始字节解析为采样点绝对值列表（取多声道平均）
    if sampwidth == 2:
        fmt = f"<{total_frames * nchannels}h"
        samples = list(struct.unpack(fmt, raw))
    elif sampwidth == 4:
        fmt = f"<{total_frames * nchannels}i"
        samples = list(struct.unpack(fmt, raw))
    else:
        return wav_bytes

    # 每帧取各声道绝对值的平均值
    frame_amps = []
    for i in range(total_frames):
        frame_samples = samples[i * nchannels : (i + 1) * nchannels]
        amp = sum(abs(s) for s in frame_samples) / nchannels
        frame_amps.append(amp)

    # 找到第一个幅度超过阈值的帧
    max_trim_frames = int(max_trim_sec * framerate)
    trim_frames = 0
    found_signal = False
    for i, amp in enumerate(frame_amps):
        if i >= max_trim_frames:
            break
        if amp >= silence_threshold:
            trim_frames = i
            found_signal = True
            break

    if not found_signal:
        # 未找到超过阈值的帧 → 音频整体较柔和，不做裁剪以免误删
        logger.info(f"WAV silence trim: audio is soft throughout, skipping trim "
                    f"(max_amp_in_window={max(frame_amps[:max_trim_frames]) if frame_amps else 0:.0f})")
        return wav_bytes

    if trim_frames <= 0:
        logger.info(f"WAV silence trim: no leading silence detected (threshold={silence_threshold})")
        return wav_bytes  # 无需裁剪

    # 安全回退 2 帧（避免削到辅音起音）
    trim_frames = max(0, trim_frames - 2)

    bytes_per_frame = sampwidth * nchannels
    trimmed_raw = raw[trim_frames * bytes_per_frame:]

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf_out:
        wf_out.setparams(params)
        wf_out.setnframes(total_frames - trim_frames)
        wf_out.writeframes(trimmed_raw)

    trimmed = buf.getvalue()
    logger.info(f"WAV silence trimmed: {trim_frames} frames "
                f"({trim_frames / framerate * 1000:.0f} ms) "
                f"from {len(wav_bytes)} -> {len(trimmed)} bytes")
    return trimmed


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

        # 归一化文本：清除 MeloTTS 无法发音的特殊字符
        text = _normalize_tts_text(text)
        if not text.strip():
            raise ValueError("text empty after normalization")

        # 短文本补齐：MeloTTS 对极短文本（< 6 字）可能静音
        MIN_TTS_LEN = 6
        if len(text) < MIN_TTS_LEN:
            pad_needed = MIN_TTS_LEN - len(text)
            text = text + "。" * pad_needed
            logger.info(f"Text padded to {MIN_TTS_LEN} chars (was {len(text) - pad_needed})")

        if len(text) > TTS_MAX_LEN:
            # 按句子边界截断，避免切在逗号中间导致后半句丢失
            truncated = text[:TTS_MAX_LEN]
            # 在最后一个句号/问号/感叹号处截断
            last_period = max(
                truncated.rfind('\u3002'),  # 。
                truncated.rfind('\uff0c'),  # ，
                truncated.rfind('\uff01'),  # ！
                truncated.rfind('\uff1f'),  # ？
            )
            if last_period > TTS_MAX_LEN * 0.6:  # 至少保留60%长度
                text = truncated[:last_period + 1]
                logger.info(f"Text truncated at sentence boundary ({len(text)} chars)")
            else:
                text = truncated
                logger.warning(f"Text hard-truncated ({len(text)} -> {TTS_MAX_LEN})")

        logger.info(f"TTS [MeloTTS] len={len(text)}: {text[:60]}...")

        loop = asyncio.get_running_loop()
        out_path = await loop.run_in_executor(_thread_pool, self._synthesize_sync, text)

        # 仅裁剪开头纯静音（阈值极低 50，最大 0.2s，不依赖 warmup）
        try:
            with open(out_path, "rb") as f:
                raw = f.read()
            trimmed = _trim_wav_leading_silence(raw)
            with open(out_path, "wb") as f:
                f.write(trimmed)

            # 音频静音检测：若输出近乎全静音，记录警告便于排查
            wav_samples = trimmed[44:]  # 跳过 WAV 头
            if len(wav_samples) >= 100:
                max_amp = max(abs(int.from_bytes(wav_samples[i:i+2], 'little', signed=True))
                              for i in range(0, len(wav_samples) - 1, 2))
                if max_amp < 100:
                    logger.warning(f"TTS output is near-silent! max_amp={max_amp}, "
                                   f"text_len={len(text)}, text={repr(text[:50])}")
        except Exception as e:
            logger.warning(f"Silence trim skipped: {e}")

        return out_path

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
    # ---- 传输链路诊断：记录原始请求 ----
    raw_body = await request.body()
    logger.info(f"TTS request: {len(raw_body)} bytes, "
                f"first 80 bytes hex: {raw_body[:80].hex() if raw_body else 'EMPTY'}")
    try:
        body = json.loads(raw_body.decode('utf-8'))
    except Exception as e:
        logger.error(f"TTS JSON parse failed: {e}")
        raise HTTPException(400, f"invalid JSON: {e}")

    text = (body.get("text", "") or "").strip()
    if not text:
        raise HTTPException(400, "text is empty")

    # 传输诊断：记录文本关键信息
    _last10 = repr(text[-10:]) if len(text) >= 10 else repr(text)
    _has_cjk = bool(re.search(r'[\u4e00-\u9fff]', text))
    logger.info(f"TTS text: len={len(text)} chars, "
                f"has_cjk={_has_cjk}, "
                f"first_20={repr(text[:20])}, "
                f"last_10={_last10}")

    try:
        audio_path = await engine.synthesize(text)

        # 读取音频并检测静音
        with open(audio_path, "rb") as f:
            audio_bytes = f.read()
        try:
            os.unlink(audio_path)
        except OSError:
            pass

        # 静音检测：若输出近乎全静音，补齐文本重试一次
        wav_data = audio_bytes[44:]  # 跳过 WAV 头
        if len(wav_data) >= 100:
            max_amp = max(abs(int.from_bytes(wav_data[i:i+2], 'little', signed=True))
                          for i in range(0, len(wav_data) - 1, 2))
            if max_amp < 100 and len(text) < 120:
                logger.warning(f"TTS silent (max_amp={max_amp}), retrying with padded text")
                # 补齐上下文到 120+ 字（已知阈值），用无害填充句
                pad_sentence = "。这是苗族文化的重要组成部分，值得深入研究和传承。"
                retry_text = text
                while len(retry_text) < 120:
                    retry_text += pad_sentence
                audio_path2 = await engine.synthesize(retry_text)
                with open(audio_path2, "rb") as f:
                    audio_bytes = f.read()
                try:
                    os.unlink(audio_path2)
                except OSError:
                    pass
                logger.info(f"TTS retry: {len(text)} -> {len(retry_text)} chars, {len(audio_bytes)} bytes")

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
