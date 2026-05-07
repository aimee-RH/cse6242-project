from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage
from graph.state import AgentState
from graph.schemas import RoutingDecision, EntitySet, ResolvedAuthor, AuthorCandidate
import os
import logging

# 配置日志
logger = logging.getLogger(__name__)

# ========================================
# Routing Layer Components
# ========================================

from prompts.routing_prompt import build_routing_prompt
from graph.node_helpers.author_resolver import resolve_author_name_to_id, build_clarification_for_duplicate_authors
from graph.node_helpers.llm_factory import _get_routing_llm


def _extract_query_and_history(state: AgentState, history_limit: int = 5):
    """
    从 state 中提取当前查询和历史消息。

    Args:
        state: AgentState
        history_limit: 保留最近多少轮历史

    Returns:
        Tuple[str, List[Dict]]: (当前查询, 历史消息列表)
    """
    messages = state.get("messages", [])

    if not messages:
        return "", []

    # 提取当前查询（最后一条 HumanMessage）
    current_query = ""
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            current_query = msg.content
            break

    # 提取历史消息（排除最后一条用户消息，转换为 prompt 需要的格式）
    history = []
    for msg in messages[:-1]:  # 排除当前用户消息
        if isinstance(msg, HumanMessage):
            history.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            # 跳过包含工具调用的消息（工具结果不放进历史）
            if not (hasattr(msg, 'tool_calls') and msg.tool_calls):
                history.append({"role": "assistant", "content": msg.content})

    # 只保留最近 history_limit 轮
    if len(history) > history_limit * 2:
        history = history[-history_limit * 2:]

    return current_query, history


def _resolve_author_ids(
    decision: RoutingDecision,
    skip_existing: dict = None
) -> RoutingDecision:
    """
    对 LLM 识别出的作者做 Neo4j ID 解析。

    策略：
    1. 遍历 entities.authors
    2. 对每个作者名调用 resolve_author_name_to_id
    3. 根据结果更新 author_id 和 candidates
    4. 跳过 skip_existing 中已存在的作者（由 session 解析）

    Args:
        decision: LLM 输出的 RoutingDecision
        skip_existing: 已解析的作者字典 {name: ResolvedAuthor}，跳过这些作者的 Neo4j 查询

    Returns:
        更新后的 RoutingDecision
    """
    skip_existing = skip_existing or {}
    entities = decision.entities

    for i, author in enumerate(entities.authors):
        name = author.name

        # 如果已由 session 解析，跳过 Neo4j 查询
        if name in skip_existing:
            logger.info(f"[route_query] Skipping Neo4j resolution for '{name}' (already resolved in session)")
            continue

        original_expr = author.original_expression or name

        # 获取主题提示（用于过滤重名）
        topic_hints = entities.topics if entities.topics else None

        try:
            candidates = resolve_author_name_to_id(name, topic_hints)

            if not candidates:
                # 无匹配，移到 unresolved_authors
                entities.unresolved_authors.append(name)
                author.confidence = 0.0
                logger.info(f"[route_query] Author '{name}' not found in database")
            elif len(candidates) == 1:
                # 唯一匹配
                author.author_id = candidates[0].author_id
                author.confidence = 1.0
                author.candidates = []
                logger.info(f"[route_query] Author '{name}' resolved to {candidates[0].author_id[:40]}...")
            else:
                # 重名，保存候选列表
                author.candidates = candidates
                author.confidence = 0.5  # 不确定
                logger.info(f"[route_query] Author '{name}' has {len(candidates)} candidates")

        except Exception as e:
            logger.error(f"[route_query] Failed to resolve author '{name}': {str(e)}")
            author.confidence = 0.0

    return decision


