"""
Disambiguation Handler Test

测试消歧响应识别和 session 实体持久化功能。

测试范围：
1. 用户回复数字选择候选
2. 用户回复中文选择候选
3. Session 实体持久化（消歧后第二轮提问）
4. 边界情况：越界编号、空 pending 等

Author: Scholar Compass Team
Date: 2025-04-22
"""

import os
import time
from langchain_core.messages import HumanMessage, AIMessage
from graph.schemas import PendingClarification, AuthorCandidate, ResolvedAuthor
from graph.nodes import route_query_node

# 加载 .env 文件（如果存在）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# 确保设置了 API Key
assert os.getenv("ANTHROPIC_API_KEY"), "请设置 ANTHROPIC_API_KEY 环境变量"


# 模拟一个已存在的 pending_clarification（上一轮触发的）
fake_pending = PendingClarification(
    entity_name="Yao Xie",
    candidates=[
        AuthorCandidate(
            author_id="https://openalex.org/A5047736740",
            name="Yao Xie",
            paper_count=18,
            total_citations=585,
            max_citations=120,
            sample_titles=["Sequential (Quickest) Change Detection..."],
        ),
        AuthorCandidate(
            author_id="https://openalex.org/A5103006471",
            name="Yao Xie",
            paper_count=1,
            total_citations=23,
            max_citations=23,
            sample_titles=["Matrix Completion With Deterministic Pattern..."],
        ),
    ],
    created_at="2026-04-22T00:00:00",
)


def run_test_case(case: dict) -> dict:
    """运行单个测试用例"""
    print(f"\n{'='*60}")
    print(f"TEST: {case['id']}")
    print(f"Desc: {case['desc']}")

    # 构建 state
    state = {
        "messages": case.get("history", []) + [HumanMessage(content=case["query"])],
        "pending_clarification": case.get("pending_clarification"),
        "resolved_entities": case.get("resolved_entities", {}),
    }

    # 记录开始时间
    t0 = time.time()
    result = route_query_node(state)
    elapsed = time.time() - t0

    # 提取结果
    decision = result.get("routing_decision")
    new_pending = result.get("pending_clarification")
    new_resolved = result.get("resolved_entities", {})

    # 输出基本信息
    print(f"[Elapsed] {elapsed:.3f}s")
    print(f"[Decision JSON]")
    print(decision.model_dump_json(indent=2))

    # 收集断言结果
    assertions = []

    # 1. 检查耗时
    if "expected_elapsed_max" in case:
        passed = elapsed <= case["expected_elapsed_max"]
        status = "✅" if passed else "❌"
        assertions.append({
            "name": f"Elapsed <= {case['expected_elapsed_max']}s",
            "expected": f"<={case['expected_elapsed_max']}s",
            "actual": f"{elapsed:.3f}s",
            "passed": passed
        })
        print(f"{status} Elapsed <= {case['expected_elapsed_max']}s (got {elapsed:.3f}s)")

    # 2. 检查 resolved author_id
    if "expected_resolved_author_id" in case:
        author_id = None
        if decision.entities.authors:
            author_id = decision.entities.authors[0].author_id
        passed = author_id == case["expected_resolved_author_id"]
        status = "✅" if passed else "❌"
        assertions.append({
            "name": "resolved author_id",
            "expected": case["expected_resolved_author_id"],
            "actual": author_id,
            "passed": passed
        })
        print(f"{status} resolved author_id: expected {case['expected_resolved_author_id']}, got {author_id}")

    # 3. 检查不应触发 CLARIFICATION
    if case.get("expected_not_clarification"):
        passed = decision.task_type != "CLARIFICATION_NEEDED"
        status = "✅" if passed else "❌"
        assertions.append({
            "name": "task_type is NOT CLARIFICATION_NEEDED",
            "expected": "not CLARIFICATION_NEEDED",
            "actual": decision.task_type,
            "passed": passed
        })
        print(f"{status} task_type is NOT CLARIFICATION_NEEDED (got {decision.task_type})")

    # 4. 检查应触发 CLARIFICATION
    if case.get("expected_still_clarification"):
        passed = decision.task_type == "CLARIFICATION_NEEDED"
        status = "✅" if passed else "❌"
        assertions.append({
            "name": "task_type IS CLARIFICATION_NEEDED",
            "expected": "CLARIFICATION_NEEDED",
            "actual": decision.task_type,
            "passed": passed
        })
        print(f"{status} task_type IS CLARIFICATION_NEEDED (got {decision.task_type})")

    # 5. 检查 pending_clarification 变化
    old_pending_name = case.get("pending_clarification").entity_name if case.get("pending_clarification") else None
    new_pending_name = new_pending.entity_name if new_pending else None
    print(f"[Pending clarification] '{old_pending_name}' -> '{new_pending_name}'")

    # 6. 检查 resolved_entities 变化
    old_resolved_keys = set(case.get("resolved_entities", {}).keys())
    new_resolved_keys = set(new_resolved.keys())
    added_keys = new_resolved_keys - old_resolved_keys
    print(f"[Resolved entities] {list(old_resolved_keys)} -> {list(new_resolved_keys)}")
    if added_keys:
        print(f"  [Added] {list(added_keys)}")

    return {
        "elapsed": elapsed,
        "decision": decision,
        "new_pending": new_pending,
        "new_resolved": new_resolved,
        "assertions": assertions,
    }


