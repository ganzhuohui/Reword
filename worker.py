"""
proj-publisher — 后台工作线程

将「内容抽取 → AI改写」放在独立 QThread 中运行，
避免阻塞 UI。通过 signal 向主线程推送状态和结果。
"""

from __future__ import annotations

import logging
import os
import threading
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
    chunk = Signal(str)              # 流式输出 — 每次收到一个文本片段时发出
    finished = Signal(str, str)       # 成功：(title, body) 改写后的标题和正文
    error = Signal(str)              # 错误信息
    cancelled = Signal()             # 用户取消完成
    prompt_ready = Signal(str)       # 发送 AI 前的完整 prompt，供 UI 展示


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
        """在后台线程执行：抽取 → 流式改写。"""
        import content_extractor as ce
        import rewriter as rw

        logger.info(
            ">>> [WORKER] run() entered | thread_id=%s | pid=%d",
            threading.current_thread().name, os.getpid(),
        )

        try:
            # --- Step 1: 内容抽取 ---
            logger.info(">>> [WORKER] Step 1: content extraction starting")
            self.signals.status.emit("正在提取原文…")
            self.signals.progress.emit(1, 3, "正在提取原文…")

            logger.info(
                ">>> [WORKER] Calling ce.extract() | type=%s | value_len=%d",
                self.source_type, len(self.source_value),
            )
            result = ce.extract(self.source_type, self.source_value)
            logger.info(
                ">>> [WORKER] ce.extract() returned | text_len=%d | title=%r",
                len(result.extracted_text), result.source_title[:30] if result.source_title else None,
            )

            if not result.extracted_text.strip():
                self.signals.error.emit("提取到的内容为空，请检查输入源。")
                logger.info(">>> [WORKER] error emitted: empty content")
                return

            original_text = result.extracted_text
            detected_title = result.source_title or ""

            self.signals.status.emit(f"原文提取完成（{len(original_text)} 字）。正在改写…")
            self.signals.progress.emit(2, 3, "原文提取完成，正在AI改写…")

            # --- Step 2: AI 流式改写 ---
            t0 = time.time()
            heartbeat_interval = 10  # 每 10 秒更新一次状态栏
            last_heartbeat = t0
            collected_text = []  # 累积已收到的所有 chunk

            def _on_chunk(chunk_text: str) -> bool:
                """
                每次流式回调：发射 chunk 信号供 UI 实时更新，
                同时检查是否用户请求取消。
                返回 True 表示继续，False 表示停止。
                """
                nonlocal last_heartbeat

                collected_text.append(chunk_text)
                self.signals.chunk.emit(chunk_text)
                logger.debug(
                    ">>> [WORKER] _on_chunk received | chunk_len=%d | total_chunks=%d",
                    len(chunk_text), len(collected_text),
                )

                # 心跳提示（每 heartbeat_interval 秒更新一次状态栏）
                now = time.time()
                if now - last_heartbeat >= heartbeat_interval:
                    elapsed = int(now - t0)
                    token_count = len("".join(collected_text))
                    self.signals.status.emit(
                        f"⏳ AI改写进行中… (已等待 {elapsed} 秒，已产出 {token_count} 字)"
                    )
                    last_heartbeat = now

                # 检查取消标志
                if self.is_cancelled:
                    return False
                return True

            def _on_first_chunk(chunk_text: str) -> bool:
                """在第一次收到 chunk 时更新状态栏。"""
                self.signals.status.emit("✏️ AI正在生成内容…")
                return _on_chunk(chunk_text)

            # 用标志来区分首次回调
            first = [True]  # list 用于在闭包内修改
            def streaming_callback(chunk_text: str) -> bool:
                if first[0]:
                    first[0] = False
                    return _on_first_chunk(chunk_text)
                return _on_chunk(chunk_text)

            self.signals.status.emit("正在调用AI模型，请耐心等候…")
            self.signals.progress.emit(2, 3, "正在调用AI模型…")

            # T2.7 — 构建 prompt 并发送给 UI 展示（避免重复构造）
            logger.info(">>> [WORKER] Building prompt and emitting to UI")
            full_prompt = rw.build_prompt(original_text, self.config)
            self.signals.prompt_ready.emit(full_prompt)

            logger.info(
                ">>> [WORKER] Calling rw.call_ollama_streaming() | model=%s",
                self.config.get("model_name", "unknown"),
            )
            rewritten = rw.call_ollama_streaming(
                full_prompt, chunk_callback=streaming_callback
            )
            logger.info(
                ">>> [WORKER] call_ollama_streaming returned | rewritten_len=%d",
                len(rewritten),
            )

            elapsed_total = int(time.time() - t0)

            if self.is_cancelled:
                self.signals.status.emit("任务已取消。")
                self.signals.progress.emit(3, 3, "任务已取消。")
                self.signals.cancelled.emit()
                return

            self.signals.progress.emit(3, 3, f"改写完成！（耗时 {elapsed_total} 秒）")
            self.signals.status.emit(f"改写完成（耗时 {elapsed_total} 秒）。")

            # --- Step 3: 分离标题与正文 ---
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
