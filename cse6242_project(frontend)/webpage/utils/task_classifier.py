#!/usr/bin/env python3
"""
Task Classifier Module - Query Type Detection for Prompt Routing

This module implements LLM-based task classification to route queries
to appropriate prompt templates and strategies.

Core Design:
- Classify queries into 5 types: single_lookup, comparison, aggregation, multi_hop, recommendation
- Each type gets specialized prompt template and few-shot examples in Text2Cypher
- Lightweight classification (minimal LLM call) before expensive retrieval

Benefits:
- Improved Text2Cypher accuracy (task-specific prompts)
- Better routing decisions (e.g., comparison tasks use table rendering)
- Clear separation of concerns (classification vs. execution)

Author: Scholar Compass Team
Date: 2026-04-16
"""

from langchain_openai import ChatOpenAI
import os
import json
from typing import Dict, List, Optional, Tuple
from enum import Enum


class QueryType(Enum):
    """Query type enumeration"""
    SINGLE_LOOKUP = "single_lookup"  # Single entity query: "Yao Xie 的论文"
    COMPARISON = "comparison"         # Multi-entity comparison: "对比 A 和 B"
    AGGREGATION = "aggregation"       # Statistical aggregation: "平均 FWCI"
    MULTI_HOP = "multi_hop"           # Multi-hop reasoning: "A 的合作者的合作者"
    RECOMMENDATION = "recommendation" # Recommendation: "推荐合适的导师"
    UNKNOWN = "unknown"               # Unable to classify


def _get_classifier_llm():
    """Initialize LLM for task classification"""
    api_key = os.getenv("MINIMAX_API_KEY", "")
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")

    if not api_key:
        raise ValueError("MINIMAX_API_KEY not set")

    return ChatOpenAI(
        model=model,
        temperature=0,  # Deterministic classification
        top_p=1.0,  # Disable nucleus sampling
        api_key=api_key,
        base_url=base_url,
        model_kwargs={
            "seed": 42  # Fixed seed for reproducibility
        }
    )


# Global LLM instance
_classifier_llm = None


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

    # === Step 4: Remove common explanatory prefixes ===
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



def get_classifier_llm():
    """Get or create LLM instance"""
    global _classifier_llm
    if _classifier_llm is None:
        _classifier_llm = _get_classifier_llm()
    return _classifier_llm