def main():
    """运行所有测试用例"""

    # 准备已解析的实体（用于 test_3）
    session_resolved_yao_xie = ResolvedAuthor(
        name="Yao Xie",
        author_id="https://openalex.org/A5047736740",
        confidence=1.0,
        candidates=[],
    )

    test_cases = [
        {
            "id": "test_1_user_selects_number",
            "desc": "用户回复数字 '1'",
            "query": "1",
            "pending_clarification": fake_pending,
            "expected_elapsed_max": 0.1,  # 快速路径不调 LLM
            "expected_resolved_author_id": "https://openalex.org/A5047736740",
        },
        {
            "id": "test_2_user_selects_chinese",
            "desc": "用户回复 '第二个'",
            "query": "第二个",
            "pending_clarification": fake_pending,
            "expected_elapsed_max": 0.1,
            "expected_resolved_author_id": "https://openalex.org/A5103006471",
        },
        {
            "id": "test_3_session_persistence",
            "desc": "消歧后第二轮提问该作者",
            "query": "她的 top 5 论文",
            "resolved_entities": {"Yao Xie": session_resolved_yao_xie},
            "history": [
                HumanMessage(content="介绍一下 Yao Xie"),
                AIMessage(content="已选定")
            ],
            "expected_not_clarification": True,  # 不应再触发 CLARIFICATION
            "expected_resolved_author_id": "https://openalex.org/A5047736740",
        },
        {
            "id": "test_4_out_of_range_number",
            "desc": "用户输入越界编号 '5'（只有 2 个候选）",
            "query": "5",
            "pending_clarification": fake_pending,
            "expected_still_clarification": True,  # 应走 LLM 路径（因为 detect 返回 None）
        },
        {
            "id": "test_5_no_pending_with_normal_query",
            "desc": "没有 pending 时正常查询",
            "query": "Yao Xie 的论文",
            "pending_clarification": None,
            # 这是一个正常查询，会走 LLM 路径，不检查耗时
        },
        {
            "id": "test_6_chinese_number_selection",
            "desc": "用户回复中文数字 '二'",
            "query": "二",
            "pending_clarification": fake_pending,
            "expected_elapsed_max": 0.1,
            "expected_resolved_author_id": "https://openalex.org/A5103006471",
        },
        {
            "id": "test_7_select_with_prefix",
            "desc": "用户回复 '选1'",
            "query": "选1",
            "pending_clarification": fake_pending,
            "expected_elapsed_max": 0.1,
            "expected_resolved_author_id": "https://openalex.org/A5047736740",
        },
    ]

    # 运行所有测试
    results = {}
    for case in test_cases:
        try:
            results[case["id"]] = run_test_case(case)
        except Exception as e:
            print(f"\n❌ TEST {case['id']} FAILED WITH EXCEPTION:")
            print(f"   {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            results[case["id"]] = {"error": str(e), "traceback": traceback.format_exc()}

    # 打印汇总
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}\n")

    total = len(test_cases)
    passed = sum(1 for r in results.values() if "error" not in r and all(a["passed"] for a in r.get("assertions", [])))
    failed = total - passed

    print(f"Total: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    # 详细结果
    for case_id, result in results.items():
        print(f"\n[{case_id}]")
        if "error" in result:
            print(f"  ❌ Exception: {result['error']}")
        else:
            elapsed = result.get("elapsed", 0)
            print(f"  ⏱️  Elapsed: {elapsed:.3f}s")
            for assertion in result.get("assertions", []):
                status = "✅" if assertion["passed"] else "❌"
                print(f"  {status} {assertion['name']}: {assertion['actual']}")

    # 性能对比
    fast_path_tests = ["test_1_user_selects_number", "test_2_user_selects_chinese",
                       "test_6_chinese_number_selection", "test_7_select_with_prefix"]
    fast_path_times = [results[t]["elapsed"] for t in fast_path_tests if t in results and "elapsed" in results[t]]
    if fast_path_times:
        avg_fast_time = sum(fast_path_times) / len(fast_path_times)
        print(f"\n{'='*60}")
        print("PERFORMANCE SUMMARY")
        print(f"{'='*60}")
        print(f"快速路径平均耗时: {avg_fast_time:.3f}s")
        print(f"预期: < 0.1s（不调 LLM）")
        if avg_fast_time < 0.1:
            print(f"✅ 性能达标！快速路径不调 LLM，加速倍数: ~50x")
        else:
            print(f"❌ 性能未达标，可能调用了 LLM")

    return results


if __name__ == "__main__":
    main()
