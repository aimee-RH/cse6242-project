#!/usr/bin/env python3
"""
测试 Yao Xie 查询 - 验证修复
"""

from tools.scholar_search import search_scholars_by_field
from tools.author_analysis import get_author_details
from tools.collaboration_analyzer import analyze_collaborations

def test_yao_xie():
    print("=" * 60)
    print("测试 Yao Xie 查询")
    print("=" * 60)
    print()

    # 测试1: 搜索统计学领域的学者
    print("【测试1】搜索统计学领域的学者")
    print("-" * 40)
    result1 = search_scholars_by_field.invoke({"research_field": "Statistics", "limit": 5})
    print(result1)
    print()

    # 测试2: 获取 Yao Xie 的详细信息
    print("【测试2】获取 Yao Xie 的详细信息")
    print("-" * 40)
    author_id = "https://openalex.org/A5047736740"
    result2 = get_author_details.invoke({"author_id": author_id})
    print(result2)
    print()

    # 测试3: 分析 Yao Xie 的合作者
    print("【测试3】分析 Yao Xie 的合作者")
    print("-" * 40)
    result3 = analyze_collaborations.invoke({"author_id": author_id, "limit": 10})
    print(result3)
    print()

    print("=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    test_yao_xie()
