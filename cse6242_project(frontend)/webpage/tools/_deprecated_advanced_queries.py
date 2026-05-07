#!/usr/bin/env python3
"""
Advanced Graph Query Module for Scholar Compass

This module extends the graph retrieval capabilities with advanced queries:
1. Scholar comparison (横向对比)
2. Conditional filtering (条件筛选)
3. Community discovery (社区发现)
4. Path finding (路径查询)
5. Evolution analysis (演化分析)

Author: Scholar Compass Team
Date: 2026-04-16
Phase: 2 - Advanced Features
"""

from langchain_core.tools import tool
from tools.neo4j_connector import neo4j_connector
from typing import List, Dict, Optional
import json

# ========================================
# Scholar Comparison Query
# ========================================

@tool
def compare_scholars(
    scholar_names: str,
    compare_aspects: str = "all"
) -> str:
    """
    Compare multiple scholars across different dimensions

    Args:
        scholar_names: Comma-separated list of scholar names (e.g., "Yao Xie,Jing Liu")
        compare_aspects: Aspects to compare - 'all', 'papers', 'citations', 'fields', 'collaborations'

    Returns:
        Comparison report in structured format

    Examples:
        >>> compare_scholars("Yao Xie,Jing Liu", "all")
        >>> compare_scholars("Zhong Lin Wang,Vince D. Calhoun", "papers,citations")
    """
    # Parse scholar names
    scholars = [s.strip() for s in scholar_names.split(",")]

    if len(scholars) < 2:
        return "❌ 至少需要2位学者进行对比。请提供学者姓名，用逗号分隔。"

    # Build comparison query
    query = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)
    WHERE toLower(a.display_name) IN $scholar_names
    WITH a, count(p) as paper_count,
         sum(p.cited_by_count) as total_citations,
         avg(p.fwci) as avg_fwci
    RETURN a.display_name as name,
           paper_count,
           total_citations,
           avg_fwci
    ORDER BY paper_count DESC
    """

    try:
        results = neo4j_connector.execute_query(query, {
            "scholar_names": [s.lower() for s in scholars]
        })

        if not results:
            return f"未找到学者: {', '.join(scholars)}"

        # Format comparison report
        output = f"【学者对比报告】\n\n"

        for i, scholar in enumerate(results, 1):
            output += f"{i}. {scholar['name']}\n"
            output += f"   论文数: {scholar['paper_count']}\n"
            output += f"   总引用: {scholar['total_citations']}\n"
            output += f"   平均FWCI: {scholar['avg_fwci']:.2f}\n\n"

        # Add comparison insights
        if len(results) >= 2:
            max_papers = max(results, key=lambda x: x['paper_count'])
            max_citations = max(results, key=lambda x: x['total_citations'])

            output += "【对比洞察】\n"
            output += f"• 最多论文: {max_papers['name']} ({max_papers['paper_count']}篇)\n"
            output += f"• 最高引用: {max_citations['name']} ({max_citations['total_citations']}次)\n"

        return output

    except Exception as e:
        return f"❌ 对比查询失败: {str(e)}"


# ========================================
# Conditional Filtering Query
# ========================================

@tool
def filter_scholars(
    field: str,
    min_papers: int = 5,
    min_citations: int = None,
    year_range: str = None,
    top_n: int = 10
) -> str:
    """
    Filter scholars based on multiple criteria

    Args:
        field: Research field name (e.g., "Machine Learning")
        min_papers: Minimum number of papers (default 5)
        min_citations: Minimum total citations (optional)
        year_range: Year range like "2018-2023" (optional)
        top_n: Number of results to return (default 10)

    Returns:
        Filtered list of scholars with statistics

    Examples:
        >>> filter_scholars("Machine Learning", min_papers=10, min_citations=1000)
        >>> filter_scholars("Computer Vision", year_range="2020-2023", top_n=20)
    """
    # Build dynamic query with filters
    where_clauses = ["toLower(s.display_name) CONTAINS toLower($field)"]
    params = {"field": field, "min_papers": min_papers, "top_n": top_n}

    query = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
    """

    # Add year filter if specified
    if year_range:
        try:
            start_year, end_year = map(int, year_range.split("-"))
            query += " WHERE p.publication_year >= $start_year AND p.publication_year <= $end_year"
            params["start_year"] = start_year
            params["end_year"] = end_year
        except:
            pass  # Invalid year range, skip

    # Continue query
    query += f"""
    WITH a, count(p) as paper_count, sum(p.cited_by_count) as total_citations
    WHERE paper_count >= $min_papers
    """

    # Add citation filter if specified
    if min_citations:
        query += " AND total_citations >= $min_citations"
        params["min_citations"] = min_citations

    # Final return
    query += f"""
    RETURN a.display_name as name,
           paper_count,
           total_citations
    ORDER BY paper_count DESC, total_citations DESC
    LIMIT $top_n
    """

    try:
        results = neo4j_connector.execute_query(query, params)

        if not results:
            return f"未找到符合条件 '{field}' 的学者。请尝试：\n1. 降低筛选条件\n2. 使用更通用的领域名称"

        output = f"【筛选结果】{field}领域的学者\n\n"
        output += f"筛选条件:\n"
        output += f"- 最少论文数: {min_papers}\n"
        if min_citations:
            output += f"- 最少引用数: {min_citations}\n"
        if year_range:
            output += f"- 年份范围: {year_range}\n"

        output += f"\n找到 {len(results)} 位学者:\n\n"

        for i, scholar in enumerate(results, 1):
            output += f"{i}. {scholar['name']}\n"
            output += f"   论文数: {scholar['paper_count']}\n"
            output += f"   总引用: {scholar['total_citations']}\n\n"

        return output

    except Exception as e:
        return f"❌ 筛选查询失败: {str(e)}"


