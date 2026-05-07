#!/usr/bin/env python3
"""
Report Generation Module for Scholar Compass

This module generates comprehensive academic reports including:
1. Scholar analysis report
2. Advisor comparison report
3. Recommendation report
4. Research field analysis report

Author: Scholar Compass Team
Date: 2026-04-16
Phase: 2 - Advanced Features
"""

from langchain_core.tools import tool
from tools.neo4j_connector import neo4j_connector
from typing import Dict, List, Optional
from datetime import datetime
import json

# ========================================
# Scholar Analysis Report
# ========================================

@tool
def generate_scholar_report(
    scholar_name: str,
    include_collaborators: bool = True,
    include_papers: bool = True,
    include_evolution: bool = True
) -> str:
    """
    Generate a comprehensive analysis report for a specific scholar

    Args:
        scholar_name: Name of the scholar
        include_collaborators: Include collaboration network (default True)
        include_papers: Include top papers (default True)
        include_evolution: Include research evolution (default True)

    Returns:
        Formatted Markdown report

    Examples:
        >>> generate_scholar_report("Yao Xie")
        >>> generate_scholar_report("Jing Liu", include_collaborators=True)
    """
    report = f"""# 学者分析报告

**学者姓名**: {scholar_name}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**数据库**: Scholar Compass Academic Graph

---

## 1. 基本信息

"""

    try:
        # Basic scholar info
        basic_query = """
        MATCH (a:Author)-[:AUTHORED]->(p:Paper)
        WHERE toLower(a.display_name) CONTAINS toLower($scholar_name)
        WITH a, count(p) as paper_count,
             sum(p.cited_by_count) as total_citations,
             avg(p.fwci) as avg_fwci
        RETURN a.display_name as name,
               paper_count,
               total_citations,
               avg_fwci
        ORDER BY paper_count DESC
        LIMIT 1
        """

        basic_info = neo4j_connector.execute_query({"scholar_name": scholar_name})

        if not basic_info:
            return f"❌ 未找到学者: {scholar_name}。请检查姓名拼写。"

        info = basic_info[0]
        report += f"""- **论文总数**: {info['paper_count']} 篇
- **总引用数**: {info['total_citations']:,} 次
- **平均FWCI**: {info['avg_fwci']:.2f}
- **学术影响力**: {'高' if info['avg_fwci'] > 1.5 else '中' if info['avg_fwci'] > 1.0 else '一般'}

"""

        # Research fields
        field_query = """
        MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
        WHERE toLower(a.display_name) CONTAINS toLower($scholar_name)
        WITH s.display_name as field, count(p) as papers
        ORDER BY papers DESC
        RETURN field, papers
        LIMIT 5
        """

        fields = neo4j_connector.execute_query({"scholar_name": scholar_name})

        if fields:
            report += "## 2. 研究领域\n\n"
            for i, field in enumerate(fields, 1):
                report += f"{i}. **{field['field']}** - {field['papers']} 篇论文\n"
            report += "\n"

        # Top papers
        if include_papers:
            papers_query = """
            MATCH (a:Author)-[:AUTHORED]->(p:Paper)
            WHERE toLower(a.display_name) CONTAINS toLower($scholar_name)
            RETURN p.title as title, p.cited_by_count as citations,
                   p.publication_year as year
            ORDER BY p.cited_by_count DESC
            LIMIT 5
            """

            papers = neo4j_connector.execute_query({"scholar_name": scholar_name})

            if papers:
                report += "## 3. 代表性论文\n\n"
                for i, paper in enumerate(papers, 1):
                    report += f"{i}. **{paper['title']}**\n"
                    report += f"   - 引用: {paper['citations']:,} 次\n"
                    report += f"   - 年份: {paper['year']}\n"
                report += "\n"

        # Collaborations
        if include_collaborators:
            collab_query = """
            MATCH (a:Author)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(co:Author)
            WHERE toLower(a.display_name) CONTAINS toLower($scholar_name)
              AND co.id <> a.id
            WITH co, count(p) as strength
            ORDER BY strength DESC
            RETURN co.display_name as name, strength
            LIMIT 10
            """

            collabs = neo4j_connector.execute_query({"scholar_name": scholar_name})

            if collabs:
                report += "## 4. 合作网络\n\n"
                report += "### Top 合作者\n\n"
                for i, collab in enumerate(collabs, 1):
                    report += f"{i}. **{collab['name']}** - {collab['strength']} 篇合作\n"
                report += "\n"

        # Research evolution
        if include_evolution:
            evolution_query = """
            MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
            WHERE toLower(a.display_name) CONTAINS toLower($scholar_name)
              AND p.publication_year >= 2018
            RETURN p.publication_year as year,
                   s.display_name as field,
                   count(p) as papers
            ORDER BY year DESC, papers DESC
            """

            evolution = neo4j_connector.execute_query({"scholar_name": scholar_name})

            if evolution:
                report += "## 5. 研究主题演变\n\n"
                current_year = None
                for record in evolution:
                    if current_year != record['year']:
                        current_year = record['year']
                        report += f"### {record['year']}年\n"
                    report += f"- {record['field']} ({record['papers']} 篇)\n"
                report += "\n"

        # Conclusion
        report += "---\n\n"
        report += "**报告说明**: 本报告基于 Scholar Compass 学术知识图谱生成。\n"
        report += "数据来源：OpenAlex + Neo4j 图数据库\n"
        report += f"最后更新：{datetime.now().strftime('%Y年%m月日')}\n"

        return report

    except Exception as e:
        return f"❌ 生成报告失败: {str(e)}"