def classify_query(
    query: str,
    referenced_scholars: List[str] = None
) -> Tuple[QueryType, Dict[str, any]]:
    """
    Classify the query type for routing and prompt selection.

    Args:
        query: User query (already rewritten by Query Rewriter)
        referenced_scholars: List of scholar names mentioned (optional, provides context)

    Returns:
        Tuple of (query_type, metadata)
        - query_type: QueryType enum
        - metadata: Dict with keys:
            - "confidence": str (high/medium/low)
            - "reasoning": str (explanation of classification)
            - "entity_count": int (number of entities mentioned)
            - "requires_aggregation": bool
            - "requires_multi_hop": bool
            - "suggested_strategy": str (recommended approach)

    Example:
        >>> query_type, meta = classify_query("对比 Yao Xie 和 Kai Wang 的论文数")
        >>> print(query_type)
        QueryType.COMPARISON
        >>> print(meta["entity_count"])
        2
        >>> print(meta["suggested_strategy"])
        "Use separate MATCH for each scholar, then UNION results for table display"
    """

    # Build system prompt
    system_prompt = """你是 Scholar Compass 系统的查询分类专家，负责分析用户查询并确定查询类型，以便系统选择最佳的检索策略和提示词模板。

【查询类型定义】

1. **single_lookup（单实体查询）**
   - 特征：查询单个学者、论文或领域的信息
   - 关键词：查询、查找、显示、列出、介绍
   - 示例："Yao Xie 的 Top 10 高被引论文"、"Machine Learning 领域的主要研究方向"
   - 策略：直接 MATCH + RETURN，简单高效

2. **comparison（对比分析）** ⭐ 重点
   - 特征：明确要求对比、比较多个实体（学者、论文、领域等）
   - 关键词：对比、比较、差异、区别、哪个更好、排名、前三/五/十
   - 示例："对比 Yao Xie 和 Kai Wang 的学术指标"、"这三位导师综合分析一下"
   - 策略：为每个实体单独 MATCH，最后 UNION 合并，不要在中间 LIMIT

3. **aggregation（聚合统计）**
   - 特征：要求统计、平均值、总数、排名等聚合计算
   - 关键词：平均、总计、统计、总数、最多、最少、排名前、分布
   - 示例："Machine Learning 领域学者的平均 FWCI"、"论文数最多的前 10 位学者"
   - 策略：使用聚合函数（count, sum, avg），注意 GROUP BY 使用

4. **multi_hop（多跳推理）**
   - 特征：需要跨越多个关系类型的推理（A 的 B 的 C）
   - 关键词：的合作者、的学生、属于哪个、关系路径、间接
   - 示例："Yao Xie 的合作者中哪些人也和 Jing Liu 合作过"、"找两次合作关系的学者"
   - 策略：使用可变长度路径 (a)-[:REL*1..N]->(b)，控制跳数避免性能问题

5. **recommendation（推荐建议）**
   - 特征：要求推荐、建议、匹配、适合性分析
   - 关键词：推荐、建议、适合、应该选择、匹配度、哪个更适合
   - 示例："推荐适合我的导师"、"哪个导师更适合做计算机视觉研究"
   - 策略：需要用户偏好信息，基于多维度匹配打分

【分类规则】
1. 优先识别 comparison（如果有"对比、比较"或明确提到多个实体）
2. 其次识别 multi_hop（如果有"的合作者、的学生"等嵌套关系）
3. 然后识别 aggregation（如果有聚合函数关键词）
4. 最后识别 recommendation（如果有推荐相关关键词）
5. 默认为 single_lookup

【输出格式】
严格按照以下 JSON 格式输出：
```json
{
  "query_type": "single_lookup|comparison|aggregation|multi_hop|recommendation",
  "confidence": "high|medium|low",
  "reasoning": "分类依据说明",
  "entity_count": 0,
  "requires_aggregation": true|false,
  "requires_multi_hop": true|false,
  "suggested_strategy": "建议的检索策略说明"
}
```

【分类示例】

示例 1 - 对比任务：
输入："对比 Yao Xie、Kai Wang、Tuo Zhao 三位学者的学术指标"
输出：
```json
{
  "query_type": "comparison",
  "confidence": "high",
  "reasoning": "明确包含'对比'关键词，涉及三个学者实体，需要并排展示多维度指标",
  "entity_count": 3,
  "requires_aggregation": true,
  "requires_multi_hop": false,
  "suggested_strategy": "MATCH (a:Author)-[:AUTHORED]->(p:Paper) WHERE ANY(n IN ['Yao Xie','Kai Wang','Tuo Zhao'] WHERE toLower(a.display_name) CONTAINS toLower(n)) WITH a, count(p) as paper_count, sum(p.cited_by_count) as total_citations RETURN a.display_name, paper_count, total_citations ORDER BY paper_count DESC"
}
```

示例 2 - 多跳查询：
输入："Yao Xie 的合作者中，哪些人也和 Jing Liu 合作过？"
输出：
```json
{
  "query_type": "multi_hop",
  "confidence": "high",
  "reasoning": "需要两次跳转：Yao Xie → 合作者 → 这些合作者是否和 Jing Liu 合作",
  "entity_count": 2,
  "requires_aggregation": false,
  "requires_multi_hop": true,
  "suggested_strategy": "MATCH (a1:Author)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(co:Author) WHERE toLower(a1.display_name) CONTAINS toLower('Yao Xie') MATCH (co)-[:AUTHORED]->(p2:Paper)<-[:AUTHORED]-(a2:Author) WHERE toLower(a2.display_name) CONTAINS toLower('Jing Liu') AND co.id <> a2.id RETURN co.display_name, count(p2) ORDER BY count(p2) DESC LIMIT 10"
}
```

示例 3 - 聚合统计：
输入："Machine Learning 领域论文数最多的前 10 位学者"
输出：
```json
{
  "query_type": "aggregation",
  "confidence": "high",
  "reasoning": "包含聚合关键词'最多'、'前10位'，需要对学者按论文数排序",
  "entity_count": 0,
  "requires_aggregation": true,
  "requires_multi_hop": false,
  "suggested_strategy": "MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield) WHERE toLower(s.display_name) CONTAINS toLower('Machine Learning') WITH a, count(p) as paper_count ORDER BY paper_count DESC LIMIT 10 RETURN a.display_name, paper_count"
}
```

示例 4 - 单实体查询：
输入："查找 Yao Xie 的 Top 5 高被引论文"
输出：
```json
{
  "query_type": "single_lookup",
  "confidence": "high",
  "reasoning": "查询单个学者的论文信息，无对比、聚合或多跳需求",
  "entity_count": 1,
  "requires_aggregation": false,
  "requires_multi_hop": false,
  "suggested_strategy": "MATCH (a:Author)-[:AUTHORED]->(p:Paper) WHERE toLower(a.display_name) CONTAINS toLower('Yao Xie') RETURN p ORDER BY p.cited_by_count DESC LIMIT 5"
}
```

示例 5 - 推荐任务：
输入："根据我的研究方向，推荐合适的导师"
输出：
```json
{
  "query_type": "recommendation",
  "confidence": "medium",
  "reasoning": "包含'推荐'关键词，但缺少用户的具体研究方向信息，可能需要额外交互",
  "entity_count": 0,
  "requires_aggregation": false,
  "requires_multi_hop": false,
  "suggested_strategy": "先询问用户的研究方向和偏好，然后基于领域匹配、导师活跃度、学生评价等多维度打分"
}
```

【重要】
- entity_count: 统计查询中提到的实体数量（学者名、领域名等）
- 如果查询类型不明确，confidence 设为 low，suggested_strategy 中说明需要进一步交互
- 必须输出有效的 JSON

【数据库Schema - 用于suggested_strategy】
- Author节点属性: id, display_name (注意：用display_name不是name!)
- Paper节点属性: id, title, publication_year, fwci, cited_by_count
- Subfield节点属性: id, display_name
- 关系: (Author)-[:AUTHORED]->(Paper), (Paper)-[:IN_SUBFIELD]->(Subfield)
- 学者名称必须用模糊匹配: WHERE toLower(a.display_name) CONTAINS toLower('姓名')"""

    # Build user message
    scholar_context = f"\n提到的学者: {', '.join(referenced_scholars or [])}" if referenced_scholars else ""
    user_message = f"""【用户查询】
{query}
{scholar_context}

请分析这个查询的类型和特征。"""

    try:
        # Call LLM
        llm = get_classifier_llm()
        completion = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ])

        response = completion.content.strip()

        # Debug: 打印原始响应
        print(f"\n[Debug] ========== TaskClassifier LLM响应 START ==========")
        print(f"响应长度: {len(response)}")
        print(f"响应内容:\n{response[:500] if len(response) > 500 else response}")
        print(f"[Debug] ========== TaskClassifier LLM响应 END ==========\n")

        # Clean up response (remove markdown and thinking content)
        response = _clean_llm_output(response)

        # Debug: 打印清理后响应
        print(f"[Debug] TaskClassifier 清理后响应长度: {len(response)}")
        print(f"清理后响应: {repr(response[:200] if len(response) > 200 else response)}")

        # Parse JSON
        result = json.loads(response)

        # Convert query_type string to enum
        query_type_str = result.get("query_type", "unknown")
        try:
            query_type = QueryType(query_type_str)
        except ValueError:
            query_type = QueryType.UNKNOWN

        # Validate required fields
        required_fields = ["query_type", "confidence", "reasoning", "entity_count",
                          "requires_aggregation", "requires_multi_hop", "suggested_strategy"]
        for field in required_fields:
            if field not in result:
                raise ValueError(f"Missing required field: {field}")

        print(f"\n{'='*60}")
        print(f"🏷️  [TaskClassifier] 查询分类")
        print(f"{'='*60}")
        print(f"查询: {query}")
        print(f"类型: {query_type.value}")
        print(f"置信度: {result['confidence']}")
        print(f"实体数: {result['entity_count']}")
        print(f"需要聚合: {result['requires_aggregation']}")
        print(f"需要多跳: {result['requires_multi_hop']}")
        print(f"建议策略: {result['suggested_strategy']}")
        print(f"{'='*60}\n")

        return query_type, result

    except json.JSONDecodeError as e:
        print(f"❌ [TaskClassifier] JSON 解析失败: {str(e)}")
        # Fallback: rule-based classification
        return _fallback_classification(query, referenced_scholars)
    except Exception as e:
        print(f"❌ [TaskClassifier] 分类失败: {str(e)}")
        # Fallback: rule-based classification
        return _fallback_classification(query, referenced_scholars)


