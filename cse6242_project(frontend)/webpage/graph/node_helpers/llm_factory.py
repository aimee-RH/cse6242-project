"""
LLM Factory Module

This module provides centralized LLM instance creation for different components.
Routing layer uses Claude Haiku for fast, cost-effective classification.
Other modules continue using MiniMax.

Author: Scholar Compass Team
Date: 2025-04-22
"""

import os
from typing import Optional

# 官方 Anthropic API URL（硬编码，不受环境变量影响）
ANTHROPIC_OFFICIAL_URL = "https://api.anthropic.com"

# 模型优先级列表（从快到慢，从便宜到贵）
MODEL_FALLBACKS = [
    "claude-haiku-4-5",             # Haiku 4.5（最快最便宜）
    "claude-haiku-4-5-20251001",    # Haiku 4.5 完整名
    "claude-sonnet-4-20250514",     # Sonnet 4（备用）
]


def _get_routing_llm():
    """
    获取路由层专用的 LLM 实例（优先 Claude Haiku，降级到 Sonnet）。

    显式指定 base_url 以绕过 ANTHROPIC_BASE_URL 环境变量可能的污染
    （某些开发环境会预设此变量指向代理服务）。

    Returns:
        ChatAnthropic: Claude LLM instance

    Raises:
        ValueError: 如果 ANTHROPIC_API_KEY 未设置或所有模型都不可用
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set (required for routing layer). "
            "Please set ANTHROPIC_API_KEY in your .env file."
        )

    from langchain_anthropic import ChatAnthropic

    # 尝试环境变量指定的模型
    preferred_model = os.getenv("ROUTING_MODEL")
    models_to_try = [preferred_model] + MODEL_FALLBACKS if preferred_model else MODEL_FALLBACKS

    for model in models_to_try:
        if not model:
            continue
        try:
            # 快速测试模型是否可用
            llm = ChatAnthropic(
                model=model,
                temperature=0,
                anthropic_api_key=api_key,
                anthropic_api_url=ANTHROPIC_OFFICIAL_URL,
                max_tokens=10,
            )
            llm.invoke("hi")
            # 模型可用，创建正式实例
            return ChatAnthropic(
                model=model,
                temperature=0,
                anthropic_api_key=api_key,
                anthropic_api_url=ANTHROPIC_OFFICIAL_URL,
                max_tokens=2048,
            )
        except Exception as e:
            # 模型不可用，尝试下一个
            if "not_found_error" in str(e) or "404" in str(e):
                continue
            else:
                raise

    raise ValueError(
        f"No available Claude model. Tried: {models_to_try}. "
        "Please check your Anthropic account permissions."
    )


def _get_text2cypher_llm():
    """
    text2cypher fallback 专用 LLM，使用 Claude Haiku。

    与 _get_routing_llm 的区别：
    - max_tokens 更大（Cypher 可能较长）
    - temperature 略高（0.1 而非 0，允许 Cypher 生成一点灵活度）

    Returns:
        ChatAnthropic: Claude Haiku LLM instance

    Raises:
        ValueError: 如果 ANTHROPIC_API_KEY 未设置
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("TEXT2CYPHER_MODEL", "claude-haiku-4-5")

    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set (required for text2cypher fallback). "
            "Please set ANTHROPIC_API_KEY in your .env file."
        )

    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=model,
        temperature=0.1,
        anthropic_api_key=api_key,
        anthropic_api_url=ANTHROPIC_OFFICIAL_URL,  # 强制官方 URL
        max_tokens=4096,
    )


def _get_routing_llm_with_fallback():
    """
    获取路由层 LLM，支持 fallback 到 MiniMax。

    如果 Claude API 不可用，自动降级到 MiniMax。

    Returns:
        ChatAnthropic or ChatOpenAI: LLM instance
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    model = os.getenv("ROUTING_MODEL", "claude-haiku-4-5-20251001")

    if api_key:
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model=model,
                temperature=0,
                anthropic_api_key=api_key,
                max_tokens=2048,
            )
        except Exception as e:
            import logging
            logging.warning(f"[llm_factory] Failed to initialize Claude: {e}, falling back to MiniMax")

    # Fallback to MiniMax
    from langchain_openai import ChatOpenAI
    api_key = os.getenv("MINIMAX_API_KEY", "")
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")

    if not api_key:
        raise ValueError("Neither ANTHROPIC_API_KEY nor MINIMAX_API_KEY is set")

    return ChatOpenAI(
        model=model,
        temperature=0,
        top_p=1.0,
        api_key=api_key,
        base_url=base_url,
        model_kwargs={"seed": 42}
    )