# ========================================
# Comparison Report
# ========================================

@tool
def generate_comparison_report(
    scholar_names: str,
    comparison_dimensions: str = "all"
) -> str:
    """
    Generate a comparison report between multiple scholars

    Args:
        scholar_names: Comma-separated scholar names
        comparison_dimensions: Dimensions to compare - 'all', 'overview', 'research', 'impact'

    Returns:
        Formatted Markdown comparison report

    Examples:
        >>> generate_comparison_report("Yao Xie,Jing Liu", "all")
    """
    scholars = [s.strip() for s in scholar_names.split(",")]

    if len(scholars) < 2:
        return "❌ 至少需要2位学者进行对比。"

    report = f"""# 学者对比报告

**对比学者**: {', '.join(scholars)}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 1. 综合对比

"""

    try:
        # Fetch data for all scholars
        comparison_data = []

        for scholar in scholars:
            query = """
            MATCH (a:Author)-[:AUTHORED]->(p:Paper)
            WHERE toLower(a.display_name) CONTAINS toLower($scholar)
            WITH a, count(p) as papers,
                 sum(p.cited_by_count) as citations,
                 avg(p.fwci) as avg_fwci
            RETURN a.display_name as name,
                   papers,
                   citations,
                   avg_fwci
            ORDER BY papers DESC
            LIMIT 1
            """

            result = neo4j_connector.execute_query({"scholar": scholar})
            if result:
                comparison_data.append(result[0])

        if len(comparison_data) < 2:
            return f"❌ 只有 {len(comparison_data)} 位学者找到数据，无法对比。"

        # Create comparison table
        report += "| 学者 | 论文数 | 总引用 | 平均FWCI | 影响力等级 |\n"
        report += "|------|--------|--------|---------|----------|\n"

        for data in comparison_data:
            impact = "高" if data['avg_fwci'] > 1.5 else "中" if data['avg_fwci'] > 1.0 else "一般"
            report += f"| {data['name']} | {data['papers']:,} | {data['citations']:,} | {data['avg_fwci']:.2f} | {impact} |\n"

        report += "\n"

        # Research field comparison
        report += "## 2. 研究领域对比\n\n"

        for data in comparison_data:
            scholar = data['name']
            field_query = """
            MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
            WHERE toLower(a.display_name) CONTAINS toLower($scholar)
            RETURN collect(DISTINCT s.display_name)[0..5] as fields
            """

            result = neo4j_connector.execute_query({"scholar": scholar})
            if result and result[0]['fields']:
                report += f"### {scholar}\n"
                report += f"研究兴趣: {', '.join(result[0]['fields'])}\n\n"

        # Key insights
        report += "## 3. 关键洞察\n\n"

        max_papers = max(comparison_data, key=lambda x: x['papers'])
        max_citations = max(comparison_data, key=lambda x: x['citations'])

        report += f"- **最多论文**: {max_papers['name']} ({max_papers['papers']:,}篇)\n"
        report += f"- **最高引用**: {max_citations['name']} ({max_citations['citations']:,}次)\n"

        report += "\n---\n\n"
        report += "**报告说明**: 本对比报告基于 Scholar Compass 学术知识图谱生成。\n"

        return report

    except Exception as e:
        return f"❌ 生成对比报告失败: {str(e)}"


# ========================================
# Recommendation Report
# ========================================