def _check_post_resolution_ambiguity(decision: RoutingDecision) -> RoutingDecision:
    """
    在 Neo4j 解析后检查是否需要升级为 CLARIFICATION_NEEDED。

    规则：
    1. 如果任何 author.candidates 非空（重名）且原 task_type 不是 CLARIFICATION_NEEDED
       → 升级为 CLARIFICATION_NEEDED，ambiguity_reason = multiple_author_candidates
    2. 如果所有 authors 都在 unresolved_authors 中（找不到任何匹配）
       → 保持原 task_type（可能是 ANALYSIS 或 COMPLEX），让下游处理

    Args:
        decision: 已解析过 ID 的 RoutingDecision

    Returns:
        可能被升级后的 RoutingDecision
    """
    # 检查是否有重名情况
    has_duplicates = any(
        len(author.candidates) > 1
        for author in decision.entities.authors
    )

    if has_duplicates and decision.task_type != "CLARIFICATION_NEEDED":
        # 构建澄清问题
        duplicate_authors = [
            a for a in decision.entities.authors
            if len(a.candidates) > 1
        ]

        if duplicate_authors:
            author = duplicate_authors[0]
            # 使用新的消歧反问文案函数
            decision.clarification_question = build_clarification_for_duplicate_authors(
                author.name, author.candidates
            )
            decision.task_type = "CLARIFICATION_NEEDED"
            decision.ambiguity_reason = "multiple_author_candidates"
            decision.suggested_tools = []
            decision.routing_confidence = "medium"
            logger.warning(f"[route_query] Upgraded to CLARIFICATION_NEEDED due to duplicate authors: {author.name}")

    return decision


