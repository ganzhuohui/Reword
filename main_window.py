"""
proj-publisher — 主窗口 UI (Phase 1)

基于 ui-code.txt / ui-design.txt / ui-setting.txt 搭建完整界面。
包含：APP_STYLE、MainWindow 类、参数收集方法、占位槽函数。
"""

from __future__ import annotations

import sys
import logging

from PySide6.QtCore import Qt, QThread, QTimer, QEasingCurve, QPropertyAnimation, QPoint
from PySide6.QtWidgets import QSizePolicy, QMessageBox, QGraphicsDropShadowEffect
from PySide6.QtGui import QFont, QFontMetrics, QGuiApplication, QPalette, QColor

logger = logging.getLogger(__name__)
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QGroupBox, QLabel, QPushButton, QRadioButton,
    QButtonGroup, QLineEdit, QTextEdit, QFileDialog,
    QComboBox, QCheckBox, QStatusBar, QFrame,
    QGridLayout,
)

# ---------------------------------------------------------------------------
# 从 models 导入所有选项和默认值常量
# ---------------------------------------------------------------------------
from models import (
    STYLE_OPTIONS, SCENE_OPTIONS, AUDIENCE_OPTIONS,
    LENGTH_STRATEGY_OPTIONS, LANGUAGE_OPTIONS, TONE_OPTIONS,
    STRUCTURE_MODE_OPTIONS,
    DEFAULT_WORD_COUNT_MIN, DEFAULT_WORD_COUNT_MAX,
    DEFAULT_STYLE, DEFAULT_SCENE, DEFAULT_AUDIENCE,
    DEFAULT_LENGTH_STRATEGY, DEFAULT_LANGUAGE, DEFAULT_TONE,
    DEFAULT_STRUCTURE_MODE,
    DEFAULT_STRICT_WORD_LIMIT, DEFAULT_AUTO_TITLE,
    DEFAULT_FORBID_NEW_FACTS, DEFAULT_SHOW_SOURCE,
)

# ---------------------------------------------------------------------------
# worker — 后台工作线程与信号（持久化，防止 GC 回收）
# ---------------------------------------------------------------------------
from worker import RewriteWorker, WorkerSignals

# ---------------------------------------------------------------------------
# 中文显示标签 ↔ 英文值映射表（供 Radio/Combo 读写使用）
# ---------------------------------------------------------------------------

LABEL_MAP = {
    "style":         ["新闻稿", "报道稿", "科普稿", "规范稿"],
    "scene":         ["对外发布", "内部汇报", "学习材料", "政策参考"],
    "audience":      ["普通公众", "行业同行", "市场消费", "专业人员", "政策人员"],
    "length_strategy":["压缩优先", "平衡", "扩写优先"],
    "language":      ["中文", "英文"],
    "tone":          ["正式", "中性", "通俗", "生动", "文学化", "幽默"],
    "structure_mode":["保留原结构", "优化结构", "重组结构"],
}

OPTIONS_MAP = {
    "style":         STYLE_OPTIONS,
    "scene":         SCENE_OPTIONS,
    "audience":      AUDIENCE_OPTIONS,
    "length_strategy":LENGTH_STRATEGY_OPTIONS,
    "language":      LANGUAGE_OPTIONS,
    "tone":          TONE_OPTIONS,
    "structure_mode":STRUCTURE_MODE_OPTIONS,
}


def _get_option_value(field: str, combo: QComboBox) -> str:
    """通过 combo 的选中索引从 OPTIONS_MAP 中取真实英文值。"""
    return OPTIONS_MAP[field][combo.currentIndex()]


# ---------------------------------------------------------------------------
# 语言代码映射 — GUI 显示文本 → I18n 代码
# ---------------------------------------------------------------------------
def _map_language(display_text: str) -> str:
    """将语言组合框的显示文本（如'中文','英文'）映射为 ISO 639-1 代码。"""
    mapping = {
        "中文": "zh",
        "英文": "en",
        "日本語": "ja",
        "한국어": "ko",
    }
    return mapping.get(display_text, display_text[:2].lower())


# ---------------------------------------------------------------------------
# LoadingOverlay — 半透明加载面板（旋转动画 + 状态 + 计时器 + 取消按钮）
# ---------------------------------------------------------------------------