# ========================================
# Community Discovery Query
# ========================================

@tool
def find_research_communities(
    field: str,
    min_collaboration_strength: int = 2,
    top_communities: int = 5
) -> str:
    """
    Discover research communities based on collaboration patterns

    Args:
        field: Research field to analyze
        min_collaboration_strength: Minimum collaboration count to be considered (default 2)
        top_communities: Number of communities to return (default 5)

    Returns:
        Community analysis with key members and connections

    Examples:
        >>> find_research_communities("Machine Learning", min_collaboration_strength=3)
    """
    query = """
    MATCH (a1:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield),
         (a2:Author)-[:AUTHORED]->(p:Paper)
    WHERE toLower(s.display_name) CONTAINS toLower($field)
      AND a1.id <> a2.id
    WITH a1, a2, count(p) as strength
    WHERE strength >= $min_strength
    RETURN a1.display_name as scholar1,
           a2.display_name as scholar2,
           strength
    ORDER BY strength DESC
    LIMIT 50
    """

    try:
        results = neo4j_connector.execute_query(query, {
            "field": field,
            "min_strength": min_collaboration_strength
        })

        if not results:
            return f"未在 '{field}' 领域发现研究社区。"

        # Analyze communities (simple clustering)
        output = f"【{field} 研究社区分析】\n\n"
        output += f"基于 {len(results)} 对合作关系\n"
        output += f"最小合作强度: {min_collaboration_strength}\n\n"

        # Group by first scholar
        communities = {}
        for r in results:
            if r['scholar1'] not in communities:
                communities[r['scholar1']] = []
            communities[r['scholar1']].append({
                'collaborator': r['scholar2'],
                'strength': r['strength']
            })

        # Find top communities
        sorted_communities = sorted(
            communities.items(),
            key=lambda x: len(x[1]),
            reverse=True
        )[:top_communities]

        for i, (leader, members) in enumerate(sorted_communities, 1):
            output += f"社区 {i}: {leader}\n"
            output += f"  合作伙伴数: {len(members)}\n"
            top_collabs = sorted(members, key=lambda x: x['strength'], reverse=True)[:3]
            for collab in top_collabs:
                output += f"  - {collab['collaborator']} ({collab['strength']} 篇合作)\n"
            output += "\n"

        return output

    except Exception as e:
        return f"❌ 社区发现查询失败: {str(e)}"


# ========================================
# Path Finding Query
# ========================================

@tool
def find_academic_path(
    scholar1: str,
    scholar2: str,
    max_hops: int = 3
) -> str:
    """
    Find the shortest collaboration path between two scholars

    Args:
        scholar1: First scholar's name
        scholar2: Second scholar's name
        max_hops: Maximum path length (default 3)

    Returns:
        Path showing how scholars are connected through collaborations

    Examples:
        >>> find_academic_path("Yao Xie", "Jing Liu", max_hops=3)
    """
    query = """
    MATCH path = shortestPath(
      (a1:Author)-[:AUTHORED*1..{max_hops}]-(a2:Author)
    )
    WHERE toLower(a1.display_name) CONTAINS toLower($scholar1)
      AND toLower(a2.display_name) CONTAINS toLower($scholar2)
    RETURN [node in nodes(a1) | node in nodes(a2) | node in relationships(path) |
            CASE WHEN node:Author THEN node.display_name
                 WHEN node:Paper THEN node.title
                 WHEN node:Paper THEN '→' + node.title + '→'
            END as path_element
    """

    try:
        results = neo4j_connector.execute_query(query, {
            "scholar1": scholar1,
            "scholar2": scholar2,
            "max_hops": max_hops
        })

        if not results:
            return f"未找到 {scholar1} 和 {scholar2} 之间的学术路径（最多{max_hops}跳）。"

        output = f"【学术路径】{scholar1} → {scholar2}\n\n"

        for i, result in enumerate(results, 1):
            path = result['path_element']
            output += f"路径 {i}: {path}\n"

        return output

    except Exception as e:
        return f"❌ 路径查询失败: {str(e)}"