def route_query_node(state: AgentState) -> dict:
    """
    前置路由节点：指代消解 + 任务分类 + 实体识别 + Session 持久化

    一次 LLM 调用完成三件事，替代原 query_rewriter + task_classifier 的两次调用。
    新增：支持消歧响应快速路径（不调 LLM）和 session 实体持久化。

    Args:
        state: AgentState，包含 messages, resolved_entities, pending_clarification

    Returns:
        dict: {"routing_decision": RoutingDecision, "resolved_entities": dict, "pending_clarification": Optional[PendingClarification]}
    """
    from graph.node_helpers.disambiguation_handler import (
        detect_disambiguation_response,
        resolve_from_disambiguation,
        find_paper_count_in_candidate
    )
    from datetime import datetime

    print(f"\n{'='*60}")
    print(f"[route_query_node] 前置路由节点启动")
    print(f"{'='*60}\n")

    # 步骤 A: 提取当前 query 和历史（最近 5 轮）
    current_query, history = _extract_query_and_history(state, history_limit=5)

    # 获取 session 状态
    pending = state.get("pending_clarification")
    resolved_entities = dict(state.get("resolved_entities", {}))  # 复制，避免直接修改

    # ========================================
    # 新增：消歧响应快速路径（不调 LLM）
    # ========================================
    disambig_num = detect_disambiguation_response(current_query, pending)
    if disambig_num is not None:
        logger.info(f"[route_query] Detected disambiguation response: #{disambig_num}")
        resolved = resolve_from_disambiguation(disambig_num, pending)

        # 写入 session 持久化
        resolved_entities[resolved.name] = resolved

        # 构造确认信息
        paper_count = find_paper_count_in_candidate(pending, disambig_num - 1)

        decision = RoutingDecision(
            resolved_query=f"已选定 {resolved.name}，请继续提问",
            task_type="CLARIFICATION_NEEDED",  # 复用此类型，但标注是"已消歧"
            entities=EntitySet(authors=[resolved]),
            suggested_tools=[],
            reasoning=f"[DISAMBIGUATION_RESOLVED] 用户选择了候选 #{disambig_num}",
            clarification_question=(
                f"好的，已选定 {resolved.name}（共 {paper_count} 篇论文）。\n"
                f"您想了解她/他的什么信息？比如代表作、合作者、研究演化等。"
            ),
            ambiguity_reason=None,  # 已消歧
            routing_confidence="high",
            has_coreference=False,
        )

        print(f"[route_query] 快速路径：消歧响应已处理")
        print(f"  Selected: {resolved.name} ({resolved.author_id})")
        print(f"{'='*60}\n")

        return {
            "routing_decision": decision,
            "resolved_entities": resolved_entities,
            "pending_clarification": None,  # 清空已消歧的 pending
        }
    # ========================================
    # 消歧响应快速路径结束
    # ========================================

    if not current_query:
        logger.warning("[route_query] No query found in state")
        fallback_decision = RoutingDecision(
            resolved_query="",
            task_type="CLARIFICATION_NEEDED",
            entities=EntitySet(),
            suggested_tools=[],
            reasoning="未能提取到用户查询",
            clarification_question="请问有什么可以帮助您的？",
            ambiguity_reason="missing_info",
            routing_confidence="low",
            has_coreference=False,
        )
        return {"routing_decision": fallback_decision, "resolved_entities": resolved_entities, "pending_clarification": None}

    # 步骤 B: 构建 prompt 并调用 LLM（使用 structured output）
    # 注入 session 实体到 prompt
    llm = _get_routing_llm()
    structured_llm = llm.with_structured_output(RoutingDecision)

    prompt = build_routing_prompt(
        current_query=current_query,
        history=history,
        resolved_entities=resolved_entities,  # 注入 session 实体
    )

    logger.info(f"[route_query] Input query: {current_query[:100]}...")
    logger.info(f"[route_query] Prompt length: {len(prompt)} chars")
    logger.info(f"[route_query] History turns: {len([h for h in history if h['role'] == 'user'])}")
    logger.info(f"[route_query] Session entities: {list(resolved_entities.keys())}")

    try:
        decision: RoutingDecision = structured_llm.invoke(prompt)

        # 检查是否返回了 None（某些 API 可能不返回结果）
        if decision is None:
            raise ValueError("LLM returned None for structured output")

        logger.info(f"[route_query] Task type: {decision.task_type}")
        logger.info(f"[route_query] Resolved query: {decision.resolved_query[:100]}...")
        logger.info(f"[route_query] Authors found: {len(decision.entities.authors)}")
        logger.info(f"[route_query] Topics: {decision.entities.topics}")

    except Exception as e:
        logger.error(f"[route_query] LLM parsing failed: {str(e)}")
        # 重试 1 次（温度升为 0.3）
        try:
            llm_retry = _get_routing_llm()
            llm_retry.temperature = 0.3
            structured_llm_retry = llm_retry.with_structured_output(RoutingDecision)
            decision = structured_llm_retry.invoke(prompt)

            # 检查重试是否也返回了 None
            if decision is None:
                raise ValueError("Retry also returned None")

            logger.info(f"[route_query] Retry succeeded")
        except Exception as e2:
            logger.error(f"[route_query] Retry also failed: {str(e2)}")
            # Fallback decision
            fallback_decision = RoutingDecision(
                resolved_query=current_query,
                task_type="COMPLEX",  # 降级到 ReAct 路径
                entities=EntitySet(),
                suggested_tools=[],
                reasoning="路由层解析失败，降级到 ReAct 处理",
                routing_confidence="low",
                has_coreference=False,
            )
            return {
                "routing_decision": fallback_decision,
                "resolved_entities": resolved_entities,
                "pending_clarification": None
            }

    # ========================================
    # 新增：应用 session 实体到 decision
    # ========================================
    decision = _apply_session_resolved_entities(decision, resolved_entities)

    # 步骤 C: 对 LLM 识别出的作者做 Neo4j ID 解析（跳过 session 中已有的）
    decision = _resolve_author_ids(decision, skip_existing=resolved_entities)

    # 步骤 D: 如果解析后发现歧义，升级为 CLARIFICATION_NEEDED
    decision = _check_post_resolution_ambiguity(decision)

    # ========================================
    # 新增：如果本轮触发了 CLARIFICATION_NEEDED，保存 pending
    # ========================================
    new_pending = None
    if decision.task_type == "CLARIFICATION_NEEDED" and decision.ambiguity_reason == "multiple_author_candidates":
        # 找到有候选的作者
        for author in decision.entities.authors:
            if author.candidates:
                from graph.schemas import PendingClarification
                # 将 candidates 转换为 dict 以避免 Pydantic 验证问题
                # （兼容动态加载模块场景下的类型不一致）
                candidates_dict = [c.model_dump() if hasattr(c, 'model_dump') else c for c in author.candidates]
                new_pending = PendingClarification(
                    entity_name=author.name,
                    candidates=candidates_dict,
                    created_at=datetime.utcnow().isoformat(),
                )
                break

    print(f"\n{'='*60}")
    print(f"[route_query_node] 路由决策完成")
    print(f"  Task Type: {decision.task_type}")
    print(f"  Resolved Query: {decision.resolved_query[:80]}...")
    print(f"  Authors: {len(decision.entities.authors)}")
    print(f"  Suggested Tools: {decision.suggested_tools}")
    if decision.task_type == "CLARIFICATION_NEEDED":
        print(f"  Clarification: {decision.clarification_question}")
        print(f"  Ambiguity Reason: {decision.ambiguity_reason}")
    if resolved_entities:
        print(f"  Session Entities: {list(resolved_entities.keys())}")
    print(f"{'='*60}\n")

    return {
        "routing_decision": decision,
        "resolved_entities": resolved_entities,
        "pending_clarification": new_pending,
    }


