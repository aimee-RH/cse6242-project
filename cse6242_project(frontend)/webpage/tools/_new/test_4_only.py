"""
Test 4 Only - Factual Query Fallback to Text2Cypher with Haiku

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
from graph.schemas import EntitySet, ResolvedAuthor
from tools._new.factual_query import factual_query

# Yao Xie 的真实 author_id
YAO_XIE_ID = "https://openalex.org/A5047736740"

print("\n" + "="*60)
print("Test 4: Factual Query Fallback to Text2Cypher with Haiku")
print("="*60 + "\n")

case = {
    "id": "test_4_fallback_to_text2cypher",
    "resolved_query": "Yao Xie 的合作者里发文最多的三个人",
    "entities": EntitySet(
        authors=[ResolvedAuthor(
            name="Yao Xie",
            author_id=YAO_XIE_ID,
            confidence=1.0,
        )]
    ),
    "query_shape": "multi_hop",
}

print(f"Query: {case['resolved_query']}")
print(f"Query shape: {case['query_shape']}")
print(f"Author ID: {YAO_XIE_ID}\n")

t0 = time.time()
try:
    result = factual_query.invoke({
        "resolved_query": case["resolved_query"],
        "entities_json": case["entities"].model_dump_json(),
        "query_shape": case["query_shape"],
    })
    elapsed = time.time() - t0

    print(f"[Elapsed] {elapsed:.2f}s\n")
    print(f"[Result]")
    print(result)

except Exception as e:
    elapsed = time.time() - t0
    print(f"[Elapsed] {elapsed:.2f}s\n")
    print(f"❌ Exception: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