# ========================================
# Research Evolution Query
# ========================================

@tool
def analyze_research_evolution(
    scholar_name: str,
    start_year: int = 2018,
    end_year: int = 2024,
    top_topics: int = 3
) -> str:
    """
    Analyze how a scholar's research focus has evolved over time

    Args:
        scholar_name: Name of the scholar
        start_year: Starting year (default 2018)
        end_year: Ending year (default 2024)
        top_topics: Number of top topics to show per year (default 3)

    Returns:
        Year-by-year research topic evolution

    Examples:
        >>> analyze_research_evolution("Yao Xie", 2018, 2023, top_topics=5)
    """
    query = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
    WHERE toLower(a.display_name) CONTAINS toLower($scholar_name)
      AND p.publication_year >= $start_year
      AND p.publication_year <= $end_year
    RETURN p.publication_year as year,
           s.display_name as topic,
           count(p) as papers
    ORDER BY year ASC, papers DESC
    """

    try:
        results = neo4j_connector.execute_query(query, {
            "scholar_name": scholar_name,
            "start_year": start_year,
            "end_year": end_year
        })

        if not results:
            return f"未找到学者 {scholar_name} 在 {start_year}-{end_year} 年间的论文数据。"

        output = f"【研究主题演变】{scholar_name} ({start_year}-{end_year})\n\n"

        # Group by year
        yearly_topics = {}
        for r in results:
            year = r['year']
            if year not in yearly_topics:
                yearly_topics[year] = []
            yearly_topics[year].append({
                'topic': r['topic'],
                'papers': r['papers']
            })

        # Format output
        for year in sorted(yearly_topics.keys()):
            output += f"{year}年:\n"
            topics = yearly_topics[year][:top_topics]
            for i, topic in enumerate(topics, 1):
                output += f"  {i}. {topic['topic']} ({topic['papers']} 篇)\n"
            output += "\n"

        return output

    except Exception as e:
        return f"❌ 演化分析失败: {str(e)}"


# ========================================
# Export Tools
# ========================================

ADVANCED_TOOLS = [
    compare_scholars,
    filter_scholars,
    find_research_communities,
    find_academic_path,
    analyze_research_evolution
]

# Test function
def test_advanced_queries():
    """
    Test advanced query modules
    """
    print("\n" + "="*60)
    print("Advanced Graph Query Module Test")
    print("="*60 + "\n")

    # Test 1: Scholar comparison
    print("【测试1】学者对比")
    try:
        result = compare_scholars.invoke({
            "scholar_names": "Yao Xie,Jing Liu",
            "compare_aspects": "all"
        })
        print(f"✅ 学者对比完成")
        print(f"   结果预览: {result[:200]}...")
    except Exception as e:
        print(f"❌ 学者对比失败: {str(e)}")

    print()

    # Test 2: Research evolution
    print("【测试2】研究演化")
    try:
        result = analyze_research_evolution.invoke({
            "scholar_name": "Yao Xie",
            "start_year": 2018,
            "end_year": 2023,
            "top_topics": 3
        })
        print(f"✅ 研究演化分析完成")
        print(f"   结果预览: {result[:200]}...")
    except Exception as e:
        print(f"❌ 研究演化失败: {str(e)}")

    print()

    # Test 3: Filtering
    print("【测试3】条件筛选")
    try:
        result = filter_scholars.invoke({
            "field": "Machine Learning",
            "min_papers": 10,
            "top_n": 5
        })
        print(f"✅ 条件筛选完成")
        print(f"   结果预览: {result[:200]}...")
    except Exception as e:
        print(f"❌ 条件筛选失败: {str(e)}")

    print("\n" + "="*60)
    print("✅ 高级查询模块测试完成！")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_advanced_queries()