def _apply_session_resolved_entities(
    decision: "RoutingDecision",
    resolved_entities: dict
) -> "RoutingDecision":
    """
    对 decision 中 LLM 识别到的作者名，如果 session 中已有消歧记录，
    直接替换为已消歧的 ResolvedAuthor，跳过 Neo4j 查询。
    """
    if not resolved_entities:
        return decision

    updated_authors = []
    for author in decision.entities.authors:
        if author.name in resolved_entities:
            logger.info(f"[route_query] Using session-resolved entity for '{author.name}'")
            session_author = resolved_entities[author.name]
            # 保留原表达式（如果是指代消解的结果）
            # Pydantic model_copy() 可能不可用，手动复制
            from graph.schemas import ResolvedAuthor
            session_author_copy = ResolvedAuthor(
                name=session_author.name,
                author_id=session_author.author_id,
                confidence=session_author.confidence,
                candidates=session_author.candidates,
                original_expression=author.original_expression,
            )
            updated_authors.append(session_author_copy)
        else:
            updated_authors.append(author)

    decision.entities.authors = updated_authors

    # 如果所有作者都从 session 解析了且没有其他歧义源，降级 task_type
    all_resolved = all(a.author_id is not None for a in updated_authors)
    if all_resolved and decision.task_type == "CLARIFICATION_NEEDED":
        if decision.ambiguity_reason == "multiple_author_candidates":
            # 之前是因为重名才触发 CLARIFICATION，现在 session 已解决，降级
            from graph.schemas import EntitySet
            decision.task_type = "FACTUAL_QUERY"  # 或根据 reasoning 重新判断
            decision.ambiguity_reason = None
            decision.clarification_question = None
            decision.reasoning = f"[SESSION_RESOLVED] " + decision.reasoning

    return decision


# ========================================
# Handler Nodes for Routing Layer
# ========================================

def clarification_handler(state: AgentState) -> dict:
    """处理 CLARIFICATION_NEEDED，直接返回 clarification_question"""
    decision = state["routing_decision"]
    reply = decision.clarification_question or decision.resolved_query

    logger.info(f"[clarification_handler] Replying with clarification")

    return {
        "messages": [AIMessage(content=reply)],
        # resolved_entities 和 pending_clarification 已由 route_query_node 更新
    }


def factual_handler(state: AgentState) -> dict:
    """处理 FACTUAL_QUERY，调用 factual_query 工具"""
    decision = state["routing_decision"]

    logger.info(f"[factual_handler] Invoking factual_query")

    try:
        # 直接导入 factual_query 工具
        from tools._new.factual_query import factual_query

        # 调用工具内部函数
        result = factual_query.func(
            resolved_query=decision.resolved_query,
            entities_json=decision.entities.model_dump_json(),
            query_shape=decision.query_shape or "single_lookup",
        )
    except Exception as e:
        logger.error(f"[factual_handler] Error: {e}", exc_info=True)
        result = f"❌ 查询出错: {e}"

    return {
        "messages": [AIMessage(content=result)],
    }


def semantic_handler(state: AgentState) -> dict:
    """处理 SEMANTIC_SEARCH，调用 semantic_search 工具或 recommend_advisors"""
    decision = state["routing_decision"]
    entities = decision.entities

    # 如果 suggested_tools 包含 recommend_advisors，调用推荐导师工具
    if "recommend_advisors" in (decision.suggested_tools or []):
        logger.info(f"[semantic_handler] Redirecting to recommend_advisors")

        try:
            from tools._new.recommend_advisors import recommend_advisors

            result = recommend_advisors.invoke({
                "resolved_query": decision.resolved_query,
                "entities_json": entities.model_dump_json(),
            })
        except Exception as e:
            logger.error(f"[semantic_handler] recommend_advisors error: {e}", exc_info=True)
            result = f"❌ 推荐导师出错: {e}"

        return {
            "messages": [AIMessage(content=result)],
        }

    # 构造工具输入
    query_text = decision.resolved_query

    # Hybrid search: 如果 entities.topics 非空，可以用它作为简单 subfield hint
    # 但需要把 topics（通常是自由文本）映射到具体 subfield 名
    # 第一版保持简单，暂不启用 subfield 过滤
    subfield_filter = None

    logger.info(f"[semantic_handler] Invoking semantic_search: '{query_text}'")

    try:
        # 直接导入 semantic_search 工具
        from tools._new.semantic_search import semantic_search

        # 调用工具内部函数
        result = semantic_search.func(
            query_text=query_text,
            top_k=10,
            subfield_filter=subfield_filter,
        )
    except Exception as e:
        logger.error(f"[semantic_handler] Error: {e}", exc_info=True)
        result = f"❌ 语义搜索出错: {e}"

    return {
        "messages": [AIMessage(content=result)],
    }


