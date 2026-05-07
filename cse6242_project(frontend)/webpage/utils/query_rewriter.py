#!/usr/bin/env python3
"""
Query Rewriter Module - Contextual Query Reformulation for Multi-turn RAG

This module implements LLM-based query rewriting to handle:
1. Coreference resolution (e.g., "这三个导师" → "Yao Xie, Kai Wang, Tuo Zhao")
2. Context injection (convert dependent queries to self-contained ones)
3. Query simplification and clarification

Core Design:
- Use LLM to rewrite queries instead of rule-based NER
- Output self-contained queries that don't depend on conversation history
- Feed rewritten query directly to downstream modules (Text2Cypher, Agent)

Benefits:
- Clean separation of concerns (don't let every module guess references)
- Improved input quality for all downstream modules
- Better debuggability (can see what query was actually used)

Author: Scholar Compass Team
Date: 2026-04-16
"""

from langchain_openai import ChatOpenAI
import os
import json
from typing import List, Dict, Optional, Tuple


def _get_rewriter_llm():
    """Initialize LLM for query rewriting"""
    api_key = os.getenv("MINIMAX_API_KEY", "")
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")

    if not api_key:
        raise ValueError("MINIMAX_API_KEY not set")

    return ChatOpenAI(
        model=model,
        temperature=0,  # Deterministic rewriting
        top_p=1.0,  # Disable nucleus sampling
        api_key=api_key,
        base_url=base_url,
        model_kwargs={
            "seed": 42  # Fixed seed for reproducibility
        }
    )


# Global LLM instance (lazy initialization)
_rewriter_llm = None


