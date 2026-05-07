"""
Routing Prompt Module

This module constructs the prompt for the pre-routing layer LLM call.
It combines query rewriting, task classification, and entity resolution
into a single structured output.

Author: Scholar Compass Team
Date: 2025-04-20
"""

from typing import List, Dict, Any, Optional


def _get_brief_schema() -> str:
    """返回简化的图数据库 schema"""
    return """【Neo4j 图数据库 Schema】

节点类型：
- Author（学者）：id, display_name
- Paper（论文）：id, title, publication_year, cited_by_count, fwci
- Source（发表场所）：id, display_name
- User（用户）、Session（会话）、Message（消息）

关系类型：
- (Author)-[:AUTHORED]->(Paper)：学者发表论著
- (Paper)-[:REFERENCES]->(Paper)：论文引用关系
- (User)-[:HAS_SESSION]->(Session)-[:HAS_MESSAGE]->(Message)：对话历史

重要约束：
- 作者姓名使用精确匹配：a.display_name = $name
- 所有查询必须包含 LIMIT 子句（防止性能问题）
- 数据库只包含 Georgia Tech 的学者
- Paper 节点包含 abstract，支持向量语义检索

"""


def _get_task_type_definitions() -> str:
    """返回任务类型定义"""
    return """【任务类型定义】

1. **FACTUAL_QUERY**（事实查询）
   特征：有明确实体+明确属性的查询，可用模板 Cypher 直接解决
   关键词：查询、查找、显示、列出、介绍、多少篇、哪些
   示例："Yao Xie 的高被引论文"、"张三的 email"、"XX 发过几篇论文"
   路径：直接调用 factual_query 工具，使用模板 Cypher
   query_shape: single_lookup（默认）, comparison（对比）, aggregation（统计）, multi_hop（多跳）

2. **SEMANTIC_SEARCH**（语义检索）
   特征：需要语义匹配，没有明确实体名
   关键词：找、搜索、推荐、有哪些、谁在做
   示例："找做联邦学习的老师"、"推荐做多模态的组"
   路径：调用 semantic_search 工具，基于主题匹配

3. **ANALYSIS**（分析推理）
   特征：需要对已知实体做深度分析或推理
   关键词：变化、趋势、演进、契合度、适合、分析
   示例："XX 研究方向变化"、"XX 和我方向契合度"、"XX 的合作网络趋势"
   路径：调用 analyze_author_trajectory 或 analyze_collaboration

4. **COMPLEX**（复合任务）
   特征：涉及多实体多步骤，需要 ReAct 循环
   关键词：找3个、对比、综合、分别、然后
   示例："帮我找 3 个做 X 方向的老师并对比"
   路径：进入完整 ReAct 循环，多工具协作

5. **CLARIFICATION_NEEDED**（需要澄清）
   特征：信息不足或存在歧义，需要反问用户
   示例："他怎么样？"（无前文）、"那个老师"（多个候选且无法判断）
   ambiguity_reason:
     - multiple_author_candidates: 重名，需用户选择
     - missing_context: 代词无前文
     - vague_topic: 话题过泛
     - missing_info: 缺少关键信息
   路径：返回反问内容，等待用户澄清"""


def _get_coreference_resolution_rules() -> str:
    """返回指代消解规则"""
    return """【指代消解规则】

当前年份：2026

1. 代词替换：
   - "他/她/这位老师/那位学者" → 从历史中提取的具体人名
   - "这三位/那两个" → 历史中提到的实体列表
   - "这个方向/那个领域" → 历史中提到的研究主题

2. 时间表达标准化：
   - "最近" = 2024-2026
   - "近几年" = 2022-2026
   - "早期" = 作者第一篇论文年份到第一篇+3年
   - "去年" = 2025
   - "今年" = 2026
   - "前年" = 2024

3. 模糊指代处理：
   - "这种论文/这类研究" → 附加研究主题关键词
   - "这所学校/这个学院" → Georgia Tech（数据库只有这个学校）

4. 无前文处理：
   - 如果代词在历史中找不到对应实体，将 task_type 设为 CLARIFICATION_NEEDED
   - ambiguity_reason 设为 missing_context"""


