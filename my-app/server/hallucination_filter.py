"""
苗绣·识裳 — LLM 幻觉过滤器（应用层）
========================================
策略: 关键词评分 → 超过阈值则替换为安全回退语
设计目标: 低计算开销，适合 K1 RISC-V 边缘设备
"""

import re
import logging

logger = logging.getLogger("hallucination_filter")

# ============================================================
# 幻觉特征库（按类别分组，每组有独立权重）
# ============================================================

# 类别 1: 技术术语泄漏 — Qwen 基座模型训练数据残留（权重 3，命中即判）
TECH_LEAK_PATTERNS = [
    r'\bllama\b', r'\btoken\b', r'\bGPT\b', r'\bAI\b',
    r'大模型', r'驱动大模型', r'首字token', r'首字\s*token',
    r'快速排序', r'Python\s*代码', r'编程', r'深度学习',
    r'神经网络', r'transformer', r'fine[\s-]*tun',
    r'量化', r'Q4_K_M', r'gguf', r'ollama\s+run',
    r'核心计算', r'num_thread', r'num_ctx',
]

# 类别 2: 外语碎片 — 非中文内容泄漏（权重 3，命中即判）
FOREIGN_PATTERNS = [
    r'\bqué\b', r'\bhace\b', r'\bleche\b', r'\bmañana\b',  # 西班牙语
    r'\bwhat\b', r'\bthe\b', r'\bthis\b', r'\bthat\b',      # 英语
    r'\bhello\b', r'\b请问.*英文', r'\btranslate',
    r'[a-z]{15,}',  # 连续 15+ 小写英文字母（异常长英文单词）
]

# 类别 3: 身份编造 — 虚构个人信息（权重 2，需累积）
IDENTITY_FAB_PATTERNS = [
    r'我叫(?!阿妹)',       # "我叫XXX"但不是"我叫阿妹"
    r'我来自(?!苗族)',     # "我来自XXX"但不是"我来自苗族"
    r'我住在', r'我家里', r'我妈妈', r'我爸爸',
    r'县.*镇.*村',         # 地名编造模式 "X县X镇X村"
    r'自治县', r'苗族.*自治州',
]

# 类别 4: 角色叙事漂移 — 第三人称旁白（权重 2）
ROLE_NARRATION_PATTERNS = [
    r'^阿妹[：:]',         # "阿妹：XXX"（旁白格式）
    r'^assistant[：:]',
    r'^用户[：:]', r'^user[：:]',
]

# 类别 5: 结构化回答 — 学术/书面风格（权重 1，需累积）
STRUCTURED_PATTERNS = [
    r'综上所述', r'总而言之', r'首先，', r'其次，', r'最后，',
    r'具有以下几方面的意义', r'具有以下几个特点',
    r'^\d+[\.\、]',         # "1." "2、" 编号列表开头
    r'\n\d+[\.\、]',        # 换行后的编号列表
]

# 类别 6: 乱码/异常输出 — 无意义字符（权重 5，命中即判）
GARBLED_PATTERNS = [
    r'[^\x00-\x7f\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]{5,}',  # 5+ 连续非中英文合法字符
    r'([\u4e00-\u9fff])\1{4,}',  # 同一汉字连续重复 5+ 次
]

# ============================================================
# 回退安全回复（阿妹风格的兜底话术）
# ============================================================
FALLBACK_REPLIES = [
    "阿妹不太清楚呢🌸～要不我们聊聊苗绣的蝴蝶纹、银饰的錾刻工艺呀？",
    "哎呀，阿妹只懂苗族文化呢🌸～你想了解苗绣、银饰还是蜡染呀？",
    "这个问题阿妹答不上来🦋～试试问我苗绣有几种针法、银角有什么寓意吧！",
]


def check_hallucination(text: str) -> tuple[bool, int, list[str]]:
    """
    检查文本是否包含幻觉特征。

    返回: (is_hallucination, score, matched_categories)
    - is_hallucination: True 表示应替换为回退语
    - score: 幻觉分数（越高越可疑）
    - matched_categories: 命中的类别名列表
    """
    if not text or not text.strip():
        return False, 0, []

    text_lower = text.lower()
    total_score = 0
    matched_categories = []

    # 类别定义: (名称, 模式列表, 权重, 是否单命中即触发)
    categories = [
        ("TECH_LEAK",    TECH_LEAK_PATTERNS,    3, True),
        ("FOREIGN",      FOREIGN_PATTERNS,      3, True),
        ("GARBLED",      GARBLED_PATTERNS,      5, True),
        ("IDENTITY_FAB", IDENTITY_FAB_PATTERNS, 2, False),
        ("ROLE_NARRATION", ROLE_NARRATION_PATTERNS, 2, False),
        ("STRUCTURED",   STRUCTURED_PATTERNS,   1, False),
    ]

    for cat_name, patterns, weight, instant_trigger in categories:
        cat_hits = 0
        for pat in patterns:
            try:
                if re.search(pat, text_lower if pat.startswith(r'\b') or any(c.isascii() and c.isalpha() for c in pat.replace(r'\b', '')) else text):
                    cat_hits += 1
            except re.error:
                continue
        if cat_hits > 0:
            matched_categories.append(cat_name)
            total_score += weight * cat_hits
            if instant_trigger:
                # 高权重类别命中即判
                logger.warning(f"幻觉检测 [{cat_name}]: score=+{weight * cat_hits}, text_preview={text[:80]}...")
                return True, total_score, matched_categories

    # 对于非即时触发类别，总分 >= 4 才判为幻觉
    if total_score >= 4:
        logger.warning(f"幻觉检测 [累积]: total_score={total_score}, categories={matched_categories}, text_preview={text[:80]}...")
        return True, total_score, matched_categories

    return False, total_score, matched_categories


def filter_response(raw_content: str) -> str:
    """
    过滤 LLM 响应。如果检测到幻觉，返回回退安全回复。

    返回: (过滤后的内容, 是否被替换)
    """
    is_hallu, score, cats = check_hallucination(raw_content)

    if is_hallu:
        import random
        fallback = random.choice(FALLBACK_REPLIES)
        logger.info(f"幻觉已拦截 → 回退: score={score} cats={cats}")
        return fallback

    return raw_content


def filter_stream_chunks(chunks: list[str]) -> tuple[str, bool]:
    """
    对流式响应的完整文本进行过滤。

    参数:
        chunks: 所有已接收的文本块列表

    返回: (最终文本, 是否被替换)
    """
    full_text = "".join(chunks)
    filtered = filter_response(full_text)
    was_replaced = (filtered != full_text)
    return filtered, was_replaced
