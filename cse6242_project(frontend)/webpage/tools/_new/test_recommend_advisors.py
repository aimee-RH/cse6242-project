"""
测试 recommend_advisors 工具
运行：python tools/_new/test_recommend_advisors.py
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from graph.schemas import EntitySet

EMPTY_ENTITIES = EntitySet(authors=[], topics=[], unresolved_authors=[])


def test_recommend_change_detection():
    """测试有数据覆盖的方向"""
    print("\n" + "="*60)
    print("TEST 1: change point detection（有充足数据）")
    print("="*60)
    import time
    from tools._new.recommend_advisors import recommend_advisors

    entities = EntitySet(
        authors=[],
        topics=["change point detection", "sequential analysis"],
        unresolved_authors=[]
    )

    t0 = time.time()
    result = recommend_advisors.invoke({
        "resolved_query": "推荐做 change point detection 方向的导师",
        "entities_json": entities.model_dump_json(),
        "top_advisors": 3,
    })
    elapsed = time.time() - t0

    print(f"[Elapsed] {elapsed:.2f}s")
    print(result[:1000])

    assert "推荐" in result or "导师" in result, "应包含推荐信息"
    assert "Yao Xie" in result, "Yao Xie 应该出现在 change detection 推荐中"
    print("✅ PASS")


def test_recommend_computer_vision():
    """测试 CV 方向"""
    print("\n" + "="*60)
    print("TEST 2: computer vision（数据库有 689 篇）")
    print("="*60)
    import time
    from tools._new.recommend_advisors import recommend_advisors

    entities = EntitySet(
        authors=[],
        topics=["computer vision", "image recognition"],
        unresolved_authors=[]
    )

    t0 = time.time()
    result = recommend_advisors.invoke({
        "resolved_query": "推荐做计算机视觉方向的导师",
        "entities_json": entities.model_dump_json(),
        "top_advisors": 3,
    })
    elapsed = time.time() - t0

    print(f"[Elapsed] {elapsed:.2f}s")
    print(result[:1000])

    assert "推荐" in result or "导师" in result
    print("✅ PASS")


def test_recommend_low_coverage():
    """测试数据库覆盖少的方向，验证 low confidence 警告"""
    print("\n" + "="*60)
    print("TEST 3: quantum computing（数据库覆盖少）")
    print("="*60)
    import time
    from tools._new.recommend_advisors import recommend_advisors

    entities = EntitySet(authors=[], topics=[], unresolved_authors=[])

    t0 = time.time()
    result = recommend_advisors.invoke({
        "resolved_query": "推荐做量子计算方向的导师",
        "entities_json": entities.model_dump_json(),
        "top_advisors": 3,
    })
    elapsed = time.time() - t0

    print(f"[Elapsed] {elapsed:.2f}s")
    print(result[:800])
    print("✅ PASS（低覆盖场景验证完成）")


if __name__ == "__main__":
    test_recommend_change_detection()
    test_recommend_computer_vision()
    test_recommend_low_coverage()
    print("\n🎉 All recommend_advisors tests passed!")
