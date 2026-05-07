"""
compare_scholars.py

多学者横向对比：研究领域、影响力指标、发表趋势。
不调用 LLM，纯图查询 + 格式化。
"""

import os
import logging
from langchain_core.tools import tool
from tools.neo4j_connector import get_neo4j_driver

logger = logging.getLogger(__name__)


@tool
def compare_scholars(
    resolved_query: str,
    entities_json: str,
) -> str:
    """
    对比多位学者的研究方向和影响力。适用于：
    - "对比 XX 和 YY 的研究方向"
    - "XX、YY、ZZ 谁更适合做 A 方向的导师？"
    - "这几个老师有什么异同？"

    Args:
        resolved_query: 路由层消解后的查询
        entities_json: EntitySet 的 JSON（需包含 2+ 个已解析作者）
    """
    from graph.schemas import EntitySet
    entities = EntitySet.model_validate_json(entities_json)

    resolved = [a for a in entities.authors if a.author_id]
    if len(resolved) < 2:
        return (
            "⚠️ 对比需要至少 2 位已确认的学者。\n"
            f"当前已识别：{len(resolved)} 位。\n"
            "请先消歧重名作者，或提供更多学者姓名。"
        )

    query = """
    MATCH (a:Author {id: $author_id})
    OPTIONAL MATCH (a)-[:AUTHORED]->(p:Paper)
    OPTIONAL MATCH (p)-[:IN_SUBFIELD]->(s:Subfield)
    WITH a,
         count(DISTINCT p) AS total_papers,
         sum(p.cited_by_count) AS total_citations,
         avg(p.fwci) AS avg_fwci,
         max(p.cited_by_count) AS max_citations,
         collect(DISTINCT s.display_name)[..5] AS top_subfields,
         max(p.publication_year) AS latest_year,
         min(p.publication_year) AS earliest_year
    RETURN a.display_name AS name,
           total_papers,
           total_citations,
           avg_fwci,
           max_citations,
           top_subfields,
           latest_year,
           earliest_year
    """

    driver = get_neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    profiles = []
    try:
        with driver.session(database=database) as session:
            for author in resolved:
                result = session.run(query, author_id=author.author_id).single()
                if result:
                    profiles.append(dict(result))
                    logger.info(f"[compare] Got profile for {author.name}")
    except Exception as e:
        logger.error(f"[compare] Neo4j error: {e}", exc_info=True)
        return f"❌ 查询出错：{e}"

    if not profiles:
        return "⚠️ 未能获取任何学者的数据。"

    # 格式化对比表
    lines = [f"📊 **学者对比分析**（共 {len(profiles)} 位）\n"]

    # 逐人展示
    for p in profiles:
        subfields_str = " | ".join(p["top_subfields"]) if p["top_subfields"] else "未知"
        span = f"{p['earliest_year']}-{p['latest_year']}" if p["earliest_year"] else "未知"
        lines.append(f"### {p['name']}")
        lines.append(f"- 发表论文：{p['total_papers']} 篇（{span}）")
        lines.append(f"- 累计被引：{p['total_citations']} 次 | 最高单篇：{p['max_citations']} 次")
        lines.append(f"- 平均 FWCI：{p['avg_fwci']:.2f}" if p["avg_fwci"] else "- 平均 FWCI：N/A")
        lines.append(f"- 主要领域：{subfields_str}")
        lines.append("")

    # 综合对比
    lines.append("### 📈 综合对比")
    sorted_by_citations = sorted(profiles, key=lambda x: x["total_citations"] or 0, reverse=True)
    sorted_by_papers = sorted(profiles, key=lambda x: x["total_papers"] or 0, reverse=True)
    sorted_by_fwci = sorted(profiles, key=lambda x: x["avg_fwci"] or 0, reverse=True)

    lines.append(f"- 引用最高：**{sorted_by_citations[0]['name']}**（{sorted_by_citations[0]['total_citations']} 次）")
    lines.append(f"- 发文最多：**{sorted_by_papers[0]['name']}**（{sorted_by_papers[0]['total_papers']} 篇）")
    lines.append(f"- FWCI 最高：**{sorted_by_fwci[0]['name']}**（{sorted_by_fwci[0]['avg_fwci']:.2f}）")

    # 领域重叠分析
    if len(profiles) >= 2:
        all_fields = [set(p["top_subfields"]) for p in profiles]
        common = all_fields[0].intersection(*all_fields[1:])
        if common:
            lines.append(f"- 共同领域：{' | '.join(common)}")
        else:
            lines.append("- 共同领域：无明显重叠（研究方向差异较大）")

    return "\n".join(lines)
