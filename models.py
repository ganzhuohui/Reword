"""
proj-publisher — 数据模型层

纯数据结构定义（dataclass），含默认值常量，不含任何业务逻辑。
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field, asdict


# ---------------------------------------------------------------------------
# 默认值常量
# ---------------------------------------------------------------------------

DEFAULT_STYLE = "news_release"
DEFAULT_SCENE = "external_release"
DEFAULT_AUDIENCE = "general_public"
DEFAULT_WORD_COUNT_MIN = 300
DEFAULT_WORD_COUNT_MAX = 800
DEFAULT_LENGTH_STRATEGY = "balanced"
DEFAULT_STRICT_WORD_LIMIT = True
DEFAULT_LANGUAGE = "zh"
DEFAULT_TONE = "formal"
DEFAULT_KEEP_ORIGINAL_TONE = False
DEFAULT_STRUCTURE_MODE = "optimize"
DEFAULT_KEEP_SUBTITLES = True
DEFAULT_AUTO_TITLE = True
DEFAULT_FORBID_NEW_FACTS = True


# ---------------------------------------------------------------------------
# 合法选项常量（供 UI Combo/Radio 初始化及校验使用）
# ---------------------------------------------------------------------------

STYLE_OPTIONS: list[str] = [
    "news_release",      # 新闻稿
    "report",            # 报道稿
    "popular_science",   # 科普稿
    "specification",     # 规范稿
]

SCENE_OPTIONS: list[str] = [
    "external_release",  # 对外发布
    "internal_report",   # 内部汇报
    "study_material",    # 学习材料
    "policy_reference",  # 政策参考
]

AUDIENCE_OPTIONS: list[str] = [
    "general_public",       # 普通公众
    "industry_practitioner",  # 行业同行
    "clients",               # 市场消费
    "professional",          # 专业人员
    "policy_manager",        # 政策人员
]

LENGTH_STRATEGY_OPTIONS: list[str] = [
    "compress_first",  # 压缩优先
    "balanced",        # 平衡
    "expand_first",    # 扩写优先
]

LANGUAGE_OPTIONS: list[str] = ["zh", "en"]

TONE_OPTIONS: list[str] = [
    "formal",       # 正式
    "neutral",      # 中性
    "colloquial",   # 通俗
    "vivid",        # 生动
    "literary",     # 文学化
    "humorous",     # 幽默
]

STRUCTURE_MODE_OPTIONS: list[str] = [
    "preserve",     # 保留原有结构
    "optimize",     # 优化结构
    "reorganize",   # 重新组织结构
]


# ---------------------------------------------------------------------------
# RewriteConfig  — 改写参数配置对象（14 字段）
# ---------------------------------------------------------------------------

@dataclass
class RewriteConfig:
    """存储用户在左侧面板设置的改写参数。"""

    style: str = DEFAULT_STYLE
    scene: str = DEFAULT_SCENE
    audience: str = DEFAULT_AUDIENCE
    word_count_min: int = DEFAULT_WORD_COUNT_MIN
    word_count_max: int = DEFAULT_WORD_COUNT_MAX
    length_strategy: str = DEFAULT_LENGTH_STRATEGY
    strict_word_limit: bool = DEFAULT_STRICT_WORD_LIMIT
    language: str = DEFAULT_LANGUAGE
    tone: str = DEFAULT_TONE
    keep_original_tone: bool = DEFAULT_KEEP_ORIGINAL_TONE
    structure_mode: str = DEFAULT_STRUCTURE_MODE
    keep_subtitles: bool = DEFAULT_KEEP_SUBTITLES
    auto_title: bool = DEFAULT_AUTO_TITLE
    forbid_new_facts: bool = DEFAULT_FORBID_NEW_FACTS

    # ------------------------------------------------------------------
    # 序列化 / 反序列化
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """转为普通 dict（便于 JSON 序列化、QSettings 存储等）。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> RewriteConfig:
        """从 dict 构造。缺失字段自动回退默认值。"""
        valid_keys = {f.name for f in dataclasses.fields(cls)}
        filtered = {k: v for k, v in d.items() if k in valid_keys}
        return cls(**filtered)

    # ------------------------------------------------------------------
    # 快捷方法
    # ------------------------------------------------------------------

    @classmethod
    def default(cls) -> RewriteConfig:
        """创建一个全部为默认值的配置实例。"""
        return cls()

    def reset_to_defaults(self) -> None:
        """将当前实例的所有字段重置为默认值（原地修改）。"""
        defaults = RewriteConfig()
        for f in dataclasses.fields(RewriteConfig):
            setattr(self, f.name, getattr(defaults, f.name))


# ---------------------------------------------------------------------------
# ContentTask — 一次改写任务的数据载体
# ---------------------------------------------------------------------------

@dataclass
class ContentTask:
    """记录一次从输入抽取 -> AI 改写 -> 导出的完整生命周期数据。"""

    source_type: str = ""           # "url" | "text" | "pdf"
    source_value: str = ""          # URL / 原始文本 / PDF 文件路径
    source_title: str = ""          # 从源中自动提取的标题
    extracted_text: str = ""        # 清洗后的纯文本（抽取结果）
    generated_title: str = ""       # AI 生成 / 用户编辑后的标题
    generated_body: str = ""        # AI 生成 / 用户编辑后的正文
    metadata: dict = field(default_factory=dict)

    # ------------------------------------------------------------------
    # 状态判定
    # ------------------------------------------------------------------

    def is_input_ready(self) -> bool:
        """判断是否已有有效的输入源（source_type + source_value 均非空）。"""
        return bool(self.source_type and self.source_value)

    def is_extracted(self) -> bool:
        """判断抽取步骤是否已完成。"""
        return bool(self.extracted_text.strip())

    def is_result_ready(self) -> bool:
        """判断 AI 改写结果是否已就绪。"""
        return bool(self.generated_title.strip() or self.generated_body.strip())

    # ------------------------------------------------------------------
    # 清除操作
    # ------------------------------------------------------------------

    def clear_input(self) -> None:
        """清空输入源相关字段（保留生成结果）。"""
        self.source_type = ""
        self.source_value = ""
        self.source_title = ""
        self.extracted_text = ""

    def clear_output(self) -> None:
        """清空 AI 生成结果（保留输入源）。"""
        self.generated_title = ""
        self.generated_body = ""

    def clear_all(self) -> None:
        """清空所有字段，回到初始空白状态。"""
        self.clear_input()
        self.clear_output()
        self.metadata.clear()
