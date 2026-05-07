"""
Mock test for route_query_node - Demonstrates expected output format

This script shows what the RoutingDecision output looks like
without requiring actual LLM or database connections.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph.schemas import RoutingDecision, EntitySet, ResolvedAuthor, TimeRange


def mock_test_case_1_direct_factual_query():
    """
    Test Case 1: Direct factual query
    Input: "Yao Xie 的 top 5 高被引论文是什么？"
    Expected: FACTUAL_QUERY, no coreference, single_lookup
    """
    print("\n" + "="*80)
    print("测试用例 1: 直接事实查询")
    print("="*80)

    decision = RoutingDecision(
        resolved_query="查找 Yao Xie 的 Top 5 高被引论文",
        task_type="FACTUAL_QUERY",
        entities=EntitySet(
            authors=[
                ResolvedAuthor(
                    name="Yao Xie",
                    author_id=None,  # 需要数据库解析
                    confidence=1.0,
                    candidates=[],
                    original_expression=None
                )
            ],
            unresolved_authors=[],
            topics=[],
            time_range=None,
            paper_ids=[],
            venues=[]
        ),
        suggested_tools=["factual_query"],
        reasoning="查询单个学者的高被引论文，明确实体和属性，使用模板 Cypher",
        clarification_question=None,
        ambiguity_reason=None,
        routing_confidence="high",
        has_coreference=False,
        query_shape="single_lookup"
    )

    print("\n【RoutingDecision 输出】")
    print(decision.model_dump_json(indent=2))

    print("\n【验证】")
    print(f"  Task Type: {decision.task_type} (期望: FACTUAL_QUERY) ✅")
    print(f"  Has Coreference: {decision.has_coreference} (期望: False) ✅")
    print(f"  Query Shape: {decision.query_shape} (期望: single_lookup) ✅")
    print(f"  Authors Count: {len(decision.entities.authors)} (期望: 1) ✅")
    print(f"  Author Name: {decision.entities.authors[0].name} (期望: Yao Xie) ✅")


def mock_test_case_2_coreference_with_history():
    """
    Test Case 2: Coreference resolution with history
    Input History:
      - User: "Yao Xie 是谁？"
      - Assistant: "Yao Xie 是 Georgia Tech 的教授..."
    Current: "她发过多少篇论文？"
    Expected: FACTUAL_QUERY, has_coreference=True, resolved to Yao Xie
    """
    print("\n" + "="*80)
    print("测试用例 2: 指代消解（带历史）")
    print("="*80)

    decision = RoutingDecision(
        resolved_query="Yao Xie 总共发表了多少篇论文",
        task_type="FACTUAL_QUERY",
        entities=EntitySet(
            authors=[
                ResolvedAuthor(
                    name="Yao Xie",
                    author_id=None,
                    confidence=1.0,
                    candidates=[],
                    original_expression="她"  # 指代消解记录
                )
            ],
            unresolved_authors=[],
            topics=[],
            time_range=None,
            paper_ids=[],
            venues=[]
        ),
        suggested_tools=["factual_query"],
        reasoning="将'她'消解为历史对话中的 Yao Xie，查询论文总数",
        clarification_question=None,
        ambiguity_reason=None,
        routing_confidence="high",
        has_coreference=True,  # 发生了指代消解
        query_shape="aggregation"
    )

    print("\n【RoutingDecision 输出】")
    print(decision.model_dump_json(indent=2))

    print("\n【验证】")
    print(f"  Task Type: {decision.task_type} (期望: FACTUAL_QUERY) ✅")
    print(f"  Has Coreference: {decision.has_coreference} (期望: True) ✅")
    print(f"  Resolved Query: {decision.resolved_query} ✅ 包含 Yao Xie")
    print(f"  Author Original Expression: {decision.entities.authors[0].original_expression} (期望: 她) ✅")


def mock_test_case_3_clarification_needed_no_context():
    """
    Test Case 3: Clarification needed without context
    Input: "他怎么样？" (no history)
    Expected: CLARIFICATION_NEEDED, ambiguity_reason=missing_context
    """
    print("\n" + "="*80)
    print("测试用例 3: 需要澄清（无历史的代词）")
    print("="*80)

    decision = RoutingDecision(
        resolved_query="查询学者的信息",
        task_type="CLARIFICATION_NEEDED",
        entities=EntitySet(
            authors=[],
            unresolved_authors=[],
            topics=[],
            time_range=None,
            paper_ids=[],
            venues=[]
        ),
        suggested_tools=[],
        reasoning="用户使用代词'他'但对话历史为空，无法确定指代对象",
        clarification_question="请问您想了解哪位学者的情况？请提供学者的姓名。",
        ambiguity_reason="missing_context",
        routing_confidence="high",
        has_coreference=False,
        query_shape=None
    )

    print("\n【RoutingDecision 输出】")
    print(decision.model_dump_json(indent=2))

    print("\n【验证】")
    print(f"  Task Type: {decision.task_type} (期望: CLARIFICATION_NEEDED) ✅")
    print(f"  Ambiguity Reason: {decision.ambiguity_reason} (期望: missing_context) ✅")
    print(f"  Clarification Question: {decision.clarification_question} ✅ 非空")


def main():
    """Run all mock test cases"""
    print("\n" + "="*80)
    print("路由节点 Mock 测试套件（演示输出格式）")
    print("="*80)

    mock_test_case_1_direct_factual_query()
    mock_test_case_2_coreference_with_history()
    mock_test_case_3_clarification_needed_no_context()

    print("\n" + "="*80)
    print("Mock 测试完成 - 以上演示了 RoutingDecision 的预期输出格式")
    print("="*80)


if __name__ == "__main__":
    main()
