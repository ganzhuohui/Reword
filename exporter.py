"""
proj-publisher — 导出模块

支持 TXT 和 DOCX 两种格式的保存。
使用标题生成文件名，提供统一入口 export_file()。
"""

from __future__ import annotations

import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def save_txt(title: str, body: str, filepath: str) -> Tuple[bool, str]:
    """
    将标题和正文保存为 .txt 文件。
    
    Returns
    -------
    (True, "成功消息") 或 (False, "错误消息")
    """
    try:
        content = ""
        if title:
            content += f"标题：{title}\n\n"
        if body:
            content += f"{body}"
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"TXT 导出成功: {filepath}")
        return True, f"文件已保存: {filepath}"
    except OSError as e:
        logger.error(f"TXT 写入失败: {e}")
        return False, f"TXT 写入失败: {e}"


def save_docx(title: str, body: str, filepath: str) -> Tuple[bool, str]:
    """
    将标题和正文保存为 .docx 文件（使用 python-docx）。
    
    Returns
    -------
    (True, "成功消息") 或 (False, "错误消息")
    """
    try:
        from docx import Document  # type: ignore
    except ImportError as e:
        msg = f"python-docx 未安装: {e}"
        logger.error(msg)
        return False, msg

    try:
        doc = Document()

        if title:
            doc.add_heading(title, level=1)

        # 按段落写入正文
        if body:
            paragraphs = body.split("\n")
            for para in paragraphs:
                line = para.strip()
                if not line:
                    continue
                doc.add_paragraph(line)

        doc.save(filepath)
        logger.info(f"DOCX 导出成功: {filepath}")
        return True, f"文件已保存: {filepath}"
    except Exception as e:
        logger.error(f"DOCX 写入失败: {e}")
        return False, f"DOCX 写入失败: {e}"


def export_file(
    body: str,
    filepath: str,
    title: str = "",
    fmt: str = "txt",  # "txt" or "docx"
) -> Tuple[bool, str]:
    """
    统一导出入口。
    
    Parameters
    ----------
    body : str — 改写后的正文内容。
    filepath : str — 目标文件完整路径（含扩展名）。
    title : str — 文章标题（可选，默认取空字符串）。
    fmt : str — 导出格式，"txt" 或 "docx"。
    
    Returns
    -------
    (True, "成功消息") 或 (False, "错误消息")
    """
    fmt_lower = fmt.lower().lstrip(".")
    if fmt_lower in ("docx", "doc"):
        return save_docx(title, body, filepath)
    else:
        return save_txt(title, body, filepath)
