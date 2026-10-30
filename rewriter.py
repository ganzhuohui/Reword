"""
proj-publisher — AI 改写模块

将左侧参数拼装为 prompt，调用 Ollama 本地模型完成改写。
若 Ollama 不可达则返回友好错误信息。
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "qwen3.6:27b"   # 可自定义替换
OLLAMA_BASE_URL = "http://localhost:11434"


# ---------------------------------------------------------------------------
# Prompt 组装
# ---------------------------------------------------------------------------

def build_prompt(original_text: str, config: dict) -> str:
    """
    根据左侧改写参数和原文，拼装完整 prompt。
    
    Parameters
    ----------
    original_text : str
        待改写的原始文本内容。
    config : dict
        来自 UI collect_parameters() 的结构化配置字典。
    
    Returns
    -------
    str — 发送给 Ollama 的完整系统+用户 prompt。
    """
    from utils import (
        STYLE_LABELS, SCENE_LABELS, AUDIENCE_LABELS,
        LANGUAGE_LABELS, TONE_LABELS, STRUCTURE_LABELS,
    )

    style = config.get("style", "news_release")
    scene = config.get("scene", "external_release")
    audience = config.get("audience", "general_public")
    lang = config.get("language", "zh")
    tone = config.get("tone", "formal")
    structure = config.get("structure_mode", "optimize")
    word_min = int(config.get("word_count_min", 300))
    word_max = int(config.get("word_count_max", 800))

    # 中文标签
    style_cn = STYLE_LABELS.get(style, "新闻稿")
    scene_cn = SCENE_LABELS.get(scene, "对外发布")
    audience_cn = AUDIENCE_LABELS.get(audience, "普通公众")
    lang_cn = LANGUAGE_LABELS.get(lang, "中文")

    # 字数策略描述
    strict_len = config.get("strict_word_limit", True)
    keep_tone = config.get("keep_original_tone", False)
    auto_title = config.get("auto_title", True)
    forbid_new_facts = config.get("forbid_new_facts", True)
    special_remarks = config.get("special_remarks", "")

    prompt = f"""你是一个专业改写助手。

任务：
根据输入原文，改写为{style_cn}风格，面向{audience_cn}的文章，该文章用于{scene_cn}。

内容要求：
1. 不得新增原文中没有的事实。{"（最高优先级）" if forbid_new_facts else ""}
2. 不得改变原文核心意思。
3. 如需引用，关键事实（时间、地点、人物、事件）必须与原文相符。
4. 不得照抄原文。与原文重复度不得超过30%。
5. 字数控制在 {word_min}-{word_max} 字。{"（严格执行）" if strict_len else "大致即可"}
6. 输出语言为{lang_cn}。
7. {"必须同时输出标题和正文。" if auto_title else "只输出正文，不要生成标题。"}
8. 可以适当补充过渡句以保证行文流畅。
{"9. " + special_remarks if special_remarks.strip() else ""}

风格约束：
- 语言风格为{TONE_LABELS.get(tone, tone)}
- 内容表达适合{audience_cn}（阅读对象）
- 使用场合为{scene_cn}
- 结构处理策略：{STRUCTURE_LABELS.get(structure, structure)}
{"- 保留原文语气特征" if keep_tone else "- 不必刻意保留原文语气"}

