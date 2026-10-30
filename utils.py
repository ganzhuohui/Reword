"""
proj-publisher — 工具函数层

文本清洗、文件名生成、参数标签转换等辅助功能。
不含任何 UI 依赖，纯数据处理。
"""

from __future__ import annotations

import re
import unicodedata


# ---------------------------------------------------------------------------
# 文本清洗
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """基础清洗：去多余空白行、首尾空白，保留基本段落结构。"""
    if not text:
        return ""
    # 合并连续空行（最多保留一个空行）
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate(text: str, max_len: int = 40000) -> str:
    """截断过长的文本，超出部分加省略提示。"""
    if len(text) <= max_len:
        return text
    return text[:max_len] + f"\n\n[内容过长，已截断（共{len(text)}字）]"


def sanitize_filename(name: str, fallback: str = "未命名") -> str:
    """清洗字符串为合法文件名（去除非法字符、限制长度）。"""
    if not name or not name.strip():
        return fallback
    # 移除 Windows/Linux 下非法文件名字符
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", name)
    # 去除首尾空白和点号
    cleaned = cleaned.strip().strip(".")
    # 限制最大长度（200字符）
    if len(cleaned) > 200:
        cleaned = cleaned[:200]
    return cleaned if cleaned else fallback


# ---------------------------------------------------------------------------
# 参数值 → 中文标签映射
# ---------------------------------------------------------------------------

STYLE_LABELS = {
    "news_release":      "新闻稿",
    "report":            "报道稿",
    "popular_science":   "科普稿",
    "specification":     "规范稿",
}

SCENE_LABELS = {
    "external_release":  "对外发布",
    "internal_report":   "内部汇报",
    "study_material":    "学习材料",
    "policy_reference":  "政策参考",
}

AUDIENCE_LABELS = {
    "general_public":       "普通公众",
    "industry_practitioner": "行业同行",
    "clients":              "市场消费",
    "professional":         "专业人员",
    "policy_manager":       "政策人员",
}

LANGUAGE_LABELS = {
    "zh": "中文",
    "en": "英文",
}

TONE_LABELS = {
    "formal":     "正式",
    "neutral":    "中性",
    "colloquial": "通俗",
    "vivid":      "生动",
    "literary":   "文学化",
    "humorous":   "幽默",
}

STRUCTURE_LABELS = {
    "preserve":     "保留原有结构",
    "optimize":     "优化结构",
    "reorganize":   "重新组织结构",
}

LENGTH_STRATEGY_LABELS = {
    "compress_first": "压缩优先",
    "balanced":       "平衡",
    "expand_first":   "扩写优先",
}


def config_summary_text(config: dict | None) -> str:
    """生成参数的中文摘要字符串（用于日志/状态栏）。"""
    if not config:
        return ""
    parts = []
    parts.append(f"风格: {STYLE_LABELS.get(config.get('style'), '?')}")
    parts.append(f"场景: {SCENE_LABELS.get(config.get('scene'), '?')}")
    parts.append(f"受众: {AUDIENCE_LABELS.get(config.get('audience'), '?')}")
    parts.append(
        f"字数: {config.get('word_count_min', 0)}-{config.get('word_count_max', 0)}"
    )
    parts.append(
        f"策略: {LENGTH_STRATEGY_LABELS.get(config.get('length_strategy'), '?')}"
    )
    parts.append(f"语言: {LANGUAGE_LABELS.get(config.get('language'), '?')}")
    parts.append(f"语气: {TONE_LABELS.get(config.get('tone'), '?')}")
    parts.append(f"结构: {STRUCTURE_LABELS.get(config.get('structure_mode'), '?')}")
    return " | ".join(parts)
