"""
LangGraph Main Graph

路由驱动架构：
1. route_query_node 作为入口节点，完成指代消解、任务分类、实体识别
2. 根据 routing_decision.task_type 路由到不同的 handler
3. 每个 handler 完成特定任务后返回，直接 END

Author: Scholar Compass Team
Date: 2025-04-22 (Step 5: 路由层集成)
"""

from typing import Literal
from langgraph.graph import StateGraph, END
from graph.state import AgentState


def route_by_task_type(state: AgentState) -> Literal["factual", "clarification", "semantic", "analysis", "fallback"]:
    """
    根据 routing_decision.task_type 决定下一个节点

    路由规则：
    - CLARIFICATION_NEEDED → clarification_handler（返回澄清问题）
    - FACTUAL_QUERY → factual_handler（调用 factual_query 工具）
    - SEMANTIC_SEARCH → semantic_handler（调用 semantic_search 工具）
    - ANALYSIS → analysis_handler（调用分析工具）
    - COMPLEX → fallback_handler（占位，待后续实现）
    """
    decision = state.get("routing_decision")
    if decision is None:
        return "fallback"

    task_type = decision.task_type

    if task_type == "CLARIFICATION_NEEDED":
        return "clarification"
    elif task_type == "FACTUAL_QUERY":
        return "factual"
    elif task_type == "SEMANTIC_SEARCH":
        return "semantic"
    elif task_type == "ANALYSIS":
        return "analysis"
    else:
        # COMPLEX 暂时走 fallback
        return "fallback"


def create_graph():
    """创建 LangGraph StateGraph（路由驱动架构）"""
    from graph.nodes import (
        route_query_node,
        clarification_handler,
        factual_handler,
        semantic_handler,
        analysis_handler,
        fallback_handler,
    )

    # 创建状态图
    workflow = StateGraph(AgentState)

    # ========================================
    # 路由层节点
    # ========================================
    workflow.add_node("route_query", route_query_node)
    workflow.add_node("factual_handler", factual_handler)
    workflow.add_node("clarification_handler", clarification_handler)
    workflow.add_node("semantic_handler", semantic_handler)
    workflow.add_node("analysis_handler", analysis_handler)
    workflow.add_node("fallback_handler", fallback_handler)

    # ========================================
    # 入口点
    # ========================================
    workflow.set_entry_point("route_query")

    # ========================================
    # 条件路由：从 route_query_node 出发
    # ========================================
    workflow.add_conditional_edges(
        "route_query",
        route_by_task_type,
        {
            "factual": "factual_handler",
            "clarification": "clarification_handler",
            "semantic": "semantic_handler",
            "analysis": "analysis_handler",
            "fallback": "fallback_handler",
        }
    )

    # ========================================
    # 所有 handler 执行完都直接 END
    # ========================================
    workflow.add_edge("factual_handler", END)
    workflow.add_edge("clarification_handler", END)
    workflow.add_edge("semantic_handler", END)
    workflow.add_edge("analysis_handler", END)
    workflow.add_edge("fallback_handler", END)

    # 编译图
    app = workflow.compile()
    return app


# 创建全局图实例
graph_app = create_graph()