def _fallback_classification(query: str, referenced_scholars: List[str] = None) -> Tuple[QueryType, Dict[str, any]]:
    """
    Fallback rule-based classification if LLM fails.

    Args:
        query: User query
        referenced_scholars: Referenced scholar names

    Returns:
        Tuple of (query_type, metadata)
    """
    query_lower = query.lower()

    # Count entities
    entity_count = len(referenced_scholars) if referenced_scholars else 0

    # Rule-based classification
    if any(keyword in query for keyword in ["对比", "比较", "差异", "区别", "哪个更好"]):
        query_type = QueryType.COMPARISON
        reasoning = "检测到对比关键词"
    elif any(keyword in query for keyword in ["的合作者", "的学生", "路径", "关系", "间接"]):
        query_type = QueryType.MULTI_HOP
        reasoning = "检测到多跳关系关键词"
    elif any(keyword in query for keyword in ["平均", "总计", "统计", "最多", "最少", "排名"]):
        query_type = QueryType.AGGREGATION
        reasoning = "检测到聚合统计关键词"
    elif any(keyword in query for keyword in ["推荐", "建议", "适合", "应该选择"]):
        query_type = QueryType.RECOMMENDATION
        reasoning = "检测到推荐关键词"
    else:
        query_type = QueryType.SINGLE_LOOKUP
        reasoning = "默认单实体查询"

    return query_type, {
        "query_type": query_type.value,
        "confidence": "low",
        "reasoning": f"{reasoning}（规则分类回退）",
        "entity_count": entity_count,
        "requires_aggregation": query_type in [QueryType.AGGREGATION, QueryType.COMPARISON],
        "requires_multi_hop": query_type == QueryType.MULTI_HOP,
        "suggested_strategy": "基于规则的建议策略",
        "fallback": True
    }