def _get_available_tools() -> str:
    """返回可用工具列表"""
    return """【可用工具列表】

- factual_query: 事实查询（作者、论文、领域信息，支持模板 Cypher）
- semantic_search: 语义搜索（基于主题查找学者）
- analyze_author_trajectory: 研究轨迹分析（研究方向演化、时间序列分析）
- analyze_collaboration: 合作网络分析（合作者、社区发现）
- compare_scholars: 学者对比（多维度指标对比）
- recommend_advisors: 导师推荐（基于研究兴趣匹配）
- generate_report: 报告生成（汇总分析结果）"""


def _get_few_shot_examples() -> str:
    """返回 Few-shot 示例（10 个）"""
    return """【Few-Shot 示例】

示例 1 - 直接事实查询（FACTUAL_QUERY）：
输入：
{
  "current_query": "Yao Xie 的 top 5 高被引论文是什么？",
  "history": []
}
输出：
```json
{
  "resolved_query": "查找 Yao Xie 的 Top 5 高被引论文",
  "task_type": "FACTUAL_QUERY",
  "entities": {
    "authors": [{"name": "Yao Xie", "author_id": null, "confidence": 1.0, "candidates": []}],
    "unresolved_authors": [],
    "topics": [],
    "time_range": null,
    "paper_ids": [],
    "venues": []
  },
  "suggested_tools": ["factual_query"],
  "reasoning": "查询单个学者的高被引论文，明确实体和属性，使用模板 Cypher",
  "clarification_question": null,
  "ambiguity_reason": null,
  "routing_confidence": "high",
  "has_coreference": false,
  "query_shape": "single_lookup"
}
```

示例 2 - 有指代需要消解（FACTUAL_QUERY）：
输入：
{
  "current_query": "她发过多少篇论文？",
  "history": [
    {"role": "user", "content": "Yao Xie 是谁？"},
    {"role": "assistant", "content": "Yao Xie 是 Georgia Tech 的教授..."}
  ]
}
输出：
```json
{
  "resolved_query": "Yao Xie 总共发表了多少篇论文",
  "task_type": "FACTUAL_QUERY",
  "entities": {
    "authors": [{"name": "Yao Xie", "author_id": null, "confidence": 1.0, "candidates": [], "original_expression": "她"}],
    "unresolved_authors": [],
    "topics": [],
    "time_range": null,
    "paper_ids": [],
    "venues": []
  },
  "suggested_tools": ["factual_query"],
  "reasoning": "将'她'消解为历史对话中的 Yao Xie，查询论文总数",
  "clarification_question": null,
  "ambiguity_reason": null,
  "routing_confidence": "high",
  "has_coreference": true,
  "query_shape": "aggregation"
}
```

示例 3 - 有时间消解（ANALYSIS）：
输入：
{
  "current_query": "Kai Wang 最近几年的研究方向有变化吗？",
  "history": []
}
输出：
```json
{
  "resolved_query": "分析 Kai Wang 在 2022-2026 年期间的研究方向演化",
  "task_type": "ANALYSIS",
  "entities": {
    "authors": [{"name": "Kai Wang", "author_id": null, "confidence": 1.0, "candidates": []}],
    "unresolved_authors": [],
    "topics": [],
    "time_range": {"start_year": 2022, "end_year": 2026, "original_expression": "最近几年"},
    "paper_ids": [],
    "venues": []
  },
  "suggested_tools": ["analyze_author_trajectory"],
  "reasoning": "将'最近几年'解析为 2022-2026，研究方向演化属于分析任务",
  "clarification_question": null,
  "ambiguity_reason": null,
  "routing_confidence": "high",
  "has_coreference": false,
  "query_shape": null
}
```

示例 4 - 语义模糊搜索（SEMANTIC_SEARCH）：
输入：
{
  "current_query": "找几个做联邦学习隐私保护的老师",
  "history": []
}
输出：
```json
{
  "resolved_query": "搜索研究联邦学习隐私保护的学者",
  "task_type": "SEMANTIC_SEARCH",
  "entities": {
    "authors": [],
    "unresolved_authors": [],
    "topics": ["联邦学习", "隐私保护", "Privacy", "Federated Learning"],
    "time_range": null,
    "paper_ids": [],
    "venues": []
  },
  "suggested_tools": ["semantic_search"],
  "reasoning": "无明确学者名，需要基于研究主题进行语义匹配",
  "clarification_question": null,
  "ambiguity_reason": null,
  "routing_confidence": "high",
  "has_coreference": false,
  "query_shape": null
}
```

示例 5 - 作者研究演化分析（ANALYSIS，有指代）：
输入：
{
  "current_query": "他的方向适合做多模态的学生吗？",
  "history": [
    {"role": "user", "content": "介绍一下 Tuo Zhao"},
    {"role": "assistant", "content": "Tuo Zhao 主要研究统计学、机器学习..."}
  ]
}
输出：
```json
{
  "resolved_query": "分析 Tuo Zhao 的研究方向与多模态学习的契合度",
  "task_type": "ANALYSIS",
  "entities": {
    "authors": [{"name": "Tuo Zhao", "author_id": null, "confidence": 1.0, "candidates": [], "original_expression": "他"}],
    "unresolved_authors": [],
    "topics": ["多模态", "Multimodal", "Machine Learning"],
    "time_range": null,
    "paper_ids": [],
    "venues": []
  },
  "suggested_tools": ["analyze_author_trajectory"],
  "reasoning": "将'他'消解为 Tuo Zhao，契合度分析属于 ANALYSIS 任务",
  "clarification_question": null,
  "ambiguity_reason": null,
  "routing_confidence": "high",
  "has_coreference": true,
  "query_shape": null
}
```

示例 6 - 多实体对比（COMPLEX）：
输入：
{
  "current_query": "帮我找 3 个做因果推断的老师并对比他们的研究方向",
  "history": []
}
输出：
```json
{
  "resolved_query": "搜索研究因果推断的学者并对比研究方向",
  "task_type": "COMPLEX",
  "entities": {
    "authors": [],
    "unresolved_authors": [],
    "topics": ["因果推断", "Causal Inference"],
    "time_range": null,
    "paper_ids": [],
    "venues": []
  },
  "suggested_tools": ["semantic_search", "compare_scholars"],
  "reasoning": "需要先搜索学者再对比，涉及多步骤",
  "clarification_question": null,
  "ambiguity_reason": null,
  "routing_confidence": "medium",
  "has_coreference": false,
  "query_shape": null
}
```

示例 7 - 重名待澄清（CLARIFICATION_NEEDED）：
输入：
{
  "current_query": "张三教授最近在做什么？",
  "history": []
}
输出：
```json
{
  "resolved_query": "查询张三教授的研究动态",
  "task_type": "CLARIFICATION_NEEDED",
  "entities": {
    "authors": [{"name": "张三", "author_id": null, "confidence": 0.5, "candidates": []}],
    "unresolved_authors": [],
    "topics": [],
    "time_range": null,
    "paper_ids": [],
    "venues": []
  },
  "suggested_tools": [],
  "reasoning": "'张三'是非常常见的中文姓名，存在多个同名作者，需要用户提供更多信息（研究领域）来区分",
  "clarification_question": "数据库中有多位叫'张三'的学者。请问您要找的是哪个研究领域的张三？比如：机器学习、计算机视觉、数据库等？",
  "ambiguity_reason": "multiple_author_candidates",
  "routing_confidence": "medium",
  "has_coreference": false,
  "query_shape": null
}
```

示例 8 - 代词无前文（CLARIFICATION_NEEDED）：
输入：
{
  "current_query": "他怎么样？",
  "history": []
}
输出：
```json
{
  "resolved_query": "查询学者的信息",
  "task_type": "CLARIFICATION_NEEDED",
  "entities": {
    "authors": [],
    "unresolved_authors": [],
    "topics": [],
    "time_range": null,
    "paper_ids": [],
    "venues": []
  },
  "suggested_tools": [],
  "reasoning": "用户使用代词'他'但对话历史为空，无法确定指代对象",
  "clarification_question": "请问您想了解哪位学者的情况？请提供学者的姓名。",
  "ambiguity_reason": "missing_context",
  "routing_confidence": "high",
  "has_coreference": false,
  "query_shape": null
}
```

示例 9 - 话题过泛（CLARIFICATION_NEEDED）：
输入：
{
  "current_query": "介绍一下这个领域",
  "history": [
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "你好！我可以帮你查询学术信息..."}
  ]
}
输出：
```json
{
  "resolved_query": "介绍研究领域",
  "task_type": "CLARIFICATION_NEEDED",
  "entities": {
    "authors": [],
    "unresolved_authors": [],
    "topics": [],
    "time_range": null,
    "paper_ids": [],
    "venues": []
  },
  "suggested_tools": [],
  "reasoning": "用户说'这个领域'但历史中没有提到任何具体领域，话题过于宽泛",
  "clarification_question": "请问您想了解哪个研究领域？比如：机器学习、计算机视觉、自然语言处理等？",
  "ambiguity_reason": "vague_topic",
  "routing_confidence": "high",
  "has_coreference": false,
  "query_shape": null
}
```

示例 10 - 合作网络查询（ANALYSIS，多跳）：
输入：
{
  "current_query": "Yao Xie 的合作者中，哪些人也和 Jing Liu 合作过？",
  "history": []
}
输出：
```json
{
  "resolved_query": "查找 Yao Xie 的合作者中同时也和 Jing Liu 有合作的学者",
  "task_type": "ANALYSIS",
  "entities": {
    "authors": [
      {"name": "Yao Xie", "author_id": null, "confidence": 1.0, "candidates": []},
      {"name": "Jing Liu", "author_id": null, "confidence": 1.0, "candidates": []}
    ],
    "unresolved_authors": [],
    "topics": [],
    "time_range": null,
    "paper_ids": [],
    "venues": []
  },
  "suggested_tools": ["analyze_collaboration"],
  "reasoning": "需要两跳查询（Yao Xie → 合作者 → Jing Liu），属于多跳合作网络分析",
  "clarification_question": null,
  "ambiguity_reason": null,
  "routing_confidence": "high",
  "has_coreference": false,
  "query_shape": "multi_hop"
}
```"""


