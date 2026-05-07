"""
Real Data Testing for Routing Layer

Tests the routing layer with actual Neo4j data and Claude Haiku LLM.
This validates the complete flow from query input to routing decision.

Author: Scholar Compass Team
Date: 2025-04-22
"""

import os
import sys
import time
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加项目根目录到 Python 路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# 使用标准 import（__init__.py 已清理，不再有循环导入）
from graph.node_helpers.llm_factory import _get_routing_llm
from tools.neo4j_connector import get_neo4j_driver

# ========================================
# Step A: 环境验证
# ========================================

print("\n" + "="*60)
print("Step A: 环境验证")
print("="*60 + "\n")

# 检查 API Key
assert os.getenv("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not set"
print("[ENV CHECK] ANTHROPIC_API_KEY is set")

# 测试 Claude Haiku 连接
try:
    llm = _get_routing_llm()
    resp = llm.invoke("Say 'ok' if you can read this.")
    print(f"[ENV CHECK] LLM response: {resp.content}")
    model_name = getattr(resp, 'response_metadata', {}).get('model', 'unknown')
    print(f"[ENV CHECK] Model: {model_name}")
except Exception as e:
    print(f"[ENV CHECK] FAILED: {e}")
    import traceback
    traceback.print_exc()
    print("\n❌ Step A 失败，停止后续测试")
    exit(1)

# ========================================
# Step B: Neo4j 精确匹配验证
# ========================================

print("\n" + "="*60)
print("Step B: Neo4j 精确匹配验证")
print("="*60 + "\n")

try:
    driver = get_neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")
    with driver.session(database=database) as session:
        rows = list(session.run(
            "MATCH (a:Author {display_name: $name}) RETURN a.id AS id, a.display_name AS name",
            {"name": "Yao Xie"}
        ))
    print(f"[NEO4J CHECK] 精确匹配 Yao Xie 返回 {len(rows)} 条:")
    for r in rows:
        print(f"  - id: {r['id']}")
        print(f"    name: {r['name']}")

    assert len(rows) == 2, f"预期 2 条 Yao Xie，实际 {len(rows)} 条"
    print("[NEO4J CHECK] ✅ 精确匹配验证通过")

except Exception as e:
    print(f"[NEO4J CHECK] FAILED: {e}")
    import traceback
    traceback.print_exc()
    print("\n❌ Step B 失败，停止后续测试")
    exit(1)

# ========================================
# Step C: 路由测试用例
# ========================================

print("\n" + "="*60)
print("Step C: 路由测试结果")
print("="*60 + "\n")

# 导入路由节点
from graph.nodes import route_query_node

test_cases = [
    {
        "id": "test_A_duplicate_name",
        "query": "查询 Yao Xie 的 top 5 高被引论文",
        "history": [],
        "expected_task_type": "CLARIFICATION_NEEDED",
        "expected_ambiguity_reason": "multiple_author_candidates",
        "expected_candidates_count": 2,
    },
    {
        "id": "test_B_missing_context",
        "query": "他怎么样？",
        "history": [],
        "expected_task_type": "CLARIFICATION_NEEDED",
        "expected_ambiguity_reason": "missing_context",
    },
    {
        "id": "test_C_coreference_resolution",
        "query": "她发过多少论文？",
        "history": [HumanMessage(content="介绍一下 Yao Xie")],
        "expected_has_coreference": True,
    },
]

test_results = []

for case in test_cases:
    print(f"\n{'='*60}")
    print(f"TEST: {case['id']}")
    print(f"Query: {case['query']}")
    print(f"History: {case['history']}")

    t0 = time.time()
    state = {"messages": case["history"] + [HumanMessage(content=case["query"])]}
    result = route_query_node(state)
    elapsed = time.time() - t0

    decision = result["routing_decision"]
    print(f"\n[Elapsed] {elapsed:.2f}s")
    print(f"[Output]")
    print(decision.model_dump_json(indent=2))

    # Assertions
    assertions_passed = []
    assertions_failed = []

    if "expected_task_type" in case:
        if decision.task_type == case["expected_task_type"]:
            assertions_passed.append(f"✅ task_type: {decision.task_type}")
        else:
            assertions_failed.append(f"❌ task_type: 预期 {case['expected_task_type']}, 实际 {decision.task_type}")

    if "expected_ambiguity_reason" in case:
        if decision.ambiguity_reason == case["expected_ambiguity_reason"]:
            assertions_passed.append(f"✅ ambiguity_reason: {decision.ambiguity_reason}")
        else:
            assertions_failed.append(f"❌ ambiguity_reason: 预期 {case['expected_ambiguity_reason']}, 实际 {decision.ambiguity_reason}")

    if "expected_candidates_count" in case:
        actual = len(decision.entities.authors[0].candidates) if decision.entities.authors else 0
        if actual == case["expected_candidates_count"]:
            assertions_passed.append(f"✅ candidates count: {actual}")
        else:
            assertions_failed.append(f"❌ candidates count: 预期 {case['expected_candidates_count']}, 实际 {actual}")

    if "expected_has_coreference" in case:
        if decision.has_coreference == case["expected_has_coreference"]:
            assertions_passed.append(f"✅ has_coreference: {decision.has_coreference}")
        else:
            assertions_failed.append(f"❌ has_coreference: 预期 {case['expected_has_coreference']}, 实际 {decision.has_coreference}")

    print(f"\n[Assertions]")
    for a in assertions_passed:
        print(f"  {a}")
    for a in assertions_failed:
        print(f"  {a}")

    test_results.append({
        "id": case["id"],
        "elapsed": elapsed,
        "passed": len(assertions_passed),
        "failed": len(assertions_failed),
        "assertions": assertions_passed + assertions_failed
    })

# ========================================
# 汇总
# ========================================

print("\n" + "="*60)
print("测试汇总")
print("="*60 + "\n")

total_passed = sum(r["passed"] for r in test_results)
total_failed = sum(r["failed"] for r in test_results)

for r in test_results:
    status = "✅ PASS" if r["failed"] == 0 else "❌ FAIL"
    print(f"{status} {r['id']} ({r['elapsed']:.2f}s) - {r['passed']} passed, {r['failed']} failed")

print("\n" + "="*60)
if total_failed == 0:
    print("🎉 All tests passed!")
else:
    print(f"⚠️  {total_passed} assertions passed, {total_failed} assertions failed")
print("="*60 + "\n")
