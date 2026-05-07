"""
Factual Query Tool Test

测试 factual_query 工具的模板匹配和 fallback 机制。

Author: Scholar Compass Team
Date: 2025-04-22
"""

import os
import sys
import time

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv()

# 使用标准 import（__init__.py 已清理，不再有循环导入）
from graph.state import AgentState
from graph.schemas import EntitySet, ResolvedAuthor, TimeRange
from tools.neo4j_connector import get_neo4j_driver
from tools._new.query_templates import try_match_template
from tools.text2cypher import generate_cypher_with_entities
from tools._new.factual_query import factual_query

# Yao Xie 的 author_id（OpenAlex）
YAO_XIE_ID = "https://openalex.org/A5047736740"

# 检查环境变量
assert os.getenv("MINIMAX_API_KEY"), "MINIMAX_API_KEY not set"
print("✅ MINIMAX_API_KEY is set")

# Yao Xie 的真实 author_id（从 Neo4j 验证中得到)
YAO_XIE_ID = "https://openalex.org/A5047736740"

test_cases = [
    {
        "id": "test_1_top_papers_template",
        "desc": "Top N papers — 应命中 author_top_papers 模板",
        "resolved_query": "查询 Yao Xie 的 top 5 高被引论文",
        "entities": EntitySet(
            authors=[ResolvedAuthor(
                name="Yao Xie",
                author_id=YAO_XIE_ID,
                confidence=1.0,
            )]
        ),
        "query_shape": "single_lookup",
        "expect_template_hit": True,
        "expect_result_contains": ["Sequential", "Change Detection"],
    },
    {
        "id": "test_2_paper_count_template",
        "desc": "Paper count — 应命中 author_paper_count 模板",
        "resolved_query": "Yao Xie 发过多少篇论文",
        "entities": EntitySet(
            authors=[ResolvedAuthor(
                name="Yao Xie",
                author_id=YAO_XIE_ID,
                confidence=1.0,
            )]
        ),
        "query_shape": "aggregation",
        "expect_template_hit": True,
        "expect_result_contains": ["18"],  # 18 篇论文（真实数据）
    },
    {
        "id": "test_3_recent_papers_with_time",
        "desc": "带时间范围的查询 — 应命中 author_recent_papers 模板",
        "resolved_query": "Yao Xie 2022 到 2024 年的论文",
        "entities": EntitySet(
            authors=[ResolvedAuthor(
                name="Yao Xie",
                author_id=YAO_XIE_ID,
                confidence=1.0,
            )],
            time_range=TimeRange(start_year=2022, end_year=2024),
        ),
        "query_shape": "single_lookup",
        "expect_template_hit": True,
    },
    {
        "id": "test_4_fallback_to_text2cypher",
        "desc": "非标准问法 — 应 fallback 到 text2cypher",
        "resolved_query": "Yao Xie 的合作者里发文最多的三个人",
        "entities": EntitySet(
            authors=[ResolvedAuthor(
                name="Yao Xie",
                author_id=YAO_XIE_ID,
                confidence=1.0,
            )]
        ),
        "query_shape": "multi_hop",
        "expect_template_hit": False,
        # 只验证能返回结果，不验证内容
    },
]

# 用于捕获模板命中日志的简单机制
template_hits = {}

print("\n" + "="*60)
print("Factual Query Tool Test")
print("="*60 + "\n")

for case in test_cases:
    print(f"\n{'='*60}")
    print(f"TEST: {case['id']}")
    print(f"Desc: {case['desc']}")

    t0 = time.time()
    try:
        result = factual_query.invoke({
            "resolved_query": case["resolved_query"],
            "entities_json": case["entities"].model_dump_json(),
            "query_shape": case["query_shape"],
        })
        elapsed = time.time() - t0

        print(f"[Elapsed] {elapsed:.2f}s")
        print(f"\n[Result (前 500 字符)]")
        print(result[:500])

        # 验证关键词
        if "expect_result_contains" in case:
            print(f"\n[Assertion Checks]")
            for keyword in case["expect_result_contains"]:
                status = "✅" if keyword in result else "❌"
                print(f"{status} Contains '{keyword}'")

    except Exception as e:
        elapsed = time.time() - t0
        print(f"[Elapsed] {elapsed:.2f}s")
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "="*60)
print("Test Summary")
print("="*60)
print("All tests completed. Check results above.")
print("="*60 + "\n")