def _clean_llm_output(text: str) -> str:
    """
    Clean LLM output by removing markdown, thinking tags, and explanatory text.

    FIXED: Enhanced to handle LLM models that output ````thinking`` tags before JSON.

    Args:
        text: Raw LLM output

    Returns:
        Cleaned text containing only JSON
    """
    import re

    if not text:
        return ""

    original_text = text
    text = text.strip()

    # === Step 1: Remove thinking/reasoning tags FIRST (before any other processing) ===
    # This handles both ```thinking...``` and <thinking>...</thinking>
    # Using non-greedy match to avoid removing too much

    # Remove <thinking>...</thinking> tags (with closing tag)
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Handle unclosed <thinking> tags (remove everything after opening tag)
    text = re.sub(r'<thinking>.*', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Remove any remaining </thinking> closing tags
    text = re.sub(r'</thinking>', '', text, flags=re.IGNORECASE)

    # Remove ```thinking...``` blocks (with closing ```)
    text = re.sub(r'```thinking\s*\n.*?\n```', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Handle unclosed ```thinking blocks (remove only up to the next line starting with ```, or up to JSON start)
    unclosed_thinking = re.search(r'```thinking\s*\n(.*?)(?=\n```|\n\{|$)', text, flags=re.DOTALL)
    if unclosed_thinking:
        # Remove only the thinking part, keep what follows
        text = text[unclosed_thinking.end():] if unclosed_thinking.end() < len(text) else text
        # Also remove the ```thinking marker itself if it remains
        text = re.sub(r'```thinking\s*\n?', '', text, flags=re.IGNORECASE)

    # Remove <reasoning>...</reasoning> tags
    text = re.sub(r'<reasoning>.*?</reasoning>', '', text, flags=re.DOTALL | re.IGNORECASE)

    # === Step 2: Extract JSON from markdown code blocks ===
    # Look for ```json ... ``` or ``` ... ``` blocks
    json_pattern = r'```(?:json)?\s*\n?(.*?)\n?```'
    json_match = re.search(json_pattern, text, re.DOTALL | re.IGNORECASE)
    if json_match:
        text = json_match.group(1).strip()
    else:
        # === Step 3: No code block found, extract JSON by finding boundaries ===
        json_start = text.find('{')
        if json_start == -1:
            # No JSON found, log and return empty
            print(f"[CleanLLM] ⚠️ No JSON found in output")
            print(f"[CleanLLM] Original (first 200 chars): {original_text[:200]}")
            return ""
        json_end = text.rfind('}')
        if json_end == -1 or json_end < json_start:
            # Incomplete JSON
            print(f"[CleanLLM] ⚠️ Incomplete JSON (missing closing brace)")
            return ""
        text = text[json_start:json_end + 1]

    # === Step 4: Remove common explanatory prefixes (if they somehow survived) ===
    prefixes_to_remove = [
        "Here is the JSON:",
        "Here is the result:",
        "Output:",
        "Result:",
        "JSON:",
        "Here's the response:",
        "The answer is:",
    ]
    for prefix in prefixes_to_remove:
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
            # Re-extract JSON after removing prefix
            json_start = text.find('{')
            if json_start != -1:
                text = text[json_start:]
            json_end = text.rfind('}')
            if json_end != -1:
                text = text[:json_end + 1]

    # === Step 5: Final validation ===
    cleaned = text.strip()
    if not cleaned or not cleaned.startswith('{'):
        print(f"[CleanLLM] ⚠️ Cleaned output doesn't start with '{{'")
        print(f"[CleanLLM] Cleaned (first 100 chars): {cleaned[:100]}")
        return ""

    return cleaned



def get_rewriter_llm():
    """Get or create LLM instance (singleton pattern)"""
    global _rewriter_llm
    if _rewriter_llm is None:
        _rewriter_llm = _get_rewriter_llm()
    return _rewriter_llm


def rewrite_query(
    current_query: str,
    conversation_history: List[Dict[str, str]] = None,
    detected_scholars: List[str] = None,
    max_history_turns: int = 5
) -> Tuple[str, Dict[str, any]]:
    """
    Rewrite user query to be self-contained using conversation context.

    Args:
        current_query: Current user message (e.g., "这三个导师综合对比一下")
        conversation_history: Recent conversation turns in format:
            [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
        detected_scholars: Pre-detected scholar names from current query (optional, for validation)
        max_history_turns: Maximum number of history turns to consider (default: 5)

    Returns:
        Tuple of (rewritten_query, metadata)
        - rewritten_query: Self-contained query (e.g., "对比 Yao Xie, Kai Wang, Tuo Zhao 三位学者")
        - metadata: Dict with keys:
            - "original_query": str
            - "referenced_scholars": List[str]
            - "query_type": str (comparison/single_lookup/aggregation/etc)
            - "has_coreference": bool
            - "reasoning": str (explanation of what was changed)

    Example:
        >>> history = [
        ...     {"role": "user", "content": "介绍一下 Yao Xie、Kai Wang、Tuo Zhao 三位老师"},
        ...     {"role": "assistant", "content": "好的，这三位都是..."}
        ... ]
        >>> rewritten, meta = rewrite_query("这三个导师综合对比一下", history)
        >>> print(rewritten)
        "综合对比分析 Yao Xie、Kai Wang、Tuo Zhao 三位学者的学术指标"
        >>> print(meta["referenced_scholars"])
        ["Yao Xie", "Kai Wang", "Tuo Zhao"]
        >>> print(meta["has_coreference"])
        True
    """

    # Build context from conversation history
    context_str = _build_context_string(conversation_history, max_history_turns)

    # Build system prompt
    system_prompt = """你是 Scholar Compass 系统的查询重写专家，负责将用户的依赖上下文的输入改写为完全自包含、独立的查询。

【核心任务】
分析用户的当前问题，结合对话历史，识别指代词（如"这三位"、"上面的"、"他"等）并替换为具体实体，输出一个不依赖任何上下文也能理解的完整查询。

【改写规则】
1. **识别指代**：找出"这X个"、"上面的"、"他/她/它"、"前者/后者"等指代词
2. **解析上下文**：从对话历史中找出指代词所指的具体实体（学者名、论文、领域等）
3. **明确查询类型**：判断是"单实体查询"、"对比分析"、"聚合统计"、"多跳查询"还是"推荐"
4. **完整输出**：将所有隐含信息显式化，输出独立查询
5. **保持原意**：不要改变用户的原始意图，只是让隐含信息显式化

【输出格式】
严格按照以下 JSON 格式输出，不要有任何额外文字：
```json
{
  "rewritten_query": "改写后的完整查询",
  "referenced_scholars": ["学者1", "学者2"],
  "query_type": "comparison|single_lookup|aggregation|multi_hop|recommendation",
  "has_coreference": true|false,
  "reasoning": "改写说明：解释哪些指代词被替换了"
}
```

【示例】

示例 1 - 对比任务指代消解：
对话历史：
User: "介绍一下 Yao Xie、Kai Wang、Tuo Zhao 三位老师"
Assistant: "好的，这三位都是 Georgia Tech 的教授..."
当前问题："这三个导师综合对比一下"
输出：
```json
{
  "rewritten_query": "综合对比分析 Yao Xie、Kai Wang、Tuo Zhao 三位学者的学术指标，包括论文数量、引用数、研究领域和学术影响力",
  "referenced_scholars": ["Yao Xie", "Kai Wang", "Tuo Zhao"],
  "query_type": "comparison",
  "has_coreference": true,
  "reasoning": "将'这三个导师'替换为历史对话中提到的三位学者：Yao Xie、Kai Wang、Tuo Zhao"
}
```

示例 2 - 单实体查询指代消解：
对话历史：
User: "Yao Xie 的主要研究方向是什么？"
Assistant: "Yao Xie 主要研究计算机视觉、模式识别..."
当前问题："他最近三年发表了多少篇论文？"
输出：
```json
{
  "rewritten_query": "Yao Xie 最近三年（2023-2025）发表了多少篇论文",
  "referenced_scholars": ["Yao Xie"],
  "query_type": "single_lookup",
  "has_coreference": true,
  "reasoning": "将'他'替换为上下文中的学者：Yao Xie；明确'最近三年'为2023-2025年"
}
```

示例 3 - 无需改写（独立查询）：
对话历史：（空）
当前问题："查找 Yao Xie 的 Top 10 高被引论文"
输出：
```json
{
  "rewritten_query": "查找 Yao Xie 的 Top 10 高被引论文",
  "referenced_scholars": ["Yao Xie"],
  "query_type": "single_lookup",
  "has_coreference": false,
  "reasoning": "查询已独立，无需改写"
}
```

示例 4 - 聚合统计任务：
对话历史：
User: "Machine Learning 领域有哪些活跃学者？"
Assistant: "根据数据库，Machine Learning 领域活跃学者包括..."
当前问题："这些人的平均 FWCI 是多少？"
输出：
```json
{
  "rewritten_query": "计算 Machine Learning 领域活跃学者的平均 FWCI（Field Weighted Citation Impact）",
  "referenced_scholars": [],
  "query_type": "aggregation",
  "has_coreference": true,
  "reasoning": "将'这些人'替换为'Machine Learning 领域活跃学者'，从聚合任务角度改写"
}
```

【重要】
- 如果无法从上下文中解析指代词，保持原查询不变，has_coreference 设为 false
- 如果对话历史为空或无关，直接返回原查询
- 必须输出有效的 JSON，不要有任何解释性文字"""

    # Build user message
    if context_str:
        user_message = f"""【对话历史】（最近 {len(conversation_history or [])} 轮）
{context_str}

【当前问题】
{current_query}

请根据对话历史改写当前问题，输出自包含的完整查询。"""
    else:
        user_message = f"""【当前问题】
{current_query}

（无对话历史）

请直接返回当前问题（无需改写）。"""

    try:
        # Call LLM
        llm = get_rewriter_llm()
        completion = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ])

        response = completion.content.strip()

        # Debug: 打印原始响应的完整内容
        print(f"\n[Debug] ========== LLM原始响应 START ==========")
        print(f"响应长度: {len(response)}")
        print(f"响应内容:\n{response[:500] if len(response) > 500 else response}")
        print(f"[Debug] ========== LLM原始响应 END ==========\n")

        # Clean up response (remove markdown and thinking content)
        response = _clean_llm_output(response)

        # Debug: 打印清理后响应
        print(f"[Debug] 清理后响应长度: {len(response)}")
        print(f"清理后响应: {repr(response[:200] if len(response) > 200 else response)}")

        # 如果清理后为空，直接返回原查询
        if not response or not response.strip():
            print(f"[Debug] ⚠️ 清理后响应为空，使用原查询")
            raise ValueError("LLM response is empty after cleaning")

        # Parse JSON
        result = json.loads(response)

        # Validate required fields
        required_fields = ["rewritten_query", "referenced_scholars", "query_type", "has_coreference", "reasoning"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")

        # Add metadata
        result["original_query"] = current_query

        print(f"\n{'='*60}")
        print(f"🔄 [QueryRewriter] 查询重写")
        print(f"{'='*60}")
        print(f"原始查询: {current_query}")
        if result["has_coreference"]:
            print(f"✅ 检测到指代，已改写")
            print(f"改写后: {result['rewritten_query']}")
            print(f"引用学者: {', '.join(result['referenced_scholars']) or '无'}")
            print(f"查询类型: {result['query_type']}")
            print(f"改写说明: {result['reasoning']}")
        else:
            print(f"ℹ️  无需改写（独立查询）")
        print(f"{'='*60}\n")

        return result["rewritten_query"], result

    except json.JSONDecodeError as e:
        print(f"❌ [QueryRewriter] JSON 解析失败: {str(e)}")
        print(f"原始响应: {response}")
        # Fallback: return original query
        return current_query, {
            "original_query": current_query,
            "rewritten_query": current_query,
            "referenced_scholars": detected_scholars or [],
            "query_type": "unknown",
            "has_coreference": False,
            "reasoning": "JSON 解析失败，使用原查询",
            "error": str(e)
        }
    except Exception as e:
        print(f"❌ [QueryRewriter] 重写失败: {str(e)}")
        # Fallback: return original query
        return current_query, {
            "original_query": current_query,
            "rewritten_query": current_query,
            "referenced_scholars": detected_scholars or [],
            "query_type": "unknown",
            "has_coreference": False,
            "reasoning": "重写失败，使用原查询",
            "error": str(e)
        }


def _build_context_string(conversation_history: List[Dict[str, str]], max_turns: int) -> str:
    """
    Build context string from conversation history.

    Args:
        conversation_history: List of message dicts with 'role' and 'content'
        max_turns: Maximum number of turns to include

    Returns:
        Formatted context string
    """
    if not conversation_history:
        return ""

    # Take last N turns
    recent_history = conversation_history[-max_turns:] if len(conversation_history) > max_turns else conversation_history

    context_parts = []
    for i, msg in enumerate(recent_history, 1):
        role = msg.get("role", "user")
        content = msg.get("content", "")
        role_label = "用户" if role == "user" else "助手"
        context_parts.append(f"{i}. {role_label}: {content}")

    return "\n".join(context_parts)


def detect_query_type(query: str) -> str:
    """
    Quick rule-based query type detection (fallback if LLM doesn't return type).

    Args:
        query: User query

    Returns:
        Query type: comparison/single_lookup/aggregation/multi_hop/recommendation
    """
    query_lower = query.lower()

    # Comparison keywords
    if any(keyword in query for keyword in ["对比", "比较", "差异", "区别", "哪个更好", "排名"]):
        return "comparison"

    # Aggregation keywords
    if any(keyword in query for keyword in ["平均", "总计", "统计", "总数", "最多", "最少", "排名"]):
        return "aggregation"

    # Multi-hop keywords
    if any(keyword in query for keyword in ["的合作者", "的学生", "属于哪个", "路径", "关系"]):
        return "multi_hop"

    # Recommendation keywords
    if any(keyword in query for keyword in ["推荐", "建议", "适合", "应该选择"]):
        return "recommendation"

    # Default: single lookup
    return "single_lookup"


# ========================================
# Convenience Functions for Integration
# ========================================

def rewrite_and_detect(
    current_query: str,
    conversation_history: List[Dict[str, str]] = None
) -> Tuple[str, List[str], str]:
    """
    Convenience function: rewrite query and extract key information.

    Args:
        current_query: Current user message
        conversation_history: Recent conversation history

    Returns:
        Tuple of (rewritten_query, referenced_scholars, query_type)
    """
    rewritten, metadata = rewrite_query(current_query, conversation_history)

    return (
        rewritten,
        metadata.get("referenced_scholars", []),
        metadata.get("query_type", "unknown")
    )


# ========================================
# Testing
# ========================================

def test_query_rewriter():
    """Test query rewriter with sample queries"""
    print("\n" + "="*60)
    print("Query Rewriter Module Test")
    print("="*60 + "\n")

    # Test 1: Coreference resolution
    print("【测试 1】指代消解")
    history1 = [
        {"role": "user", "content": "介绍一下 Yao Xie、Kai Wang、Tuo Zhao 三位老师"},
        {"role": "assistant", "content": "好的，这三位都是 Georgia Tech 的教授..."}
    ]
    query1 = "这三个导师综合对比一下"

    rewritten1, meta1 = rewrite_query(query1, history1)
    print(f"原始: {query1}")
    print(f"改写: {rewritten1}")
    print(f"学者: {meta1['referenced_scholars']}")
    print(f"类型: {meta1['query_type']}\n")

    # Test 2: Single entity reference
    print("【测试 2】单实体指代")
    history2 = [
        {"role": "user", "content": "Yao Xie 的主要研究方向是什么？"},
        {"role": "assistant", "content": "Yao Xie 主要研究计算机视觉、模式识别..."}
    ]
    query2 = "他最近三年发表了多少篇论文？"

    rewritten2, meta2 = rewrite_query(query2, history2)
    print(f"原始: {query2}")
    print(f"改写: {rewritten2}")
    print(f"学者: {meta2['referenced_scholars']}\n")

    # Test 3: No coreference (independent query)
    print("【测试 3】独立查询（无需改写）")
    query3 = "查找 Yao Xie 的 Top 10 高被引论文"

    rewritten3, meta3 = rewrite_query(query3)
    print(f"原始: {query3}")
    print(f"改写: {rewritten3}")
    print(f"是否改写: {meta3['has_coreference']}\n")

    print("="*60)
    print("✅ 测试完成！")
    print("="*60)


if __name__ == "__main__":
    test_query_rewriter()