class LoadingOverlay(QWidget):
    """
    半透明悬浮面板，覆盖在目标 widget 上方。

    包含：
      - Unicode spinner 旋转动画 (⠋⠙⠹⠸⠼⠴⠦⠧)
      - 状态文本（实时更新）
      - 计时器显示已等待秒数
      - 取消按钮
    """

    SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧")

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_timer_tick)
        self._spinner_index = 0
        self._seconds = 0

    def _setup_ui(self):
        self.setStyleSheet(
            "background-color: rgba(0, 0, 0, 150);"
            "border-radius: 8px;"
        )
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # --- Spinner + 状态文本行 ---
        top_row = QHBoxLayout()
        top_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.spinner_label = QLabel("⠋")
        self.spinner_label.setFont(QFont("Noto Sans", 24))
        self.spinner_label.setStyleSheet("color: #60A5FA; background: transparent;")
        top_row.addWidget(self.spinner_label)

        self.status_label = QLabel("正在加载…")
        self.status_label.setFont(QFont("Noto Sans", 14))
        self.status_label.setStyleSheet("color: #E5E7EB; background: transparent;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_row.addWidget(self.status_label)

        layout.addLayout(top_row)

        # --- 计时器行 ---
        timer_row = QHBoxLayout()
        timer_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.timer_label = QLabel("已等待 0 秒")
        self.timer_label.setFont(QFont("Noto Sans", 12))
        self.timer_label.setStyleSheet("color: #9CA3AF; background: transparent;")
        timer_row.addWidget(self.timer_label)
        layout.addLayout(timer_row)

        # --- 提示文本 ---
        hint = QLabel("AI 首次加载模型可能需要较长时间，请耐心等待…")
        hint.setFont(QFont("Noto Sans", 10))
        hint.setStyleSheet("color: #6B7280; background: transparent;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

        # --- 取消按钮 ---
        self.cancel_button = QPushButton("✕  取消任务")
        self.cancel_button.setFont(QFont("Noto Sans", 13))
        self.cancel_button.setFixedSize(140, 42)
        self.cancel_button.setStyleSheet(
            "QPushButton {"
            "   background-color: #EF4444;"
            "   color: white;"
            "   border-radius: 8px;"
            "   padding: 6px 16px;"
            "}"
            "QPushButton:hover {"
            "   background-color: #DC2626;"
            "}"
            "QPushButton:pressed {"
            "   background-color: #B91C1C;"
            "}"
        )
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.addWidget(self.cancel_button)
        layout.addLayout(btn_row)

        layout.setContentsMargins(40, 30, 40, 30)

    def _on_timer_tick(self):
        self._seconds += 1
        self.timer_label.setText(f"已等待 {self._seconds} 秒")
        self._spinner_index = (self._spinner_index + 1) % len(self.SPINNER_FRAMES)
        self.spinner_label.setText(self.SPINNER_FRAMES[self._spinner_index])

    def show_event(self, parent_widget: QWidget, message: str = "正在加载…"):
        """显示在父控件中央，调整大小适应内容。"""
        self.status_label.setText(message)
        self._seconds = 0
        self._spinner_index = 0
        self.spinner_label.setText(self.SPINNER_FRAMES[0])
        self.timer_label.setText("已等待 0 秒")

        geo = parent_widget.geometry()
        w, h = int(geo.width() * 0.55), int(geo.height() * 0.6)
        x, y = (geo.width() - w) // 2, (geo.height() - h) // 2
        self.setGeometry(x, y, w, h)

        self.raise_()
        self.show()
        self._timer.start(100)

    def hide_event(self):
        """隐藏面板，停止定时器。"""
        self._timer.stop()
        self.hide()

    def set_message(self, message: str):
        """更新状态文本。"""
        self.status_label.setText(message)


# ---------------------------------------------------------------------------
# APP_STYLE — 全局样式表
# ---------------------------------------------------------------------------
APP_STYLE = """
QWidget {
    background: #EEEEEE;
    color: #1F2937;
    font-family: 'Noto Sans';
    font-size: 9pt;
}

QGroupBox {
    background: transparent;
    border: 1px solid #DDE3EA;
    border-radius: 8pt;
    margin-top: 8pt;
    padding: 8pt;
}

QLabel {
    background: transparent;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10pt;
    padding: 0 4pt;
    font-size: 7pt;
}

QLineEdit, QTextEdit, QComboBox, QSpinBox {
    background: #FFFFFF;
    border: 0.8px solid #DCE1E8;
    border-radius: 8pt;
    padding: 4pt 8pt;
    selection-background-color: #EAF2FF;
    min-height: 30pt;
}

QComboBox::drop-down {
    background: #FFFFFF;
}

QComboBox::down-arrow {
    image: none;
    border: none;
}

QTextEdit {
    min-height: auto;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1.5pt solid #6BA4E0;
    background: #FAFBFD;
}

QPushButton {
    background: #FFFFFF;
    border: 0.8px solid #DCE1E8;
    border-radius: 7pt;
    padding: 6pt 12pt;
    min-height: 30pt;
}

QPushButton:hover {
    background: #EEF4FB;
    border-color: #BFCDE0;
}

QPushButton:pressed {
    background: #DCE5F2;
}

QPushButton#primaryButton {
    background: #5B8DB8;
    color: white;
    border: 0.5px solid transparent;
    border-radius: 8pt;
    padding: 4pt 12pt;
    min-height: 36px;
    max-height: 36px;
    min-width: 80px;
    max-width: 80px;
}

QPushButton#primaryButton:hover {
    background: #4A7CA8;
    border-color: #3D6F9E;
}

QPushButton#primaryButton:pressed {
    background: #3F6D96;
}

QRadioButton {
    spacing: 6pt;
}

QScrollBar:vertical {
    width: 10pt;
    background: #F7F9FC;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #C9D4E3;
    min-height: 24pt;
    border-radius: 5pt;
}

QStatusBar {
    background: #FFFFFF;
    border-top: 1px solid #DDE3EA;
}

QMenuBar {
    spacing: 6pt;
}

QMenuBar::item {
    padding: 4pt 8pt;
    spacing: 6pt;
    background: transparent;
}

QMenuBar::item:selected {
    background: #EEF4FB;
}

QToolBar {
    spacing: 6pt;
    border: none;
    background: transparent;
}

QToolBar::separator {
    width: 1px;
    background: #DDE3EA;
}
"""


class MainWindow(QMainWindow):
    """文章改写工具主窗口。"""

    def __init__(self):
        super().__init__()

        # ------------------------------------------------------------------
        # T1.8 — 持久化 WorkerSignals，防止被 GC 回收导致段错误 / AttributeError
        # ------------------------------------------------------------------
        self._signals = WorkerSignals()
        self._thread: QThread | None = None            # 后台线程引用
        self._worker: RewriteWorker | None = None       # 工作器引用（用于 cancel）

        self.setWindowTitle("文章改写工具")
        self.resize(1280, 720)
        self.setMinimumSize(960, 540)
        # --- HiDPI / 动态字体适配 ---
        self._dpr = QGuiApplication.primaryScreen().devicePixelRatio()
        font_size = 9 * self._dpr  # base pt x DPR -> effective px size
        font = QFont("Noto Sans", round(font_size))
        QApplication.setFont(font)

        # --- FontMetrics-based layout constants (auto-scale with DPI/font) ---
        fm = QFontMetrics(font)
        fh = fm.height()            # rendered font height in px
        self._margin = max(int(fh * 1.2), 8)       # ~96% of a typical line, min 8px
        self._spacing = max(int(fh * 0.6), 4)      # ~56% of a typical line, min 4px

        central = QWidget()
        self.setCentralWidget(central)

        # T2.5 — LoadingOverlay 实例（父为 central widget，覆盖在顶层）
        self.overlay = LoadingOverlay(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(self._margin, self._margin, self._margin, self._margin)
        root_layout.setSpacing(self._spacing)

        top_bar = self._build_top_bar()
        root_layout.addWidget(top_bar)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(8)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 920])

        root_layout.addWidget(splitter)

        bottom_bar = self._build_bottom_bar()
        root_layout.addWidget(bottom_bar)

        self.setStatusBar(QStatusBar())
        self._status = self.statusBar()
        self.statusBar().showMessage("就绪")

    # -----------------------------------------------------------------------
    # T1.2 — 顶部操作栏
    # -----------------------------------------------------------------------

    def _build_top_bar(self):
        """顶部占位条（保留布局间距，按钮已移至底部）。"""
        frame = QFrame()
        frame.setObjectName("topBar")
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        return frame

    # -----------------------------------------------------------------------
    # T1.3 — 左面板（输入源 + 参数 G1~G5）
    # -----------------------------------------------------------------------

    def _build_left_panel(self):
        scroll = QFrame()
        scroll.setFixedWidth(404)
        layout = QVBoxLayout(scroll)
        layout.setContentsMargins(0, 0, 0, 0)

        self._build_input_section(layout)
        self._build_article_params(layout)

        return scroll

    # -----------------------------------------------------------------------
    # T1.4 — 左侧输入源区域（纵向单选 + 行内控件）
    # -----------------------------------------------------------------------

    def _build_input_section(self, layout: QVBoxLayout):
        # --- "输入来源"独立标题标签，紧贴框上方 ---
        input_title = QLabel("输入来源")
        input_title.setStyleSheet(
            "QLabel { font-weight: bold; font-size: 10pt; padding-bottom: 2px; }"
        )
        layout.addWidget(input_title)

        gb = QGroupBox("")
        gb.setFlat(True)
        outer = QVBoxLayout(gb)
        outer.setSpacing(6)

        # --- 纵向单选按钮组：网页链接 / 上传 PDF / 粘贴全文 ---
        self.rb_url = QRadioButton("网页链接")
        self.rb_url.setChecked(True)
        self.rb_pdf = QRadioButton("上传 PDF")
        self.rb_text = QRadioButton("粘贴全文")
        input_group = QButtonGroup()
        input_group.addButton(self.rb_url)
        input_group.addButton(self.rb_pdf)
        input_group.addButton(self.rb_text)

        # --- 行内控件（与对应单选按钮并排） ---
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://...")
        btn_load_url = QPushButton("加载")
        btn_load_url.setFixedWidth(60)

        self.pdf_path = QLineEdit()
        self.pdf_path.setPlaceholderText("选择 PDF 文件…")
        self.pdf_path.setReadOnly(True)
        self.btn_open_pdf = QPushButton("浏览")
        self.btn_open_pdf.setFixedWidth(60)
        self.cb_pdf_ocr = QCheckBox("OCR识别")

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText("在此粘贴全文…")
        self.text_input.setMinimumHeight(120)

        # --- 用垂直布局排列：每一行 = 单选按钮 + 控件 ---
        input_rows = QVBoxLayout()
        input_rows.setSpacing(4)
        input_rows.setContentsMargins(8, 4, 0, 4)

        # Row: 网页链接 + URL 输入框 + "加载"
        url_row = QHBoxLayout()
        url_row.setContentsMargins(0, 0, 0, 0)
        url_row.setSpacing(6)
        url_row.addWidget(self.rb_url)
        url_row.addWidget(self.url_edit, stretch=1)
        url_row.addWidget(btn_load_url)

        # Row: 上传 PDF + 路径 + "打开" + OCR
        pdf_row = QHBoxLayout()
        pdf_row.setContentsMargins(0, 0, 0, 0)
        pdf_row.setSpacing(6)
        pdf_row.addWidget(self.rb_pdf)
        pdf_row.addWidget(self.pdf_path, stretch=1)
        pdf_row.addWidget(self.btn_open_pdf)
        pdf_row.addWidget(self.cb_pdf_ocr)

        # Row: 粘贴全文 + QTextEdit（跨全宽）
        text_row = QHBoxLayout()
        text_row.setContentsMargins(0, 0, 0, 0)
        text_row.setSpacing(6)
        text_row.addWidget(self.rb_text)
        text_row.addStretch(1)

        text_input_row = QHBoxLayout()
        text_input_row.setContentsMargins(20, 0, 0, 0)
        text_input_row.setSpacing(0)
        text_input_row.addWidget(self.text_input, stretch=1)

        input_rows.addLayout(url_row)
        input_rows.addLayout(pdf_row)
        input_rows.addLayout(text_row)
        input_rows.addLayout(text_input_row)

        outer.addLayout(input_rows)
        layout.addWidget(gb)

        self.rb_url.toggled.connect(self.update_input_mode)
        self.rb_text.toggled.connect(self.update_input_mode)
        self.rb_pdf.toggled.connect(self.update_input_mode)
        self.btn_open_pdf.clicked.connect(self.choose_pdf)
        btn_load_url.clicked.connect(self._load_url_placeholder)
        self.update_input_mode()

    def _load_url_placeholder(self):
        """URL 加载占位（Phase-2）。"""
        url = self.url_edit.text().strip()
        if not url:
            self._status.showMessage("请输入网页链接。")
            return
        self._status.showMessage(f"正在加载: {url} — Phase 2", 3000)

    # -----------------------------------------------------------------------
    # T1.5 — 统一「设置参数」区（G1~G5 合并）
    #         内部用 QGroupBox + QLabel 分隔线区分，字段均为行内水平排列
    # -----------------------------------------------------------------------

    def _build_article_params(self, layout: QVBoxLayout):
        """将 G1~G5 参数合并到一个 GroupBox 中"""
        # --- "设置参数"独立标题标签，紧贴框上方 ---
        params_title = QLabel("设置参数")
        params_title.setStyleSheet(
            "QLabel { font-weight: bold; font-size: 10pt; padding-bottom: 2px; }"
        )
        layout.addWidget(params_title)

        gb = QGroupBox("")
        gb.setFlat(True)
        main_layout = QVBoxLayout(gb)
        main_layout.setSpacing(10)

        # ────────── helper: 统一 Combo 宽度（4个汉字 + 填充）及创建 ──────────
        self_fm = QFontMetrics(self.font())
        combo_width = int(self_fm.horizontalAdvance("中文标签") + 16)

        def make_combo():
            c = QComboBox()
            c.setMinimumWidth(combo_width)
            c.setMaximumWidth(combo_width)
            return c

        # ────────── helper: QLabel 宽度适配实际文本（+少量填充）────
        _spacing = int(self_fm.horizontalAdvance("中中"))  # ≈2个汉字间距

        def _make_label(title: str, width_pad: int = 6):
            w = self_fm.horizontalAdvance(title)
            lbl = QLabel(title)
            #lbl.setMinimumWidth(w)
            #lbl.setMaximumWidth(w + width_pad)
            lbl.setFixedWidth(w + width_pad)    
            lbl.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            return lbl

        # ────────── helper: 一行 "QLabel(标题) + QWidget(控件)" ──────────
        def add_row(title: str, widget: QWidget, stretch_widget: int = 1):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(_spacing)
            lbl = _make_label(title)
            row.addWidget(lbl)
            row.addWidget(widget, stretch=stretch_widget)
            main_layout.addLayout(row)

        # ────────── helper: 双控件行 "QLabel + Widget | QLabel + Widget" ───────
        def add_dual_row(title1: str, widget1: QWidget, title2: str, widget2: QWidget):
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(_spacing)
            lbl1 = _make_label(title1)
            lbl2 = _make_label(title2)
            row.addWidget(lbl1)
            row.addWidget(widget1)
            row.addStretch(1)
            row.addWidget(lbl2)
            row.addWidget(widget2)
            main_layout.addLayout(row)

        # ────────── G1: 文体+使用场景 · 目标受众+长度策略 ──────────
        self.style_combo = make_combo()
        self.style_combo.addItems(LABEL_MAP["style"])
        self.style_combo.setCurrentIndex(
            OPTIONS_MAP["style"].index(DEFAULT_STYLE))

        self.scene_combo = make_combo()
        self.scene_combo.addItems(LABEL_MAP["scene"])
        self.scene_combo.setCurrentIndex(
            OPTIONS_MAP["scene"].index(DEFAULT_SCENE))
        add_dual_row("文稿体裁", self.style_combo, "使用场景", self.scene_combo)

        self.audience_combo = make_combo()
        self.audience_combo.addItems(LABEL_MAP["audience"])
        self.audience_combo.setCurrentIndex(
            OPTIONS_MAP["audience"].index(DEFAULT_AUDIENCE))

        # 长度策略与受众同行
        self.length_combo = make_combo()
        self.length_combo.addItems(LABEL_MAP["length_strategy"])
        self.length_combo.setCurrentIndex(
            OPTIONS_MAP["length_strategy"].index(DEFAULT_LENGTH_STRATEGY))
        add_dual_row("目标受众", self.audience_combo, "长度策略", self.length_combo)

        # 4-digit width for word count inputs (e.g. "9999")
        wc_width = int(self_fm.horizontalAdvance("99999") )

        # ────────── 文章结构 + 最低/最高字数（同行）──────────
        struct_word_row = QHBoxLayout()
        struct_word_row.setContentsMargins(0, 0, 0, 0)
        struct_word_row.setSpacing(_spacing)

        lbl_struct = _make_label("文章结构")
        struct_word_row.addWidget(lbl_struct)

        self.struct_combo = make_combo()
        self.struct_combo.addItems(LABEL_MAP["structure_mode"])
        self.struct_combo.setCurrentIndex(
            OPTIONS_MAP["structure_mode"].index(DEFAULT_STRUCTURE_MODE))
        struct_word_row.addWidget(self.struct_combo)

        # 右侧：最低字数 / 最高字数
        struct_word_row.addStretch(1)

        lbl_min = _make_label("字数 min")
        struct_word_row.addWidget(lbl_min)

        self.word_count_min = QLineEdit()
        self.word_count_min.setPlaceholderText("如 800")
        self.word_count_min.setText(str(DEFAULT_WORD_COUNT_MIN))
        self.word_count_min.setFixedWidth(wc_width)
        from PySide6.QtCore import QRegularExpression
        from PySide6.QtGui import QRegularExpressionValidator
        wc_validator = QRegularExpressionValidator(QRegularExpression(r"^\d{1,5}$"))
        self.word_count_min.setValidator(wc_validator)
        struct_word_row.addWidget(self.word_count_min)

        dash = QLabel("—")
        dash.setFixedWidth(4)
        struct_word_row.addWidget(dash)

        lbl_max = _make_label("max")
        struct_word_row.addWidget(lbl_max)

        self.word_count_max = QLineEdit()
        self.word_count_max.setPlaceholderText("如 2000")
        self.word_count_max.setText(str(DEFAULT_WORD_COUNT_MAX))
        self.word_count_max.setFixedWidth(wc_width)
        wc_validator2 = QRegularExpressionValidator(QRegularExpression(r"^\d{1,5}$"))
        self.word_count_max.setValidator(wc_validator2)
        struct_word_row.addWidget(self.word_count_max)

        main_layout.addLayout(struct_word_row)

        # ────────── G3: 输出语言 · 语气风格 ──────────
        self.language_combo = make_combo()
        self.language_combo.addItems(LABEL_MAP["language"])
        self.language_combo.setCurrentIndex(
            OPTIONS_MAP["language"].index(DEFAULT_LANGUAGE))

        self.tone_combo = make_combo()
        self.tone_combo.addItems(LABEL_MAP["tone"])
        self.tone_combo.setCurrentIndex(
            OPTIONS_MAP["tone"].index(DEFAULT_TONE))
        add_dual_row("输出语言", self.language_combo, "语气风格", self.tone_combo)

        # ────────── G4: 格式要求复选框 ──────────
        from models import (
            DEFAULT_STRICT_WORD_LIMIT,
            DEFAULT_AUTO_TITLE,
            DEFAULT_FORBID_NEW_FACTS, DEFAULT_SHOW_SOURCE,
        )
        self.cb_strict_word_limit = QCheckBox("严格遵守字数限制")
        self.cb_strict_word_limit.setChecked(DEFAULT_STRICT_WORD_LIMIT)

        self.cb_auto_title = QCheckBox("自动生成标题")
        self.cb_auto_title.setChecked(DEFAULT_AUTO_TITLE)

        self.cb_forbid_new_facts = QCheckBox("不引入新事实")
        self.cb_forbid_new_facts.setChecked(DEFAULT_FORBID_NEW_FACTS)

        self.cb_show_source = QCheckBox("显示来源标注")
        self.cb_show_source.setChecked(DEFAULT_SHOW_SOURCE)

        fmt_grid = QGridLayout()
        fmt_grid.setSpacing(8)
        fmt_grid.addWidget(self.cb_strict_word_limit, 0, 0)
        fmt_grid.addWidget(self.cb_auto_title, 0, 1)
        fmt_grid.addWidget(self.cb_forbid_new_facts, 1, 0)
        fmt_grid.addWidget(self.cb_show_source, 1, 1)

        lbl = _make_label("高级选项")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(_spacing)
        row.addWidget(lbl)
        row.addLayout(fmt_grid)
        main_layout.addLayout(row)

        # ────────── 特殊说明 (Special Remarks) ──────────
        self.special_remarks = QTextEdit()
        self.special_remarks.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF;
                border: 1px solid #DDE3EA;
                border-radius: 6pt;
                padding: 6pt 8pt;
            }
        """)
        self.special_remarks.setPlaceholderText(
            "在此输入特殊要求，这些要求将具有最高优先级，覆盖其他所有设置…"
        )
        self.special_remarks.setMaximumHeight(100)

        lbl2 = _make_label("附加要求")
        row2 = QHBoxLayout()
        row2.setContentsMargins(0, 0, 0, 0)
        row2.setSpacing(_spacing)
        lbl2.setAlignment(Qt.AlignTop)
        row2.addWidget(lbl2)
        row2.addWidget(self.special_remarks, stretch=1)
        main_layout.addLayout(row2)

        layout.addWidget(gb)

    # -----------------------------------------------------------------------
    # T2 — 右侧输出区（含标签页、导出/清空按钮）
    # -----------------------------------------------------------------------

    def _build_right_panel(self) -> QWidget:
        """构建右侧输出面板（仅标签页，按钮统一放到底部工具栏）。"""
        container = QWidget()
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(self._spacing)

        # --- 标签页 ---
        from PySide6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(False)

        # Tab 1: 结果预览 (含标题行 + 正文区)
        tab1_widget = QWidget()
        tab1_layout = QVBoxLayout(tab1_widget)
        tab1_layout.setContentsMargins(0, 0, 0, 0)
        tab1_layout.setSpacing(8)

        # 标题输入框 (只读，由 AI 生成后填充)
        self.title_edit = QLineEdit()
        self.title_edit.setReadOnly(True)
        self.title_edit.setPlaceholderText("改写后的标题将显示在此…")
        self.title_edit.setFixedHeight(36)
        tab1_layout.addWidget(self.title_edit)

        # 正文预览区
        self.result_view = QTextEdit()
        self.result_view.setReadOnly(True)
        self.result_view.setPlaceholderText("改写结果将在此显示…")
        font = QFont("Noto Sans", 9)
        self.result_view.setFont(font)
        tab1_layout.addWidget(self.result_view, stretch=1)

        self.tabs.addTab(tab1_widget, "结果预览")

        # Tab 2: 原文/结果对照
        diff_widget = QWidget()
        diff_layout = QVBoxLayout(diff_widget)
        diff_layout.setSpacing(8)
        left_splitter = QSplitter(Qt.Horizontal)
        self.orig_view = QTextEdit()
        self.orig_view.setReadOnly(True)
        self.orig_view.setPlaceholderText("原文…")
        font2 = QFont("Noto Sans", 9)
        self.orig_view.setFont(font2)
        self.gen_view = QTextEdit()
        self.gen_view.setReadOnly(True)
        self.gen_view.setPlaceholderText("生成结果…")
        self.gen_view.setFont(font2)
        left_splitter.addWidget(self.orig_view)
        left_splitter.addWidget(self.gen_view)
        left_splitter.setStretchFactor(0, 1)
        left_splitter.setStretchFactor(1, 1)
        diff_layout.addWidget(QLabel("原文 / 改写对照"))
        diff_layout.addWidget(left_splitter, stretch=1)
        self.tabs.addTab(diff_widget, "对照视图")

        root_layout.addWidget(self.tabs, stretch=1)

        return container

    # -----------------------------------------------------------------------
    # T1.8 — 底部工具栏（主操作按钮 + 导出格式选择）
    # -----------------------------------------------------------------------

    def _build_bottom_bar(self):
        """底部工具栏：新建任务、清空参数、开始改写 + 复制/导出 + 格式选择。"""
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.btn_new = QPushButton("新建任务")
        self.btn_new.setObjectName("primaryButton")

        self.btn_clear_params = QPushButton("清空参数")
        self.btn_clear_params.setObjectName("primaryButton")

        self.btn_start = QPushButton("开始写作")
        self.btn_start.setObjectName("primaryButton")

        self.btn_copy_result = QPushButton("复制结果")
        self.btn_copy_result.setObjectName("primaryButton")

        self.btn_export = QPushButton("导出结果")
        self.btn_export.setObjectName("primaryButton")

        # 导出格式选择 (TXT / DOCX)
        self.radio_txt = QRadioButton("TXT")
        self.radio_txt.setChecked(True)
        self.radio_docx = QRadioButton("DOCX")
        self.export_group = QButtonGroup()
        self.export_group.addButton(self.radio_txt)
        self.export_group.addButton(self.radio_docx)

        fmt_label = QLabel("格式:")
        fmt_label.setMinimumWidth(36)

        layout.addWidget(self.btn_new, stretch=0)
        layout.addWidget(self.btn_clear_params, stretch=0)
        
        layout.addWidget(self.btn_start, stretch=0)
        layout.addStretch(1)
        layout.addStretch(1)
        layout.addWidget(self.btn_copy_result, stretch=0)
        layout.addWidget(self.btn_export, stretch=0)
        layout.addWidget(fmt_label, stretch=0)
        layout.addWidget(self.radio_txt, stretch=0)
        layout.addWidget(self.radio_docx, stretch=0)

        # 连线
        self.btn_new.clicked.connect(self.new_project)
        self.btn_clear_params.clicked.connect(self.clear_all)
        self.btn_start.clicked.connect(self.start_writing)

        # T2.5 — LoadingOverlay 取消按钮连线到 worker.cancel()
        self.overlay.cancel_button.clicked.connect(self._on_cancel_overlay)

        self.btn_copy_result.clicked.connect(
            lambda: QApplication.clipboard().setText(self.result_view.toPlainText()))
        self.btn_export.clicked.connect(self.save_output)

        return frame

    # -----------------------------------------------------------------------
    # 输入模式切换 / 工具方法
    # -----------------------------------------------------------------------

    def update_input_mode(self):
        """根据当前选中的 RadioButton 启用/禁用对应的输入控件。"""
        mode = "text"
        if self.rb_url.isChecked():
            mode = "url"
        elif self.rb_pdf.isChecked():
            mode = "pdf"

        self.url_edit.setEnabled(mode == "url")
        self.text_input.setEnabled(mode == "text")
        self.pdf_path.setEnabled(mode == "pdf")
        self.cb_pdf_ocr.setEnabled(mode == "pdf")
        self.btn_open_pdf.setEnabled(mode == "pdf")

    def choose_pdf(self):
        """弹出文件对话框选择 PDF。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择 PDF", "", "*.pdf  (*.pdf)")
        if path:
            self.pdf_path.setText(path)

    # -----------------------------------------------------------------------
    # 顶部按钮槽函数（Phase-1 占位）
    # -----------------------------------------------------------------------

    def new_project(self):
        """新建项目：清空左右两侧。"""
        self.clear_all()

    def open_file(self):
        """打开本地文件到左侧输入区。"""
        path, _ = QFileDialog.getOpenFileName(
            self, "打开文件", "",
            "所有支持格式 (*.pdf *.docx *.txt);;PDF 文件 (*.pdf);;"
            "Word 文档 (*.docx);;文本文件 (*.txt)")
        if path:
            self._status.showMessage(f"已选择: {path}")

    def clear_all(self):
        """清空全部区域。"""
        self.clear_left_input()
        self.clear_right_output()
        # Reset to defaults
        if hasattr(self, "style_combo"):
            self.style_combo.setCurrentIndex(0)             # default=新闻稿(news_release)
            self.scene_combo.setCurrentIndex(0)             # default=对外发布(external_release)
            self.audience_combo.setCurrentIndex(0)          # default=普通公众(general_public)
            self.length_combo.setCurrentIndex(1)            # default=平衡(balanced)
            self.language_combo.setCurrentIndex(0)          # default=中文(zh)
            self.tone_combo.setCurrentIndex(0)              # default=正式(formal)
            self.struct_combo.setCurrentIndex(1)            # default=优化结构(optimize)
            self.word_count_min.setText(str(DEFAULT_WORD_COUNT_MIN))
            self.word_count_max.setText(str(DEFAULT_WORD_COUNT_MAX))
            self.cb_strict_word_limit.setChecked(DEFAULT_STRICT_WORD_LIMIT)
            self.cb_auto_title.setChecked(DEFAULT_AUTO_TITLE)
            self.cb_forbid_new_facts.setChecked(DEFAULT_FORBID_NEW_FACTS)
            self.cb_show_source.setChecked(DEFAULT_SHOW_SOURCE)
        if hasattr(self, "special_remarks"):
            self.special_remarks.clear()

    def start_writing(self):
        """点击「开始撰写」→ 内容提取 → AI 改写（后台线程）。"""
        config = self.collect_parameters()
        source_type, source_value = self._get_source_info()

        if not source_value:
            QMessageBox.warning(
                self, "缺少输入",
                "请先选择输入源（网页 URL / PDF 文件）或在文本框中粘贴原文。",
            )
            return

        # 禁用按钮防止重复点击
        self.btn_start.setEnabled(False)
        self.btn_start.setText("改写中…")

        # 清空结果区并显示加载状态
        self.title_edit.clear()
        self.result_view.clear()
        self.result_view.append("⏳ 正在准备改写任务…")

        # T2.5 — 显示 LoadingOverlay（覆盖整个 central widget）
        self.overlay.show_event(self.centralWidget(), "正在启动 AI 改写任务…")

        # 创建后台线程 — T1.8：复用持久化信号对象，先清理旧线程
        signals = self._signals

        if self._thread and self._thread.isRunning():
            if self._worker:
                self._worker.cancel()
            self._thread.wait(3000)
            # 断开旧连接防止重复发射（忽略未连接的信号）
            for sig_name in ("status", "progress", "finished", "error"):
                try:
                    getattr(self._signals, sig_name).disconnect()
                except TypeError:
                    pass

        signals.status.connect(lambda msg: self._status.showMessage(msg))
        signals.progress.connect(self._on_progress)
        signals.finished.connect(self._on_rewrite_finished)
        signals.error.connect(self._on_rewrite_error)

        self._thread = QThread()
        self._worker = RewriteWorker(source_type, source_value, config, signals)
        self._worker.moveToThread(self._thread)

        # 线程完成 / 错误后自动清理（通过 thread.finished → _on_thread_finished）
        self._thread.started.connect(self._worker.run)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)

        self._thread.start()

    def save_output(self):
        """保存输出到本地（根据 TXT/DOCX 单选按钮选择默认格式）。"""
        text = self.result_view.toPlainText()
        title = self.title_edit.text().strip()
        if not text.strip():
            self._status.showMessage("没有可保存的内容。")
            return

        # 根据导出格式选择决定默认扩展名和过滤器
        if self.radio_docx.isChecked():
            default_ext = "改写结果.docx"
            filters = "Word 文档 (*.docx);;文本文件 (*.txt)"
            fmt = "docx"
        else:
            default_ext = "改写结果.txt"
            filters = "文本文件 (*.txt);;Word 文档 (*.docx)"
            fmt = "txt"

        path, _ = QFileDialog.getSaveFileName(
            self, "保存改写结果", "", filters)
        if path:
            # 确保文件扩展名正确
            if fmt == "docx" and not path.lower().endswith(".docx"):
                path = path + ".docx"
            elif fmt == "txt" and not path.lower().endswith(".txt"):
                path = path + ".txt"

            try:
                import exporter as exp
                success, msg = exp.export_file(text, path, title=title)
                if success:
                    self._status.showMessage(f"已保存到 {path}", 3000)
                else:
                    QMessageBox.warning(self, "保存失败", msg)
                    self._status.showMessage(msg)
            except Exception as e:
                logger.exception("导出异常")
                QMessageBox.critical(self, "导出异常", f"{e}")
                self._status.showMessage(f"导出异常: {e}")

    # -----------------------------------------------------------------------
    # 清除 / 读取辅助方法
    # -----------------------------------------------------------------------

    def clear_left_input(self):
        self.url_edit.clear()
        self.text_input.clear()
        self.pdf_path.clear()
        self.rb_text.setChecked(True)
        self.update_input_mode()

    def clear_right_output(self):
        self.title_edit.clear()
        self.result_view.clear()
        self.orig_view.clear()
        self.gen_view.clear()

    def _get_input_text(self) -> str:
        """从当前选中的输入模式获取文本。"""
        if self.rb_url.isChecked():
            return self.url_edit.text()
        if self.rb_pdf.isChecked():
            return f"[PDF]: {self.pdf_path.text()}"
        return self.text_input.toPlainText()

    # -----------------------------------------------------------------------
    # 输入源信息 — 供后台 worker 使用
    # -----------------------------------------------------------------------

    def _get_source_info(self) -> tuple[str, str]:
        """返回 (source_type, source_value)。

        source_type ∈ {'url', 'pdf', 'text'}。
        - url   → URL 文本
        - pdf   → PDF 文件路径
        - text  → 原始文本内容
        """
        if self.rb_url.isChecked():
            return "url", self.url_edit.text().strip()
        elif self.rb_pdf.isChecked():
            return "pdf", self.pdf_path.text().strip()
        else:
            return "text", self.text_input.toPlainText().strip()

    # -----------------------------------------------------------------------
    # Worker 回调 — 改写完成 / 出错 / 进度更新
    # -----------------------------------------------------------------------

    def _on_rewrite_finished(self, title: str, body: str):
        """Worker 改写完成 → 更新 UI。"""
        # T2.5 — 隐藏 LoadingOverlay
        self.overlay.hide_event()
        self.title_edit.setText(title)
        self.result_view.setPlainText(body)
        self.btn_start.setEnabled(True)
        self.btn_start.setText("开始撰写")
        self._status.showMessage(f"改写完成 — {len(body)} 字", 5000)

    def _on_rewrite_error(self, error_msg: str):
        """Worker 改写出错 → 弹窗 + 状态栏。"""
        # T2.5 — 隐藏 LoadingOverlay
        self.overlay.hide_event()
        QMessageBox.critical(self, "改写失败", error_msg)
        self.btn_start.setEnabled(True)
        self.btn_start.setText("开始撰写")
        self._status.showMessage(f"改写失败: {error_msg}")

    def _on_cancel_overlay(self):
        """T2.5 — 用户点击 LoadingOverlay 上的取消按钮。"""
        if self._worker:
            self._worker.cancel()
        self.overlay.hide_event()
        self.btn_start.setEnabled(True)
        self.btn_start.setText("开始撰写")

    def _on_thread_finished(self):
        """线程真正退出后，清空悬空引用，防止下次访问已删除的 C++ 对象。"""
        # T2.5 — 安全网：确保 overlay 最终隐藏（即使 success/error 未调用）
        self.overlay.hide_event()
        self._thread = None
        self._worker = None

    def _on_progress(self, step: int, max_steps: int, message: str):
        """Worker 进度更新（可选）。"""
        pct = int(100 * step / max(max_steps, 1)) if max_steps else 0
        self.result_view.append(f"[{pct}%] {message}")

    # -----------------------------------------------------------------------
    # T1.7 — 参数收集方法（供 Phase-2 Prompt 拼接使用）
    # -----------------------------------------------------------------------

    def collect_parameters(self) -> dict:
        """收集左侧所有用户配置，返回与 RewriteConfig 对齐的字典（15 字段）。"""
        return {
            "style":             _get_option_value("style", self.style_combo),
            "scene":             _get_option_value("scene", self.scene_combo),
            "audience":          _get_option_value("audience", self.audience_combo),
            "word_count_min":    int(self.word_count_min.text()) if self.word_count_min.text().isdigit() else DEFAULT_WORD_COUNT_MIN,
            "word_count_max":    int(self.word_count_max.text()) if self.word_count_max.text().isdigit() else DEFAULT_WORD_COUNT_MAX,
            "length_strategy":   _get_option_value("length_strategy", self.length_combo),
            "strict_word_limit": self.cb_strict_word_limit.isChecked(),
            "language":          _map_language(self.language_combo.currentText()),
            "tone":              _get_option_value("tone", self.tone_combo),
            "keep_original_tone": False,  # 后续可扩展为 checkbox
            "structure_mode":    _get_option_value("structure_mode", self.struct_combo),
            "auto_title":        self.cb_auto_title.isChecked(),
            "forbid_new_facts":  self.cb_forbid_new_facts.isChecked(),
            "show_source":       self.cb_show_source.isChecked(),
            "special_remarks":   self.special_remarks.toPlainText().strip() if hasattr(self, "special_remarks") else "",
        }
    # -----------------------------------------------------------------------
    # T1.8 — 优雅退出：停止后台线程后再关闭窗口
    # -----------------------------------------------------------------------

    def closeEvent(self, event):
        """窗口关闭时取消后台任务，等待线程结束。"""
        if self._thread and self._thread.isRunning():
            logger.info("检测到正在运行的改写线程，执行清理…")
            if self._worker:
                self._worker.cancel()
            # 最多等 5 秒
            self._thread.wait(5000)
            if self._thread.isRunning():
                # 强制终止（防止 hang）
                logger.warning("线程未在 5 秒内退出，强制终止。")
                self._thread.requestInterruption()
                self._thread.quit()
                self._thread.wait(2000)

        event.accept()

    # -----------------------------------------------------------------------
    # T1.9 — 窗口居中
    # -----------------------------------------------------------------------

    def _center_on_screen(self):
        """将窗口居中显示在屏幕中间。"""
        screen = QApplication.primaryScreen().geometry()
        geo = self.frameGeometry()
        center_point = screen.center()
        geo.moveCenter(center_point)
        self.move(geo.topLeft())


# ---------------------------------------------------------------------------
# 入口点
# ---------------------------------------------------------------------------

def main() -> None:
    # HiDPI 配置必须在 QApplication 创建之前设置
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    w = MainWindow()
    w._center_on_screen()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
