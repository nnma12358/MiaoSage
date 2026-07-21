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
import os, sys, logging, tempfile, asyncio, concurrent.futures, io, wave, struct, re, json, uuid, time
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

# ============================================================
# Monkey-patch: 阻止 MeCab 在导入时崩溃
# melo/text/japanese.py 在模块级别执行 MeCab.Tagger()，
# unidic 词典缺失会抛出 RuntimeError → 中文 TTS 也被连带崩溃。
# 中文 TTS 使用 jieba 分词，完全不依赖 MeCab/fugashi。
# ============================================================
import sys as _sys
import types as _types
if "MeCab" not in _sys.modules:
    _dummy_mecab = _types.ModuleType("MeCab")
    class _DummyTagger:
        def __init__(self, *args, **kwargs): pass
        def parse(self, text): return text
    _dummy_mecab.Tagger = _DummyTagger
    _sys.modules["MeCab"] = _dummy_mecab
    logger.info("MeCab monkey-patched (Chinese TTS does not require unidic)")
else:
    _sys.modules["MeCab"].Tagger = type("Tagger", (), {
        "__init__": lambda self, *a, **k: None,
        "parse": lambda self, text: text,
    })
    logger.info("MeCab Tagger forcefully replaced")

# ============================================================
# 拦截日语模块 — japanese.py 在模块级别调用 AutoTokenizer.from_pretrained()
# 会尝试下载 bert-base-japanese-v3，容器无法访问 HuggingFace。
# 用最小 stub 替换整个日语模块，阻止崩溃。
# ============================================================
_jp_stub = _types.ModuleType("melo.text.japanese")
_jp_stub.text_normalize = lambda t: t
_jp_stub.g2p = lambda t: ([], [], [])
_jp_stub.get_bert_feature = lambda *a, **k: None
def _distribute_phone(n_phone, n_word):
    phones_per_word = [0] * n_word
    for task in range(n_phone):
        min_tasks = min(phones_per_word)
        min_index = phones_per_word.index(min_tasks)
        phones_per_word[min_index] += 1
    return phones_per_word
_jp_stub.distribute_phone = _distribute_phone
_sys.modules["melo.text.japanese"] = _jp_stub
logger.info("Japanese text module stubbed")

# 英文 BERT 模型已预下载到容器 /root/.cache/huggingface/hub/
logger.info("BERT models preloaded from host (offline mode)")

# NLTK 禁用下载，使用预拷贝的 cmudict（从 MeloTTS 源码提供）
import nltk as _nltk
_nltk.data.path = ["/root/nltk_data"]
_nltk.download = lambda *a, **k: False
logger.info("NLTK configured (offline, cmudict preloaded)")

# ============================================================
# 打桩英文文本模块 — 中文 TTS 完全不依赖 NLTK/cmudict
# 但 MeloTTS 在导入时会遍历所有语言模块，触发 nltk.corpus.cmudict
# 查找。打桩阻止此查找，避免无网络环境下的 LookupError 崩溃。
# ============================================================
_en_stub = _types.ModuleType("melo.text.english")
_en_stub.text_normalize = lambda t: t
_en_stub.g2p = lambda t: ([], [], [])
_en_stub.get_bert_feature = lambda *a, **k: None
_en_stub.distribute_phone = _distribute_phone
_sys.modules["melo.text.english"] = _en_stub
logger.info("English text module stubbed (Chinese TTS does not need NLTK/cmudict)")

# 打桩韩文/法文模块 — 阻止 HuggingFace BERT 下载超时
_kr_stub = _types.ModuleType("melo.text.korean")
_kr_stub.text_normalize = lambda t: t
_kr_stub.g2p = lambda t: ([], [], [])
_kr_stub.get_bert_feature = lambda *a, **k: None
_kr_stub.distribute_phone = _distribute_phone
_sys.modules["melo.text.korean"] = _kr_stub
logger.info("Korean text module stubbed")

_fr_stub = _types.ModuleType("melo.text.french")
_fr_stub.text_normalize = lambda t: t
_fr_stub.g2p = lambda t: ([], [], [])
_fr_stub.get_bert_feature = lambda *a, **k: None
_fr_stub.distribute_phone = _distribute_phone
_sys.modules["melo.text.french"] = _fr_stub
logger.info("French text module stubbed")