@tool
def generate_advisor_recommendation(
    research_interest: str,
    student_background: str = None,
    top_n: int = 5
) -> str:
    """
    Generate advisor recommendation report based on student's research interest

    Args:
        research_interest: Student's research interest/topic
        student_background: Additional background info (optional)
        top_n: Number of recommendations (default 5)

    Returns:
        Formatted recommendation report

    Examples:
        >>> generate_advisor_recommendation("Machine Learning", "CS background", top_n=5)
    """
    report = f"""# 导师推荐报告

**学生研究方向**: {research_interest}
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 推荐导师列表

"""

    try:
        # Find scholars in the field
        query = """
        MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
        WHERE toLower(s.display_name) CONTAINS toLower($interest)
        WITH a, count(p) as paper_count,
             sum(p.cited_by_count) as total_citations,
             avg(p.fwci) as avg_fwci
        WHERE paper_count >= 5
        RETURN a.display_name as name,
               paper_count,
               total_citations,
               avg_fwci
        ORDER BY paper_count DESC, avg_fwci DESC
        LIMIT $top_n
        """

        results = neo4j_connector.execute_query({
            "interest": research_interest,
            "top_n": top_n
        })

        if not results:
            return f"❌ 未找到 '{research_interest}' 领域的导师推荐。请尝试更通用的关键词。"

        for i, scholar in enumerate(results, 1):
            impact = "高影响力" if scholar['avg_fwci'] > 1.5 else "中等影响力"
            report += f"{i}. **{scholar['name']}**\n"
            report += f"   - 论文数: {scholar['paper_count']:,}\n"
            report += f"   - 总引用: {scholar['total_citations']:,}\n"
            report += f"   - 学术影响: {impact} (FWCI: {scholar['avg_fwci']:.2f})\n"
            report += "\n"

        report += "---\n\n"
        report += "## 推荐说明\n\n"
        report += "以上导师基于以下标准推荐：\n"
        report += "1. 在目标研究领域有活跃发表\n"
        report += "2. 论文数量和质量综合考虑\n"
        report += "3. FWCI (归一化影响因子) 作为质量指标\n"
        report += "\n建议学生在选择导师时还应考虑：\n"
        report += "- 导师的研究方向是否匹配你的兴趣\n"
        report += "- 实验室氛围和指导风格\n"
        report += "- 职业发展机会\n"

        report += "\n---\n\n"
        report += "**报告说明**: 本推荐报告基于 Scholar Compass 学术知识图谱生成。\n"
        report += "请学生自行联系导师了解更详细信息。\n"

        return report

    except Exception as e:
        return f"❌ 生成推荐报告失败: {str(e)}"


# ========================================
# Export Tools
# ========================================

REPORT_TOOLS = [
    generate_scholar_report,
    generate_comparison_report,
    generate_advisor_recommendation
]

# Test function
def test_report_generator():
    """
    Test report generation modules
    """
    print("\n" + "="*60)
    print("Report Generation Module Test")
    print("="*60 + "\n")

    # Test 1: Scholar report
    print("【测试1】学者分析报告")
    try:
        result = generate_scholar_report.invoke({
            "scholar_name": "Yao Xie",
            "include_collaborators": True,
            "include_papers": True
        })
        print(f"✅ 报告生成成功")
        print(f"   长度: {len(result)} 字符")
        print(f"   预览:\n{result[:300]}...")
    except Exception as e:
        print(f"❌ 报告生成失败: {str(e)}")

    print()

    # Test 2: Comparison report
    print("【测试2】对比报告")
    try:
        result = generate_comparison_report.invoke({
            "scholar_names": "Yao Xie,Jing Liu",
            "comparison_dimensions": "all"
        })
        print(f"✅ 对比报告生成成功")
        print(f"   预览:\n{result[:300]}...")
    except Exception as e:
        print(f"❌ 对比报告失败: {str(e)}")

    print()

    # Test 3: Recommendation report
    print("【测试3】推荐报告")
    try:
        result = generate_advisor_recommendation.invoke({
            "research_interest": "Machine Learning",
            "top_n": 3
        })
        print(f"✅ 推荐报告生成成功")
        print(f"   预览:\n{result[:300]}...")
    except Exception as e:
        print(f"❌ 推荐报告失败: {str(e)}")

    print("\n" + "="*60)
    print("✅ 报告生成模块测试完成！")
    print("="*60 + "\n")

if __name__ == "__main__":
    test_report_generator()