def analysis_handler(state: AgentState) -> dict:
    """处理 ANALYSIS task_type，根据 suggested_tools 分发到对应分析工具"""
    from langchain_core.messages import AIMessage
    from tools._new.analyze_author_trajectory import analyze_author_trajectory
    from tools._new.analyze_collaboration import analyze_collaboration
    from tools._new.compare_scholars import compare_scholars
    from tools._new.recommend_advisors import recommend_advisors  # 新增

    decision = state["routing_decision"]
    entities_json = decision.entities.model_dump_json()
    suggested = decision.suggested_tools or []
    query = decision.resolved_query

    logger.info(f"[analysis_handler] suggested_tools: {suggested}")

    try:
        # 推荐导师优先级最高（没有指定作者 + 有话题词）
        has_resolved_authors = any(
            a.author_id for a in decision.entities.authors
        )
        has_topics = bool(decision.entities.topics)

        if (
            "recommend_advisors" in suggested
            or (not has_resolved_authors and has_topics)
            or any(kw in query for kw in ["推荐", "recommend", "适合", "哪个老师", "哪位导师"])
        ):
            result = recommend_advisors.invoke({
                "resolved_query": query,
                "entities_json": entities_json,
            })

        elif len(decision.entities.authors) >= 2 or "compare_scholars" in suggested:
            result = compare_scholars.invoke({
                "resolved_query": query,
                "entities_json": entities_json,
            })

        elif "analyze_author_trajectory" in suggested or any(
            kw in query for kw in ["变化", "趋势", "轨迹", "演进", "trajectory"]
        ):
            result = analyze_author_trajectory.invoke({
                "resolved_query": query,
                "entities_json": entities_json,
            })

        elif "analyze_collaboration" in suggested or any(
            kw in query for kw in ["合作网络", "合作圈", "collaboration"]
        ):
            result = analyze_collaboration.invoke({
                "resolved_query": query,
                "entities_json": entities_json,
            })

        else:
            result = analyze_author_trajectory.invoke({
                "resolved_query": query,
                "entities_json": entities_json,
            })

    except Exception as e:
        logger.error(f"[analysis_handler] Error: {e}", exc_info=True)
        result = f"❌ 分析出错：{e}"

    return {"messages": [AIMessage(content=result)]}


def fallback_handler(state: AgentState) -> dict:
    """未实现的 task_type 降级处理"""
    decision = state.get("routing_decision")
    task_type = decision.task_type if decision else "UNKNOWN"

    reply = (
        f"⚠️ 您的查询被分类为 `{task_type}`，该能力将在后续迭代（步骤 4B）中实现。\n\n"
        f"当前查询已识别为: {decision.resolved_query if decision else 'N/A'}\n"
        f"暂时无法处理，请尝试转换为事实查询（如'查询 XX 的论文'、'XX 发过多少论文'）。"
    )

    logger.info(f"[fallback_handler] Task type {task_type} not yet implemented")

    return {
        "messages": [AIMessage(content=reply)],
    }


# ========================================
# Original Nodes (Preserved, 待步骤 4C 清理)
# ========================================

# ========================================
# Original Nodes (Preserved, 4C 清理后已废弃)
# ========================================

# Lazy-initialized LLM and tool bindings（已废弃）
# _llm = None
# _llm_with_tools = None

# def _get_minimax_llm():
#     """获取 MiniMax LLM 实例（延迟初始化）"""
#     [已移除 - 4C cleanup]
#     pass

# # Create tool node（已废弃）
# tool_node = ToolNode(TOOLS)

# def call_model(state: AgentState) -> AgentState:
#     """Node function that calls LLM"""
#     [已移除 - 4C cleanup]
#     pass