# 强制离线防止 MeloTTS init 时触发 HuggingFace 下载
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


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

    MeloTTS chinese.py 的 rep_map 仅映射了约 20 个标点符号。
    任何不在 rep_map 中的字符（如 markdown **, /, `, - 列表标记）
    会被 pypinyin 处理时产生空音素 → 整段静音。

    本函数在文本进入 MeloTTS 之前做彻底清理。
    """
    # 1. Markdown 格式清理（必须在标点处理之前）
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)   # **粗体** → 粗体
    text = re.sub(r'\*(.+?)\*', r'\1', text)        # *斜体* → 斜体
    text = re.sub(r'`(.+?)`', r'\1', text)           # `代码` → 代码
    text = re.sub(r'~~(.+?)~~', r'\1', text)         # ~~删除线~~ → 删除线
    # 2. 列表标记 → 删除（编号列表、无序列表）
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)   # - * + 列表
    text = re.sub(r'^\s*\d+[\.\、\)]\s*', '', text, flags=re.MULTILINE)  # 1. 2、3) 编号
    # 3. 特殊符号 → 中文连接词
    text = text.replace('/', '或')     # 腰带/裤 → 腰带或裤
    text = text.replace('\\', '或')    # 反斜杠
    text = re.sub(r'[*#_~|]', '', text)  # 残留 markdown 符号 → 删除
    # 4. 箭头、特殊符号 → 删除
    text = re.sub(r'[→←↑↓↔⇒⇐⇑⇓➔➤▶▷◀◁●○◆◇■□▲△▼▽✓✗]', '', text)
    # 5. 全角标点 → 逗号（；：会导致 MeloTTS 静默跳过后续整段文字）
    text = re.sub(r'[;；]', '\uff0c', text)   # 分号 → 逗号
    text = re.sub(r'[:：]', '\uff0c', text)   # 冒号 → 逗号
    # 6. 书名号、括号类 → 删除（保留内部文字）
    text = re.sub(r'[《》〈〉「」『』【】〖〗〝〞]', '', text)
    # 7. 省略号 → 句号
    text = re.sub(r'[…‥]', '\u3002', text)
    # 8. 破折号、波浪线 → 逗号
    text = re.sub(r'[—–～〜]', '\uff0c', text)
    # 9. 全角英文字母 → 半角（MeloTTS 对全角英文支持不稳定）
    text = re.sub(r'[Ａ-Ｚ]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
    text = re.sub(r'[ａ-ｚ]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
    # 10. 全角数字 → 半角
    text = re.sub(r'[０-９]', lambda m: chr(ord(m.group()) - 0xFEE0), text)
    # 11. 连续标点去重（超过 2 个相同标点 → 保留 1 个）
    text = re.sub(r'([\u3002\uff0c\uff01\uff1f\u3001])\1{2,}', r'\1', text)
    # 12. 连续换行 → 单个句号
    text = re.sub(r'\n{2,}', '\u3002', text)
    text = re.sub(r'\n', '，', text)
    # 13. 清理不可见控制字符
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    # 14. 末尾无标点 → 补句号
    text = text.strip()
    if text and text[-1] not in '\u3002\uff0c\uff01\uff1f\u3001':
        text += '\u3002'
    return text


def _chunk_text(text: str, max_chars: int = 120) -> list[str]:
    """将长文本按句子边界分割为短块，避免 MeloTTS 单次合成过长导致静音。

    MeloTTS/VITS 对单次输入长度敏感：超过约 150 字可能产生音素对齐错误
    或模型注意力崩溃，导致后半段静音。分句合成可隔离故障范围。
    120 字/块在 VITS 注意力窗口内，同时保证足够上下文避免短句静音。
    """
    # 按句末标点分割
    sentences = re.split(r'(?<=[\u3002\uff01\uff1f\u2026])', text)
    chunks = []
    current = ''
    for sent in sentences:
        sent = sent.strip()
        if not sent:
            continue
        if len(current) + len(sent) <= max_chars:
            current += sent
        else:
            if current:
                chunks.append(current)
            # 如果单个句子就超过 max_chars，按逗号再切
            if len(sent) > max_chars:
                sub_chunks = re.split(r'(?<=[\uff0c\u3001])', sent)
                sub = ''
                for sc in sub_chunks:
                    if len(sub) + len(sc) <= max_chars:
                        sub += sc
                    else:
                        if sub:
                            chunks.append(sub)
                        sub = sc
                if sub:
                    chunks.append(sub)
            else:
                current = sent
    if current:
        chunks.append(current)
    return chunks if chunks else [text]


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


def _concat_wav_files(wav_list: list[bytes]) -> bytes:
    """拼接多个 WAV 音频数据，保持采样率和位深度一致。"""
    if not wav_list:
        return b''
    if len(wav_list) == 1:
        return wav_list[0]

    # 以第一个文件为基准
    with wave.open(io.BytesIO(wav_list[0]), 'rb') as base:
        params = base.getparams()
        base_frames = base.readframes(base.getnframes())

    buf = io.BytesIO()
    with wave.open(buf, 'wb') as out:
        out.setparams(params)
        out.writeframes(base_frames)
        for i, wav_bytes in enumerate(wav_list[1:], 1):
            try:
                with wave.open(io.BytesIO(wav_bytes), 'rb') as wf:
                    if wf.getparams().framerate != params.framerate:
                        logger.warning(f"WAV chunk {i} sample rate mismatch, skipping")
                        continue
                    out.writeframes(wf.readframes(wf.getnframes()))
            except Exception as e:
                logger.warning(f"WAV chunk {i} corrupt, skipping: {e}")
    return buf.getvalue()


def _is_silent_wav(wav_bytes: bytes, threshold: int = 35) -> bool:
    """检测 WAV 音频是否近乎全静音。阈值 35，避免误判轻柔短句。"""
    try:
        data = wav_bytes[44:]  # 跳过 44 字节 WAV 头
        if len(data) < 50:     # 极短音频视为无效
            return True
        max_amp = max(abs(int.from_bytes(data[i:i+2], 'little', signed=True))
                      for i in range(0, len(data) - 1, 2))
        return max_amp < threshold
    except Exception:
        return True


def _make_silence_wav(duration_sec: float = 0.25, sample_rate: int = 22050) -> bytes:
    """生成短静音 WAV，用于标记丢失的文本块（保留段落间的停顿感）。"""
    import struct as _struct
    num_samples = int(duration_sec * sample_rate)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(_struct.pack(f'<{num_samples}h', *([0] * num_samples)))
    logger.info(f"Silence WAV generated: {duration_sec * 1000:.0f}ms")
    return buf.getvalue()


def _aggressive_normalize(text: str) -> str:
    """激进归一化：仅保留中文字符、基本标点和数字，用于最后的兜底合成。"""
    # 保留：中文汉字、中文标点（。，！？、；：）、英文句号逗号、数字、空格
    allowed = re.compile(r'[^\u4e00-\u9fff\u3000-\u303f\uff00-\uffef0-9a-zA-Z.,!? ]')
    cleaned = allowed.sub('', text)
    # 清理连续空白
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if not cleaned:
        return text  # 如果清理后为空，返回原文
    if cleaned[-1] not in '\u3002\uff0c\uff01\uff1f\u3001':
        cleaned += '\u3002'
    return cleaned


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
        """异步合成入口 — 分句合成 + 静音重试，隔离故障。

        策略: 将文本按句子边界切分为短块（≤120字/块），逐块合成，
        静音块自动重试（追加填充句），最后拼接所有有效音频。
        """
        text = text.strip()
        if not text:
            raise ValueError("text is empty")

        # 归一化文本：清除 markdown、列表标记、特殊符号等
        text = _normalize_tts_text(text)
        if not text.strip():
            raise ValueError("text empty after normalization")

        # 短文本补齐（用有实际内容的填充句，避免纯句号导致静音）
        MIN_TTS_LEN = 8
        if len(text) < MIN_TTS_LEN:
            text = text + "，苗族文化源远流长。"
            logger.info(f"Text padded to {len(text)} chars")

        # 分句
        chunks = _chunk_text(text, max_chars=120)
        logger.info(f"TTS chunked: {len(chunks)} segments, total {len(text)} chars")

        # 逐块合成（含静音重试）
        loop = asyncio.get_running_loop()
        valid_wavs = []
        lost_chunks = []  # 记录丢失的文字
        for i, chunk in enumerate(chunks):
            chunk = chunk.strip()
            if not chunk:
                continue
            if len(chunk) < 3:
                logger.info(f"TTS chunk {i} skipped (too short: {len(chunk)} chars)")
                continue

            wav_bytes = await self._synthesize_chunk_with_retry(loop, i, chunk)
            if wav_bytes is not None:
                valid_wavs.append(wav_bytes)
                # 检测是否为静音占位（丢失标记）
                if _is_silent_wav(wav_bytes, threshold=5):
                    lost_chunks.append((i, chunk))

        if not valid_wavs:
            raise ValueError("all TTS chunks failed to synthesize")

        # 如有丢失，发出汇总警告（含丢失文字，方便排查）
        if lost_chunks:
            lost_texts = " | ".join(f"[{i}] {t[:40]}" for i, t in lost_chunks)
            logger.warning(
                f"TTS LOST {len(lost_chunks)}/{len(chunks)} chunks! "
                f"Lost text: {lost_texts}"
            )

        # 拼接所有有效音频
        combined = _concat_wav_files(valid_wavs)
        out_path = os.path.join(self._tmp_dir, f"tts_melo_{os.getpid()}_{uuid.uuid4().hex[:8]}.wav")
        with open(out_path, "wb") as f:
            f.write(combined)

        logger.info(
            f"TTS combined: {len(valid_wavs)}/{len(chunks)} chunks, "
            f"{len(combined)} bytes total, "
            f"lost={len(lost_chunks)}"
        )
        return out_path

    async def _synthesize_chunk_with_retry(self, loop, idx: int, chunk: str):
        """合成单个文本块，3 次递增重试 + 静音兜底，防止文字丢失。

        策略:
          尝试 0 — 原文合成（已通过 _normalize_tts_text 清洗）
          尝试 1 — 追加填充句 "，苗绣。" 增加音素上下文
          尝试 2 — 激进归一化（只保留 CJK+标点+数字），消除所有潜在问题字符
          全部失败 — 生成 250ms 静音占位，保留段落停顿感，文字记入日志供排查
        """
        strategies = [
            ("原文", chunk),
            ("+填充句", chunk + "，苗绣。"),
            ("激进清洗", _aggressive_normalize(chunk)),
        ]

        for attempt, (label, text_to_synth) in enumerate(strategies):
            if attempt > 0:
                logger.info(f"TTS chunk {idx} retry [{label}]: {repr(text_to_synth[:60])}")

            try:
                out_path = await loop.run_in_executor(
                    _thread_pool, self._synthesize_sync, text_to_synth, idx, attempt
                )
                with open(out_path, "rb") as f:
                    wav_bytes = f.read()
                try:
                    os.unlink(out_path)
                except OSError:
                    pass

                # 裁剪开头静音
                wav_bytes = _trim_wav_leading_silence(wav_bytes)

                if _is_silent_wav(wav_bytes):
                    logger.warning(f"TTS chunk {idx} silent [{label}], text={repr(chunk[:50])}")
                    continue  # 下一策略

                logger.info(f"TTS chunk {idx} OK [{label}]: {len(wav_bytes)} bytes, text={repr(chunk[:30])}")
                return wav_bytes

            except Exception as e:
                logger.warning(f"TTS chunk {idx} error [{label}]: {e}, text={repr(chunk[:50])}")
                continue  # 下一策略

        # 全部策略失败 → 生成静音占位，丢弃前记录丢失文字
        logger.error(
            f"TTS chunk {idx} LOST after 3 attempts! "
            f"text={repr(chunk[:80])} "
            f"len={len(chunk)} chars"
        )
        return _make_silence_wav(0.25)  # 250ms 静音标记，不丢段落感

    def _synthesize_sync(self, text: str, chunk_idx: int = 0, attempt: int = 0) -> str:
        """同步合成（在线程池中运行，避免阻塞事件循环）。
        文件名含时间戳+索引，避免 hash 碰撞导致线程池写冲突。"""
        self._load_model()

        uid = f"{int(time.time() * 1000)}_{chunk_idx}_{attempt}_{uuid.uuid4().hex[:6]}"
        out_path = os.path.join(self._tmp_dir, f"tts_melo_{uid}.wav")

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
    # 预热：触发模型下载 + 首次推理（用完整句子确保非静音）
    try:
        logger.info("MeloTTS warmup...")
        await engine.synthesize("你好，苗族文化助手已就绪。")
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