def _format_conversation_history(history: List[Dict[str, str]], max_turns: int = 5) -> str:
    """
    格式化对话历史为 prompt 友好的格式。

    Args:
        history: 历史消息列表，每条包含 role 和 content
        max_turns: 最多保留多少轮对话

    Returns:
        格式化的历史字符串
    """
    if not history:
        return "<history>\n（无对话历史）\n</history>"

    # 只保留最近 max_turns 轮
    recent = history[-max_turns*2:] if len(history) > max_turns*2 else history

    formatted = ["<history>"]
    turn = 0
    i = 0
    while i < len(recent):
        # User message
        if i < len(recent) and recent[i].get("role") == "user":
            turn += 1
            formatted.append(f"[Turn {turn}]")
            user_content = recent[i].get("content", "")[:200]  # 截断到 200 字
            formatted.append(f"User: {user_content}")
            i += 1

        # Assistant message
        if i < len(recent) and recent[i].get("role") == "assistant":
            assistant_content = recent[i].get("content", "")[:200]  # 截断到 200 字
            formatted.append(f"Assistant: {assistant_content}")
            i += 1

        formatted.append("")  # 空行分隔

    formatted.append("</history>")
    return "\n".join(formatted)


def build_routing_prompt(
    current_query: str,
    history: Optional[List[Dict[str, str]]] = None,
    graph_schema: Optional[str] = None,
    resolved_entities: Optional[Dict[str, Any]] = None
) -> str:
    """
    构建路由层的完整 prompt。

    Args:
        current_query: 用户当前问题
        history: 对话历史（格式：[{"role": "user", "content": "..."}, ...]）
        graph_schema: 图数据库 schema（可选，使用默认值）
        resolved_entities: 已消歧的实体字典 {name: ResolvedAuthor}

    Returns:
        完整的 prompt 字符串
    """
    if history is None:
        history = []

    if graph_schema is None:
        graph_schema = _get_brief_schema()

    if resolved_entities is None:
        resolved_entities = {}

    formatted_history = _format_conversation_history(history)

    # 构造 session 实体提示段落
    resolved_section = ""
    if resolved_entities:
        entries = []
        for name, author in resolved_entities.items():
            author_id = (
                author.get("author_id", "")
                if isinstance(author, dict)
                else getattr(author, "author_id", "")
            )
            paper_count = (
                author.get("paper_count", "?")
                if isinstance(author, dict)
                else getattr(author, "paper_count", "?")
            )
            entries.append(
                f"- {name}（author_id: {author_id}，共 {paper_count} 篇论文）"
            )

        entity_list = chr(10).join(entries)
        resolved_section = f"""
    <session_context>
    【当前会话已确认的学者】
    用户在本轮对话中已明确选定以下学者，这是最重要的上下文信息：

    {entity_list}

    【指代消解规则 - 必须严格遵守】
    1. 如果当前 query 使用代词（"她"/"他"/"这位老师"/"这个人"）→ 解析为上述学者
    2. 如果当前 query 是追问（"研究演化"/"发了多少论文"/"合作者"等短句）→ 主语补充为上述学者
    3. 如果当前 query 没有提到任何作者名，但语义上是在追问上述学者 → resolved_query 里必须包含该学者全名
    4. 上述学者已消歧，后续查询不要再触发 CLARIFICATION_NEEDED（除非用户主动提到新的歧义名字）
    5. 如果 query 涉及上述学者，entities.authors 里必须包含该学者（带 author_id）
    </session_context>
    """

    prompt = f"""<role>
你是一个学术查询路由分析器，服务于"学术套瓷助手"系统。

你的任务是一次性完成：
1. **指代消解**：把代词（他/她/这个老师）换成具体实体名
2. **任务分类**：判断查询类型并选择合适的处理路径
3. **实体识别**：提取查询中的学者、主题、时间范围等实体

你输出的是 RoutingDecision 结构，包含消解后的查询、任务类型、实体列表等。
</role>

{graph_schema}

<task>
你的三个核心任务：

1. 指代消解：
   - 把代词（他/她/这个老师/那个学者）替换为历史对话中的具体人名
   - 把模糊时间（最近/近几年）换成年份范围
   - 把模糊指代（这个方向/那篇论文）换成具体主题

2. 任务分类：
   - 根据查询特征判断属于哪种任务类型
   - 选择合适的处理路径和工具

3. 实体识别：
   - 提取所有提到的学者姓名
   - 提取研究主题关键词
   - 解析时间范围
</task>

{_get_task_type_definitions()}

{_get_coreference_resolution_rules()}

{_get_available_tools()}

{_get_few_shot_examples()}
{resolved_section}
{formatted_history}

<current_query>
{current_query}
</current_query>

现在，请分析当前查询并输出 RoutingDecision JSON。注意：
- 必须输出有效的 JSON，不要有任何额外文字
- 所有 JSON 字段必须存在，使用默认值填充可选字段
- authors 列表中的每个对象必须有 name, confidence, candidates 字段
- task_type 必须是 5 个值之一：FACTUAL_QUERY, SEMANTIC_SEARCH, ANALYSIS, COMPLEX, CLARIFICATION_NEEDED
"""
    return prompt


# ========================================
# Testing
# ========================================

def test_build_routing_prompt():
    """Test routing prompt construction"""
    print("\n" + "="*60)
    print("Routing Prompt Test")
    print("="*60 + "\n")

    history = [
        {"role": "user", "content": "Yao Xie 是谁？"},
        {"role": "assistant", "content": "Yao Xie 是 Georgia Tech 的教授，主要研究计算机视觉和机器学习。她的论文被引用超过 5000 次。"}
    ]

    prompt = build_routing_prompt(
        current_query="她最近发了多少篇论文？",
        history=history
    )

    print(f"Prompt length: {len(prompt)} chars")
    print(f"\n{'='*60}")
    print("First 800 chars:")
    print(f"{'='*60}")
    print(prompt[:800])
    print(f"\n{'='*60}")
    print("Last 800 chars:")
    print(f"{'='*60}")
    print(prompt[-800:])

    # Test with empty history
    print(f"\n{'='*60}")
    print("Empty history test:")
    print(f"{'='*60}")
    empty_prompt = build_routing_prompt(
        current_query="Yao Xie 的论文"
    )
    print(empty_prompt[-500:])


if __name__ == "__main__":
    test_build_routing_prompt()
