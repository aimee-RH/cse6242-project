"""
测试 3 个 analysis 工具
运行：python tools/_new/test_analysis_tools.py
"""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

from graph.schemas import EntitySet, ResolvedAuthor

# 测试用的 EntitySet（Yao Xie，已知 18 篇论文）
YAO_XIE_ENTITIES = EntitySet(
    authors=[ResolvedAuthor(
        name="Yao Xie",
        author_id="https://openalex.org/A5047736740",
        confidence=1.0,
    )]
)

# 测试 compare 用的双作者 EntitySet
COMPARE_ENTITIES = EntitySet(
    authors=[
        ResolvedAuthor(
            name="Yao Xie",
            author_id="https://openalex.org/A5047736740",
            confidence=1.0,
        ),
        ResolvedAuthor(
            name="Le Song",
            author_id="https://openalex.org/A5030892038",  # 先用这个，跑完看结果再确认
            confidence=1.0,
        ),
    ]
)


def test_trajectory():
    print("\n" + "="*60)
    print("TEST: analyze_author_trajectory")
    print("="*60)
    from tools._new.analyze_author_trajectory import analyze_author_trajectory
    import time
    t0 = time.time()
    result = analyze_author_trajectory.invoke({
        "resolved_query": "Yao Xie 最近几年研究方向有什么变化",
        "entities_json": YAO_XIE_ENTITIES.model_dump_json(),
        "window_years": 3,
    })
    elapsed = time.time() - t0
    print(f"[Elapsed] {elapsed:.2f}s")
    print(result)
    assert "研究轨迹" in result or "📊" in result, "结果应包含轨迹分析"
    assert "Yao Xie" in result, "结果应包含作者名"
    print("✅ PASS")


def test_collaboration():
    print("\n" + "="*60)
    print("TEST: analyze_collaboration")
    print("="*60)
    from tools._new.analyze_collaboration import analyze_collaboration
    import time
    t0 = time.time()
    result = analyze_collaboration.invoke({
        "resolved_query": "Yao Xie 的主要合作者是谁",
        "entities_json": YAO_XIE_ENTITIES.model_dump_json(),
        "top_k": 5,
    })
    elapsed = time.time() - t0
    print(f"[Elapsed] {elapsed:.2f}s")
    print(result)
    assert "Liyan Xie" in result or "合作" in result, "应包含合作者信息"
    print("✅ PASS")


def test_compare():
    print("\n" + "="*60)
    print("TEST: compare_scholars")
    print("="*60)

    # 先查一下 Le Song 的真实 ID
    from tools.neo4j_connector import get_neo4j_driver
    import os
    driver = get_neo4j_driver()
    with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as sess:
        result = sess.run(
            "MATCH (a:Author {display_name: 'Le Song'}) RETURN a.id AS id, a.display_name AS name ORDER BY id LIMIT 1"
        ).single()
        if result:
            le_song_id = result["id"]
            print(f"Le Song 真实 ID: {le_song_id}")
        else:
            print("⚠️ 数据库中找不到 Le Song，跳过 compare 测试")
            return

    compare_entities = EntitySet(
        authors=[
            ResolvedAuthor(
                name="Yao Xie",
                author_id="https://openalex.org/A5047736740",
                confidence=1.0,
            ),
            ResolvedAuthor(
                name="Le Song",
                author_id=le_song_id,
                confidence=1.0,
            ),
        ]
    )

    from tools._new.compare_scholars import compare_scholars
    import time
    t0 = time.time()
    result = compare_scholars.invoke({
        "resolved_query": "对比 Yao Xie 和 Le Song 的研究方向",
        "entities_json": compare_entities.model_dump_json(),
    })
    elapsed = time.time() - t0
    print(f"[Elapsed] {elapsed:.2f}s")
    print(result)
    assert "对比" in result or "📊" in result, "应包含对比信息"
    assert "Yao Xie" in result, "应包含 Yao Xie"
    print("✅ PASS")


if __name__ == "__main__":
    test_trajectory()
    test_collaboration()
    test_compare()
    print("\n🎉 All tests passed!")