# ========================================
# Prompt Template Selection
# ========================================

def get_prompt_template(query_type: QueryType) -> str:
    """
    Get appropriate prompt template based on query type.

    Args:
        query_type: Classified query type

    Returns:
        Prompt template string for Text2Cypher
    """
    templates = {
        QueryType.SINGLE_LOOKUP: """你是专业的 Neo4j Cypher 生成专家。根据用户问题生成准确的 Cypher 查询。

【重要规则】
1. 只查询一个实体（学者/论文/领域）
2. 使用 LIMIT 限制结果数量（通常 10-20）
3. 使用 ORDER BY 排序返回最相关的结果
4. 学者姓名使用模糊匹配：toLower(a.display_name) CONTAINS toLower($name)

【输出格式】
只输出 Cypher 语句，不要任何解释。""",

        QueryType.COMPARISON: """你是专业的 Neo4j Cypher 生成专家，擅长生成**多实体对比查询**。

【对比查询核心规则】⭐
1. **不要在中间使用 LIMIT**！必须返回所有对比实体，让最后的 ORDER BY 排序
2. 使用 OR 连接多个实体：WHERE ... OR ... OR ...
3. 使用 IN 简化：WHERE toLower(a.display_name) IN ['a', 'b', 'c']
4. 必须为每个实体单独计算指标，最后 UNION 合并或 GROUP BY

【对比查询模板】
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)
WHERE toLower(a.display_name) IN ['学者1', '学者2', '学者3']
WITH a, count(p) as paper_count, sum(p.cited_by_count) as total_citations
RETURN a.display_name as scholar,
       paper_count,
       total_citations,
       avg(p.fwci) as avg_fwci
ORDER BY paper_count DESC
// 注意：对比任务不要在中间 LIMIT，要让所有实体都返回
```

【输出格式】
只输出 Cypher 语句，不要任何解释。""",

        QueryType.AGGREGATION: """你是专业的 Neo4j Cypher 生成专家，擅长生成**聚合统计查询**。

【聚合查询核心规则】
1. 使用聚合函数：count(), sum(), avg(), max(), min()
2. 使用 GROUP BY 对结果分组
3. 使用 ORDER BY + LIMIT 返回 Top N 结果
4. 注意处理 NULL 值（使用 coalesce()）

【聚合查询模板】
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
WHERE toLower(s.display_name) CONTAINS toLower('领域名')
WITH a, count(p) as paper_count
ORDER BY paper_count DESC
LIMIT 10
RETURN a.display_name as scholar, paper_count
```

【输出格式】
只输出 Cypher 语句，不要任何解释。""",

        QueryType.MULTI_HOP: """你是专业的 Neo4j Cypher 生成专家，擅长生成**多跳推理查询**。

【多跳查询核心规则】
1. 使用可变长度路径：(a)-[:REL*1..N]->(b)
2. 控制跳数（通常 2-3 跳），避免性能问题
3. 使用 DISTINCT 去重
4. 一定要用 LIMIT 限制结果

【多跳查询模板】
```cypher
// 找 A 的合作者中，哪些人也和 B 合作过
MATCH (a1:Author)-[:AUTHORED]->(p)<-[:AUTHORED]-(co:Author)
WHERE toLower(a1.display_name) CONTAINS toLower('A')
MATCH (co)-[:AUTHORED]->(p)<-[:AUTHORED]-(a2:Author)
WHERE toLower(a2.display_name) CONTAINS toLower('B')
  AND co.id <> a2.id
RETURN DISTINCT co.display_name as collaborator, count(p) as collaboration_strength
ORDER BY collaboration_strength DESC
LIMIT 10
```

【输出格式】
只输出 Cypher 语句，不要任何解释。""",

        QueryType.RECOMMENDATION: """你是专业的 Neo4j Cypher 生成专家，擅长生成**推荐相关查询**。

【推荐查询核心规则】
1. 基于多维度匹配（领域、活跃度、影响力）
2. 使用加权排序
3. 需要用户偏好信息（研究领域、机构等）
4. 返回推荐理由

【推荐查询模板】
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
WHERE toLower(s.display_name) CONTAINS toLower('用户感兴趣的领域')
WITH a, count(p) as paper_count,
     sum(p.cited_by_count) as total_citations,
     avg(p.fwci) as avg_fwci
WHERE paper_count >= 10  // 活跃学者
ORDER BY paper_count * 0.5 + total_citations * 0.3 + avg_fwci * 100 * 0.2 DESC
LIMIT 10
RETURN a.display_name as recommended_scholar,
       paper_count,
       total_citations,
       avg_fwci
```

【输出格式】
只输出 Cypher 语句，不要任何解释。"""
    }

    return templates.get(query_type, templates[QueryType.SINGLE_LOOKUP])


