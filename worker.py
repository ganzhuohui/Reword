"""
proj-publisher — 后台工作线程

将「内容抽取 → AI改写」放在独立 QThread 中运行，
避免阻塞 UI。通过 signal 向主线程推送状态和结果。
"""

from __future__ import annotations

import logging
import time
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 信号定义
# ---------------------------------------------------------------------------

class WorkerSignals(QObject):
    """工作线程 → UI 的信号集。"""
    status = Signal(str)              # 状态栏消息
    progress = Signal(int, int, str)  # (current, total, message) steps
    finished = Signal(str, str)       # 成功：(title, body) 改写后的标题和正文
    error = Signal(str)              # 错误信息


# ---------------------------------------------------------------------------
# Worker 类
# ---------------------------------------------------------------------------

class RewriteWorker(QObject):
    """
    在后台线程执行完整的改写流程。

    Parameters
    ----------
    source_type : str — "url" / "text" / "pdf"
    source_value : str — URL、纯文本或 PDF 路径
    config : dict — UI collect_parameters() 返回的配置字典
    """

    def __init__(
        self,
        source_type: str,
        source_value: str,
        config: dict,
        signals: WorkerSignals | None = None,
    ):
        super().__init__()
        self.source_type = source_type
        self.source_value = source_value
        self.config = config
        self.signals = signals or WorkerSignals()
        self._cancel_requested = False

    def cancel(self):
        """请求取消当前任务。"""
        self._cancel_requested = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_requested

    # ------------------------------------------------------------------
    # 核心运行方法
    # ------------------------------------------------------------------

    def run(self):
        """在后台线程执行：抽取 → 改写。"""
        import content_extractor as ce
        import rewriter as rw

        try:
            # --- Step 1: 内容抽取 ---
            self.signals.status.emit("正在提取原文…")
            self.signals.progress.emit(1, 3, "正在提取原文…")

            result = ce.extract(self.source_type, self.source_value)

            if not result.extracted_text.strip():
                self.signals.error.emit("提取到的内容为空，请检查输入源。")
                return

            original_text = result.extracted_text
            detected_title = result.source_title or ""

            self.signals.status.emit(f"原文提取完成（{len(original_text)} 字）。正在改写…")
            self.signals.progress.emit(2, 3, "原文提取完成，正在AI改写…")

            # --- Step 2: AI 改写 — 加入心跳提示 ---
            t0 = time.time()
            heartbeat_interval = 10  # 每 10 秒更新一次状态栏
            last_heartbeat = t0

            def _heartbeat():
                """在状态栏显示已等待时间，让用户知道任务仍在进行中。"""
                nonlocal last_heartbeat
                now = time.time()
                if now - last_heartbeat >= heartbeat_interval:
                    elapsed = int(now - t0)
                    self.signals.status.emit(
                        f"⏳ AI改写进行中… (已等待 {elapsed} 秒，大模型首次加载可能较慢)"
                    )
                    last_heartbeat = now

            # 先发送心跳让用户知道调用已开始
            self.signals.status.emit("正在调用AI模型，请耐心等候…")
            _heartbeat()

            rewritten = rw.rewrite_content(original_text, self.config)

            elapsed_total = int(time.time() - t0)

            if self.is_cancelled:
                self.signals.status.emit("已取消。")
                return

            self.signals.progress.emit(3, 3, f"改写完成！（耗时 {elapsed_total} 秒）")
            self.signals.status.emit(f"改写完成（耗时 {elapsed_total} 秒）。")

            # --- Step 3: 分离标题与正文 ---
            # 尝试从改写结果中提取标题（取第一个非空行或检测 Markdown 标题）
            title = ""
            body = rewritten
            lines = rewritten.strip().split("\n", 1)
            if lines:
                first_line = lines[0].strip()
                # 如果第一行以 # 开头，去掉 markdown 标记作为标题
                heading_title = first_line.lstrip("#").strip()
                if heading_title and len(heading_title) < 80:
                    title = heading_title
                    if len(lines) > 1:
                        body = lines[1].strip()

            # 如果没有检测到标题，使用来源标题作为回退
            if not title and detected_title:
                title = detected_title

            self.signals.finished.emit(title, body)

        except Exception as e:
            logger.exception("后台改写任务异常")
            self.signals.error.emit(f"改写过程中发生错误:\n{e}")
