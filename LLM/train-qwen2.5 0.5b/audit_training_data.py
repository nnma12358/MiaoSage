"""
训练数据质量审计脚本
检查 miao_culture.jsonl 中可能存在的伪知识 / AI 生成内容 / 不一致信息

用法: python audit_training_data.py
"""
import json
import re
import sys
from collections import Counter

# ============================================================
# 配置
# ============================================================
DATA_FILE = "dataset/miao_culture.jsonl"

# 苗族文化核心术语对照表（来自权威文献）
MIAAO_VALID_TERMS = {
    # 苗绣技法（正确术语）
    "平绣", "挑花", "锁绣", "绉绣", "辫绣", "堆绣", "破线绣", "打籽绣",
    "十字绣", "牵花", "包梗绣", "贴布绣", "锡绣", "蚕丝绣",
    # 纹样
    "蝴蝶纹", "蝴蝶妈妈", "鸟纹", "鹡宇鸟", "龙纹", "苗龙", "鱼纹",
    "漩涡纹", "铜鼓纹", "太阳纹", "牛角纹", "枫木纹", "水波纹",
    "花草纹", "石榴纹", "宗庙纹", "骑马纹",
    # 银饰
    "银角", "银冠", "银项圈", "银压领", "银手镯", "银耳环",
    "银梳", "银簪", "银披肩", "银衣片", "银铃铛",
    # 蜡染
    "蜡染", "画蜡", "浸染", "脱蜡", "冰纹", "蓝靛",
    # 服饰类型（五大类型）
    "黔东南型", "黔南型", "黔西南型", "湘西型", "川滇型",
    "雷山式", "台江式", "黄平式", "丹寨式", "榕江式",
    "施洞式", "西江式", "舟溪式",
    # 节日
    "苗年", "姊妹节", "四月八", "吃新节", "鼓藏节", "芦笙节",
    "龙舟节", "爬坡节", "赶秋节", "踩花山",
    # 核心概念
    "蚩尤", "蝴蝶妈妈", "姜央", "枫木歌", "苗族古歌",
    "百鸟衣", "盛装", "便装", "银衣", "雄衣",
}

# 可疑关键词（常出现在 AI 生成/电商文案中）
SUSPICIOUS_TERMS = [
    "hapeplus", "数字化云端平台", "劳动密集型", "技术密集型",
    "AI", "人工智能", "大数据", "互联网+", "赋能", "抓手",
    "现代时尚感", "潮流", "设计感", "ins风", "国潮",
    "非物质文化遗产保护法", "第X条",  # 法律条文通常是编造的
    "据统计", "数据显示", "研究表明",  # 无出处的"数据"
]

def load_data(filepath: str) -> list:
    """加载 JSONL 数据集"""
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                data.append((line_num, record))
            except json.JSONDecodeError as e:
                print(f"[行 {line_num}] JSON 解析错误: {e}")
    return data


def check_term_validity(text: str) -> list:
    """检查文本中的可疑术语"""
    issues = []
    for term in SUSPICIOUS_TERMS:
        if term.lower() in text.lower():
            issues.append(f"   ⚠ 可疑词: '{term}'")
    return issues


def check_numeric_claims(text: str) -> list:
    """检查无出处的数字声明"""
    issues = []
    # 匹配 "X类"、"X种"、"X个"、"X次" 等数量声明
    patterns = [
        (r"(\d+)类", "类"),
        (r"(\d+)种", "种"),
        (r"(\d+)型", "型"),
        (r"(\d+)次大", "次大"),  # "X次大迁徙" 等
        (r"(\d+)级", "级"),
    ]
    for pattern, label in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            # 排除常见合理数字
            if m in ("2", "3", "5", "8"):  # 这些是苗族文化中常见的真实数字
                continue
            issues.append(f"   ⚠ 数字声明: 提到'{m}{label}'但无出处")
    return issues


def audit():
    """主审计流程"""
    print("=" * 60)
    print("  苗绣训练数据质量审计")
    print("=" * 60)

    data = load_data(DATA_FILE)
    print(f"\n📊 总计 {len(data)} 条对话\n")

    total_issues = 0
    suspicious_lines = []
    answer_lengths = []

    for line_num, record in data:
        messages = record.get("messages", [])
        issues_this_record = []

        for msg in messages:
            content = msg.get("content", "")
            role = msg.get("role", "")

            if role == "assistant":
                answer_lengths.append(len(content))

                # 检查可疑术语
                issues_this_record.extend(check_term_validity(content))

                # 检查数字声明
                issues_this_record.extend(check_numeric_claims(content))

                # 检查是否以问句结尾（模型在反问）
                if content.strip().endswith("？") or content.strip().endswith("?"):
                    issues_this_record.append("   ⚠ 回答以问句结尾（可能在反问用户）")

        if issues_this_record:
            total_issues += len(issues_this_record)
            suspicious_lines.append(line_num)
            print(f"[行 {line_num}] 发现 {len(issues_this_record)} 个问题:")
            # 显示对话摘要
            for msg in messages[:2]:
                content = msg.get("content", "")[:80]
                print(f"   {msg.get('role','?')}: {content}...")
            for issue in issues_this_record[:5]:
                print(issue)
            print()

    # ============================================================
    # 统计报告
    # ============================================================
    print("=" * 60)
    print("  统计报告")
    print("=" * 60)
    print(f"  总对话数:       {len(data)}")
    print(f"  有问题对话数:   {len(suspicious_lines)} ({100*len(suspicious_lines)/max(len(data),1):.1f}%)")
    print(f"  总问题数:       {total_issues}")

    if answer_lengths:
        avg_len = sum(answer_lengths) / len(answer_lengths)
        print(f"  平均回答长度:   {avg_len:.0f} 字符")
        print(f"  最长回答:       {max(answer_lengths)} 字符")
        print(f"  最短回答:       {min(answer_lengths)} 字符")

    # ============================================================
    # 建议
    # ============================================================
    print(f"\n{'='*60}")
    print("  修复建议")
    print("=" * 60)

    if total_issues > 0:
        print(f"""
1. 清洗数据: 手动审查上述 {len(suspicious_lines)} 条问题对话
2. 删除来源不明的"知识"（如 hapeplus、数字化平台等）
3. 对照权威文献（苗族古歌、苗学专著）逐条核实
4. 对不确定的知识，改为以下格式重新标注：
   {{
     "messages": [
       {{"role": "user", "content": "苗族服饰分几类？"}},
       {{"role": "assistant", "content": "阿妹不太确定服饰的具体分类呢，建议查阅苗族服饰研究专著～"}}
     ]
   }}
   ↑ 教会模型"不知道就说不知道"
5. 缩短回答到 50-150 字，降低伪知识混入概率
""")

    # 推荐使用 checkpoint-300（欠拟合）而非 checkpoint-600（过拟合）
    print("6. 考虑使用 checkpoint-300 替代 checkpoint-600")
    print("   训练步数越少 → 过拟合越轻 → 幻觉越少（但知识覆盖也少）")
    print()
    print("7. 重新微调时降低 max_steps 到 200-300，增大 lora_dropout 到 0.2")


if __name__ == "__main__":
    audit()