def get_few_shot_examples(query_type: QueryType) -> str:
    """
    Get few-shot examples specific to query type.

    Args:
        query_type: Classified query type

    Returns:
        Few-shot examples string
    """
    examples = {
        QueryType.COMPARISON: """
【对比查询示例】

示例 1: 三位学者对比
用户问题: 对比 Yao Xie、Kai Wang、Tuo Zhao 三位学者的学术指标
生成 Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)
WHERE toLower(a.display_name) IN ['Yao Xie', 'Kai Wang', 'Tuo Zhao']
WITH a, count(p) as paper_count,
     sum(p.cited_by_count) as total_citations,
     avg(p.fwci) as avg_fwci
RETURN a.display_name as scholar_name,
       paper_count,
       total_citations,
       avg_fwci
ORDER BY paper_count DESC
```

示例 2: 两位学者合作网络对比
用户问题: 对比 Yao Xie 和 Jing Liu 的主要合作者
生成 Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(co:Author)
WHERE toLower(a.display_name) IN ['Yao Xie', 'Jing Liu']
WITH a, co, count(p) as collaboration_count
RETURN a.display_name as scholar_name,
       collect(co.display_name)[0..5] as top_collaborators,
       collaboration_count
ORDER BY scholar_name, collaboration_count DESC
```
""",

        QueryType.MULTI_HOP: """
【多跳查询示例】

示例 1: 合作者的合作者（2跳）
用户问题: Yao Xie 的合作者中，哪些人也和 Jing Liu 合作过？
生成 Cypher:
```cypher
MATCH (a1:Author)-[:AUTHORED]->(p)<-[:AUTHORED]-(co:Author)
WHERE toLower(a1.display_name) CONTAINS toLower('Yao Xie')
MATCH (co)-[:AUTHORED]->(p)<-[:AUTHORED]-(a2:Author)
WHERE toLower(a2.display_name) CONTAINS toLower('Jing Liu')
  AND co.id <> a2.id
WITH co, count(p) as collaboration_strength
RETURN co.display_name as collaborator_name, collaboration_strength
ORDER BY collaboration_strength DESC
LIMIT 10
```

示例 2: 研究领域路径（3跳）
用户问题: 从 Yao Xie 的研究主题到 Machine Learning 领域的路径
生成 Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s1:Subfield)
WHERE toLower(a.display_name) CONTAINS toLower('Yao Xie')
MATCH (s1)-[:RELATED_TO*1..2]-(s2:Subfield)
WHERE toLower(s2.display_name) CONTAINS toLower('Machine Learning')
RETURN DISTINCT s1.display_name as start_topic,
       s2.display_name as target_topic
LIMIT 20
```
"""
    }

    return examples.get(query_type, "")


