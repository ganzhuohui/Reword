"""
proj-publisher — 内容抽取模块

支持三种输入源：网页 URL、纯文本、PDF 文件。
所有入口统一为 extract(source_type, source_value) -> ExtractResult
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import requests
from lxml import html as lxml_html

# ---------------------------------------------------------------------------
# PDF 提取依赖（延迟加载，降低启动耗时）
# ---------------------------------------------------------------------------

PDF_PLUMBER_AVAILABLE = False
PYPDF2_AVAILABLE = False
try:
    import pdfplumber
    PDF_PLUMBER_AVAILABLE = True
except ImportError:
    pass

try:
    from PyPDF2 import PdfReader as PyPdfReader  # type: ignore
    PYPDF2_AVAILABLE = True
except ImportError:
    pass

if not PDF_PLUMBER_AVAILABLE and not PYPDF2_AVAILABLE:
    logging.warning(
        "未找到 pdfplumber 或 PyPDF2，PDF 提取功能不可用。"
        "请运行: pip install pdfplumber"
    )

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 数据类：抽取结果
# ---------------------------------------------------------------------------

@dataclass
class ExtractResult:
    """统一返回结构。"""
    source_type: str          # "url" / "text" / "pdf"
    source_title: str = ""    # 来源标题（URL 的网页标题等）
    extracted_text: str = ""  # 清洗后的正文文本
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# URL 抽取
# ---------------------------------------------------------------------------

def _extract_from_url(url: str) -> ExtractResult:
    """通过 requests + lxml 抓取网页正文并清洗。"""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
        )
    }

    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding

    tree = lxml_html.fromstring(resp.text)

    # 提取标题
    title_el = tree.cssselect("title")
    page_title = ""
    if title_el:
        page_title = title_el[0].text or ""
    else:
        h1s = tree.cssselect("h1")
        if h1s:
            page_title = lxml_html.tostring(
                h1s[0], encoding="unicode", strip_whitespace=True
            ).strip()

    # 尝试读取 article / main 等常见正文容器
    container_selectors = [
        "article", "main", ".post-content", ".entry-content",
        "#content", ".article-body", ".markdown-body", ".prose",
    ]
    body_text = ""
    for sel in container_selectors:
        elems = tree.cssselect(sel)
        if elems:
            body_text = elems[0].text_content("\n")
            break

    # 回退：取 <body> 文本
    if not body_text.strip():
        body = tree.cssselect("body")
        if body:
            body_text = body[0].text_content("\n")
        else:
            body_text = lxml_html.tostring(
                tree, encoding="unicode"
            ).strip()

    from utils import clean_text, truncate
    body_text = clean_text(body_text)
    body_text = truncate(body_text, max_len=50000)

    return ExtractResult(
        source_type="url",
        source_title=page_title.strip(),
        extracted_text=body_text,
        metadata={"url": url, "status_code": resp.status_code},
    )


# ---------------------------------------------------------------------------
# 纯文本抽取
# ---------------------------------------------------------------------------

def _extract_from_text(text: str) -> ExtractResult:
    """直接清洗输入文本。"""
    from utils import clean_text
    cleaned = clean_text(text)
    return ExtractResult(
        source_type="text",
        source_title="",
        extracted_text=cleaned,
    )


# ---------------------------------------------------------------------------
# PDF 抽取
# ---------------------------------------------------------------------------

def _extract_from_pdf(path: str, use_ocr: bool = False) -> ExtractResult:
    """从 PDF 提取文本。优先 pdfplumber，回退 PyPDF2。"""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"PDF 文件不存在: {path}")

    filename = os.path.basename(path)
    text_parts: list[str] = []

    # 策略 1: pdfplumber
    if PDF_PLUMBER_AVAILABLE:
        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text() or ""
                    text_parts.append(t)
            return ExtractResult(
                source_type="pdf",
                source_title=filename,
                extracted_text=_join_and_clean(text_parts),
            )
        except Exception as e:
            logger.warning(f"pdfplumber 提取失败: {e}，尝试 PyPDF2 …")

    # 策略 2: PyPDF2
    if PYPDF2_AVAILABLE and not text_parts:
        try:
            reader = PyPdfReader(path)
            for page in reader.pages:
                t = page.extract_text() or ""
                text_parts.append(t)
            return ExtractResult(
                source_type="pdf",
                source_title=filename,
                extracted_text=_join_and_clean(text_parts),
            )
        except Exception as e:
            logger.warning(f"PyPDF2 提取失败: {e}")

    # OCR 预留
    if use_ocr and not text_parts:
        return ExtractResult(
            source_type="pdf",
            source_title=filename,
            extracted_text="[OCR 功能尚未接入]",
        )

    if not text_parts:
        raise RuntimeError(
            f"无法从 PDF '{path}' 中提取文本。\n"
            "请确认该 PDF 包含可复制的文本或安装 pdfplumber。"
        )

    return ExtractResult(
        source_type="pdf",
        source_title=filename,
        extracted_text=_join_and_clean(text_parts),
    )


def _join_and_clean(parts: list[str]) -> str:
    from utils import clean_text, truncate
    joined = "\n".join(parts)
    return truncate(clean_text(joined), max_len=60000)


# ---------------------------------------------------------------------------
# 统一入口
# ---------------------------------------------------------------------------

def extract(
    source_type: str,          # "url" / "text" / "pdf"
    source_value: str,         # URL地址 / 纯文本内容 / PDF本地路径
    use_ocr: bool = False,
) -> ExtractResult:
    """统一入口：根据 source_type 分发到对应的抽取逻辑。"""
    if source_type == "url":
        return _extract_from_url(source_value)
    elif source_type == "text":
        return _extract_from_text(source_value)
    elif source_type == "pdf":
        return _extract_from_pdf(source_value, use_ocr=use_ocr)
    else:
        raise ValueError(f"未知的输入源类型: {source_type}")


