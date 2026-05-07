"""
Test script for route_query_node

This script tests the routing layer with 3 representative cases.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, AIMessage
from graph.state import AgentState
from graph.nodes import route_query_node


def test_case_1_direct_factual_query():
    """
    Test Case 1: Direct factual query
    Input: "Yao Xie 的 top 5 高被引论文是什么？"
    Expected: FACTUAL_QUERY, no coreference, single_lookup
    """
    print("\n" + "="*80)
    print("测试用例 1: 直接事实查询")
    print("="*80)

    state: AgentState = {
        "messages": [
            HumanMessage(content="Yao Xie 的 top 5 高被引论文是什么？")
        ]
    }

    result = route_query_node(state)
    decision = result["routing_decision"]

    print("\n【RoutingDecision 输出】")
    print(decision.model_dump_json(indent=2))

    print("\n【验证】")
    print(f"  Task Type: {decision.task_type} (期望: FACTUAL_QUERY)")
    print(f"  Has Coreference: {decision.has_coreference} (期望: False)")
    print(f"  Query Shape: {decision.query_shape} (期望: single_lookup)")
    print(f"  Authors Count: {len(decision.entities.authors)} (期望: 1)")
    print(f"  Author Name: {decision.entities.authors[0].name if decision.entities.authors else 'N/A'} (期望: Yao Xie)")


def test_case_2_coreference_with_history():
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

    state: AgentState = {
        "messages": [
            HumanMessage(content="Yao Xie 是谁？"),
            AIMessage(content="Yao Xie 是 Georgia Tech 的教授，主要研究计算机视觉、机器学习、模式识别等领域。她的论文被引用超过 5000 次，是 IEEE Fellow。"),
            HumanMessage(content="她发过多少篇论文？")
        ]
    }

    result = route_query_node(state)
    decision = result["routing_decision"]

    print("\n【RoutingDecision 输出】")
    print(decision.model_dump_json(indent=2))

    print("\n【验证】")
    print(f"  Task Type: {decision.task_type} (期望: FACTUAL_QUERY)")
    print(f"  Has Coreference: {decision.has_coreference} (期望: True)")
    print(f"  Resolved Query: {decision.resolved_query} (期望包含: Yao Xie)")
    print(f"  Author Original Expression: {decision.entities.authors[0].original_expression if decision.entities.authors else 'N/A'} (期望: 她)")


def test_case_3_clarification_needed_no_context():
    """
    Test Case 3: Clarification needed without context
    Input: "他怎么样？" (no history)
    Expected: CLARIFICATION_NEEDED, ambiguity_reason=missing_context
    """
    print("\n" + "="*80)
    print("测试用例 3: 需要澄清（无历史的代词）")
    print("="*80)

    state: AgentState = {
        "messages": [
            HumanMessage(content="他怎么样？")
        ]
    }

    result = route_query_node(state)
    decision = result["routing_decision"]

    print("\n【RoutingDecision 输出】")
    print(decision.model_dump_json(indent=2))

    print("\n【验证】")
    print(f"  Task Type: {decision.task_type} (期望: CLARIFICATION_NEEDED)")
    print(f"  Ambiguity Reason: {decision.ambiguity_reason} (期望: missing_context)")
    print(f"  Clarification Question: {decision.clarification_question} (期望非空)")


def main():
    """Run all test cases"""
    print("\n" + "="*80)
    print("路由节点测试套件")
    print("="*80)

    try:
        test_case_1_direct_factual_query()
    except Exception as e:
        print(f"\n❌ 测试用例 1 失败: {str(e)}")
        import traceback
        traceback.print_exc()

    try:
        test_case_2_coreference_with_history()
    except Exception as e:
        print(f"\n❌ 测试用例 2 失败: {str(e)}")
        import traceback
        traceback.print_exc()

    try:
        test_case_3_clarification_needed_no_context()
    except Exception as e:
        print(f"\n❌ 测试用例 3 失败: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("测试完成")
    print("="*80)


if __name__ == "__main__":
    main()