# ========================================
# Testing
# ========================================

def test_task_classifier():
    """Test task classifier with sample queries"""
    print("\n" + "="*60)
    print("Task Classifier Module Test")
    print("="*60 + "\n")

    test_queries = [
        ("对比 Yao Xie、Kai Wang、Tuo Zhao 三位学者", ["Yao Xie", "Kai Wang", "Tuo Zhao"]),
        ("Yao Xie 的 Top 10 高被引论文", ["Yao Xie"]),
        ("Yao Xie 的合作者中，哪些人也和 Jing Liu 合作过？", ["Yao Xie", "Jing Liu"]),
        ("Machine Learning 领域论文数最多的前 10 位学者", []),
        ("推荐适合做计算机视觉研究的导师", []),
    ]

    for i, (query, scholars) in enumerate(test_queries, 1):
        print(f"【测试 {i}】")
        print(f"查询: {query}")
        print(f"学者: {scholars}")

        query_type, metadata = classify_query(query, scholars)

        print(f"✅ 分类: {query_type.value}")
        print(f"   置信度: {metadata['confidence']}")
        print(f"   策略: {metadata['suggested_strategy'][:80]}...")
        print()

    print("="*60)
    print("✅ 测试完成！")
    print("="*60)


if __name__ == "__main__":
    test_task_classifier()