输出格式为： 
"""
    if auto_title:
        prompt += "标题：……\n正文：……\n"
    else:
        prompt += "正文内容直接开始。\n"

    prompt += f"\n{'='*40}\n\n[以下是要改写的原文]\n\n{original_text}"
    
    # 附加用户自定义要求（最高优先级）
    if special_remarks.strip():
        prompt += f"\n\n[以上为原文。请根据上述全部约束进行改写，特别注意用户的要求：{special_remarks}]"

    return prompt


# ---------------------------------------------------------------------------
# Ollama 调用（阻塞模式）
# ---------------------------------------------------------------------------

def call_ollama(prompt: str, model: str | None = None) -> str:
    """
    通过 HTTP API 调用本地 Ollama，返回模型生成的完整文本。
    
    Raises
    ------
    RuntimeError — 连接失败或请求异常时抛出带明确信息的错误。
    """
    import json

    try:
        import ollama
    except ImportError as e:
        raise RuntimeError(
            f"未安装 ollama Python 库。\n请运行: pip install ollama\n{e}"
        ) from e

    target_model = model or DEFAULT_MODEL

    # 默认超时 600 秒（10 分钟）— 给 27B 级别模型冷启动+推理留出充足时间
    timeout_sec = 600

    try:
        # 使用 Client 而非全局函数，可以传入超时设置
        client = ollama.Client(host=OLLAMA_BASE_URL, timeout=timeout_sec)
        resp = client.chat(
            model=target_model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.7},
        )
        # 防御性处理：某些 ollama 版本可能返回 None 或空响应
        if resp is None or not hasattr(resp, "message") or resp.message is None:
            return "[警告：模型返回了无效响应]"
        content = resp.message.content
        if not content.strip():
            return "[警告：模型返回了空内容]"
        return content.strip()
    except ConnectionError:
        raise RuntimeError(
            f"无法连接到 Ollama（{OLLAMA_BASE_URL}）。\n"
            "请确认：\n"
            "1. Ollama 服务正在运行（ollama serve）；\n"
            "2. 端口 11434 未被防火墙拦截。"
        )
    except TimeoutError:
        raise RuntimeError(
            f"Ollama 请求超时（>{timeout_sec}秒）。\n"
            "可能原因：模型太大或显存不足导致加载缓慢，\n"
            "请耐心等待后重试；或尝试使用更小的模型。"
        )
    # ollama 底层 httpx/requests 库的超时异常通常不直接继承 TimeoutError，
    # 通过名称 + 错误信息兜底捕获
    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
            raise RuntimeError(
                f"Ollama 请求超时（>{timeout_sec}秒）。\n"
                "可能原因：模型太大或显存不足导致加载缓慢，\n"
                "请耐心等待后重试；或尝试使用更小的模型。\n"
                f"底层异常: {err_msg}"
            ) from e
        raise RuntimeError(f"Ollama 请求失败: {e}") from e


# ---------------------------------------------------------------------------
# Ollama 调用（流式模式）
# ---------------------------------------------------------------------------

def call_ollama_streaming(
    prompt: str,
    model: str | None = None,
    chunk_callback=None,  # def callback(text_chunk: str) -> bool  (False=stop early)
) -> str:
    """
    流式调用 Ollama，每收到一个 token chunk 即通过 callback 推送。

    Parameters
    ----------
    prompt : str
        发送给模型的完整 prompt。
    model : str | None
        模型名称，None 则用 DEFAULT_MODEL。
    chunk_callback : callable, optional
        每次收到文本片段时调用 ``callback(chunk_text)``。
        若回调返回 ``False`` 则提前终止流式读取（用于取消）。

    Returns
    -------
    str — 所有 chunk 拼接后的完整文本。

    Raises
    ------
    RuntimeError — 连接失败或请求异常。
    """
    try:
        import ollama
    except ImportError as e:
        raise RuntimeError(
            f"未安装 ollama Python 库。\n请运行: pip install ollama\n{e}"
        ) from e

    target_model = model or DEFAULT_MODEL
    timeout_sec = 600

    try:
        client = ollama.Client(host=OLLAMA_BASE_URL, timeout=timeout_sec)
        full_text = []

        for resp in client.chat(
            model=target_model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.7},
            stream=True,
        ):
            # 每次响应可能包含 message.content
            part = ""
            if resp and hasattr(resp, "message") and resp.message is not None:
                part = getattr(resp.message, "content", "") or ""

            if part:
                full_text.append(part)
                # 推送到回调（用于 UI 实时更新）
                if chunk_callback is not None:
                    should_stop = chunk_callback(part)
                    if should_stop is False:
                        logger.info("流式回调请求提前终止。")
                        break

        result = "".join(full_text).strip()
        if not result:
            return "[警告：模型返回了空内容]"
        return result

    except ConnectionError:
        raise RuntimeError(
            f"无法连接到 Ollama（{OLLAMA_BASE_URL}）。\n"
            "请确认：\n"
            "1. Ollama 服务正在运行（ollama serve）；\n"
            "2. 端口 11434 未被防火墙拦截。"
        )
    except TimeoutError:
        raise RuntimeError(
            f"Ollama 请求超时（>{timeout_sec}秒）。\n"
            "可能原因：模型太大或显存不足导致加载缓慢，\n"
            "请耐心等待后重试；或尝试使用更小的模型。"
        )
    except Exception as e:
        err_msg = str(e)
        if "timed out" in err_msg.lower() or "timeout" in err_msg.lower():
            raise RuntimeError(
                f"Ollama 请求超时（>{timeout_sec}秒）。\n"
                "可能原因：模型太大或显存不足导致加载缓慢，\n"
                "请耐心等待后重试；或尝试使用更小的模型。\n"
                f"底层异常: {err_msg}"
            ) from e
        raise RuntimeError(f"Ollama 请求失败: {e}") from e


# ---------------------------------------------------------------------------
# 统一改写入口（阻塞）
# ---------------------------------------------------------------------------

def rewrite_content(original_text: str, config: dict) -> str:
    """
    对外公开的统一改写函数。
    
    Parameters
    ----------
    original_text : str — 待改写的原文（已清洗）。
    config : dict — UI collect_parameters() 返回的配置字典。
    
    Returns
    -------
    str — 改写后的完整输出文本（含标题和正文）。
    """
    prompt = build_prompt(original_text, config)
    return call_ollama(prompt)


# ---------------------------------------------------------------------------
# 统一改写入口（流式）
# ---------------------------------------------------------------------------

def rewrite_content_streaming(
    original_text: str,
    config: dict,
    chunk_callback=None,  # def callback(chunk_text: str) -> bool
) -> str:
    """
    流式改写：每收到一个文本片段即通过 ``chunk_callback`` 推送，
    实现实时"打字机"效果。

    Parameters
    ----------
    original_text : str — 待改写的原文。
    config : dict — UI collect_parameters() 返回的配置字典。
    chunk_callback : callable, optional — 收到片段时调用，返回 False 可提前终止。

    Returns
    -------
    str — 改写后的完整文本（或用户取消时的已产出部分）。
    """
    prompt = build_prompt(original_text, config)
    return call_ollama_streaming(prompt, chunk_callback=chunk_callback)
