"""
analyze_author_trajectory.py

分析作者研究方向随时间的演进轨迹。
基于 Paper-IN_SUBFIELD-Subfield 关系，按时间窗口聚合 subfield 分布。
不调用 LLM，纯图查询。
"""

import os
import logging
from typing import Optional
from langchain_core.tools import tool
from tools.neo4j_connector import get_neo4j_driver

logger = logging.getLogger(__name__)


@tool
def analyze_author_trajectory(
    resolved_query: str,
    entities_json: str,
    window_years: int = 3,
) -> str:
    """
    分析作者研究方向随时间的演进轨迹。适用于：
    - "XX 最近几年研究方向有什么变化？"
    - "XX 的研究重心是怎么转移的？"
    - "XX 早期和现在做的方向有什么不同？"

    Args:
        resolved_query: 路由层消解后的查询
        entities_json: EntitySet 的 JSON（从 routing_decision.entities 获取）
        window_years: 时间窗口大小（年），默认 3 年
    """
    from graph.schemas import EntitySet
    entities = EntitySet.model_validate_json(entities_json)

    if not entities.authors:
        return "⚠️ 未识别到作者，请提供学者姓名。"

    author = entities.authors[0]
    if not author.author_id:
        return f"⚠️ 作者 '{author.name}' 存在重名，请先选择具体的作者。"

    author_id = author.author_id
    logger.info(f"[trajectory] Analyzing author: {author.name} ({author_id})")

    driver = get_neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    # Step 1: 获取作者的论文发表年份范围
    range_query = """
    MATCH (a:Author {id: $author_id})-[:AUTHORED]->(p:Paper)
    WHERE p.publication_year IS NOT NULL
    RETURN min(p.publication_year) AS min_year,
           max(p.publication_year) AS max_year,
           count(p) AS total_papers
    """

    # Step 2: 按时间窗口聚合 subfield 分布
    trajectory_query = """
    MATCH (a:Author {id: $author_id})-[:AUTHORED]->(p:Paper)
    WHERE p.publication_year IS NOT NULL
    OPTIONAL MATCH (p)-[:IN_SUBFIELD]->(s:Subfield)
    WITH p.publication_year AS year,
         s.display_name AS subfield,
         p.cited_by_count AS citations
    ORDER BY year
    RETURN year,
           subfield,
           count(*) AS paper_count,
           sum(citations) AS total_citations
    ORDER BY year, paper_count DESC
    """

    try:
        with driver.session(database=database) as session:
            range_result = session.run(range_query, author_id=author_id).single()
            if not range_result or range_result["total_papers"] == 0:
                return f"⚠️ 数据库中未找到 '{author.name}' 的论文记录。"

            min_year = range_result["min_year"]
            max_year = range_result["max_year"]
            total_papers = range_result["total_papers"]

            traj_results = list(session.run(trajectory_query, author_id=author_id))

    except Exception as e:
        logger.error(f"[trajectory] Neo4j error: {e}", exc_info=True)
        return f"❌ 查询出错：{e}"

    if not traj_results:
        return f"⚠️ '{author.name}' 没有可分析的研究轨迹数据。"

    # 按时间窗口聚合
    windows = {}
    for record in traj_results:
        year = record["year"]
        if year is None:
            continue
        window_start = (year - min_year) // window_years * window_years + min_year
        window_end = min(window_start + window_years - 1, max_year)
        window_key = f"{window_start}-{window_end}"

        if window_key not in windows:
            windows[window_key] = {}

        subfield = record["subfield"] or "未分类"
        if subfield not in windows[window_key]:
            windows[window_key][subfield] = {"papers": 0, "citations": 0}
        windows[window_key][subfield]["papers"] += record["paper_count"]
        windows[window_key][subfield]["citations"] += record["total_citations"] or 0

    # 格式化输出
    lines = [
        f"📊 **{author.name} 的研究轨迹分析**",
        f"   发表跨度：{min_year} - {max_year}（共 {total_papers} 篇论文）\n",
    ]

    sorted_windows = sorted(windows.items())
    prev_top_fields = set()

    for window_key, subfields in sorted_windows:
        sorted_subfields = sorted(
            subfields.items(),
            key=lambda x: x[1]["papers"],
            reverse=True
        )
        top_fields = {sf for sf, _ in sorted_subfields[:3]}

        lines.append(f"**【{window_key}】**")
        for i, (sf, stats) in enumerate(sorted_subfields[:5]):
            marker = "🔺" if sf not in prev_top_fields and prev_top_fields else ""
            lines.append(
                f"  {i+1}. {sf} {marker}— {stats['papers']} 篇，"
                f"累计被引 {stats['citations']} 次"
            )

        # 方向变化提示
        new_fields = top_fields - prev_top_fields
        if new_fields and prev_top_fields:
            lines.append(f"  ↳ 新兴方向：{', '.join(new_fields)}")

        prev_top_fields = top_fields
        lines.append("")

    return "\n".join(lines)
