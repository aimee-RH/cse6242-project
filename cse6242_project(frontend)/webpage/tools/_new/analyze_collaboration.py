"""
analyze_collaboration.py

分析作者的合作网络。
复用旧版 collaboration_analyzer.py 的 Cypher，升级接口规范。
不调用 LLM，纯图查询。
"""

import os
import logging
from typing import Optional
from langchain_core.tools import tool
from tools.neo4j_connector import get_neo4j_driver

logger = logging.getLogger(__name__)


@tool
def analyze_collaboration(
    resolved_query: str,
    entities_json: str,
    top_k: int = 10,
) -> str:
    """
    分析作者的合作网络。适用于：
    - "XX 的主要合作者是谁？"
    - "XX 和谁合作最多？"
    - "XX 的合作圈子是怎样的？"

    Args:
        resolved_query: 路由层消解后的查询
        entities_json: EntitySet 的 JSON
        top_k: 返回合作者数量，默认 10
    """
    from graph.schemas import EntitySet
    entities = EntitySet.model_validate_json(entities_json)

    if not entities.authors:
        return "⚠️ 未识别到作者，请提供学者姓名。"

    author = entities.authors[0]
    if not author.author_id:
        return f"⚠️ 作者 '{author.name}' 存在重名，请先选择具体的作者。"

    author_id = author.author_id
    logger.info(f"[collaboration] Analyzing: {author.name} ({author_id})")

    # 扩展版 Cypher：比旧版多返回合作者的 subfield 信息
    query = """
    MATCH (a:Author {id: $author_id})-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(co:Author)
    WHERE a.id <> co.id
    WITH co, count(DISTINCT p) AS collab_count,
         collect(DISTINCT p.title)[..3] AS shared_papers
    ORDER BY collab_count DESC
    LIMIT $top_k
    OPTIONAL MATCH (co)-[:AUTHORED]->(cp:Paper)-[:IN_SUBFIELD]->(s:Subfield)
    WITH co, collab_count, shared_papers,
         collect(DISTINCT s.display_name)[..3] AS co_fields,
         count(DISTINCT cp) AS co_total_papers
    RETURN co.display_name AS name,
           co.id AS co_id,
           collab_count,
           shared_papers,
           co_fields,
           co_total_papers
    ORDER BY collab_count DESC
    """

    driver = get_neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    try:
        with driver.session(database=database) as session:
            results = list(session.run(
                query,
                author_id=author_id,
                top_k=top_k,
            ))
    except Exception as e:
        logger.error(f"[collaboration] Neo4j error: {e}", exc_info=True)
        return f"❌ 查询出错：{e}"

    if not results:
        return f"⚠️ 未找到 '{author.name}' 的合作者记录。"

    lines = [
        f"🤝 **{author.name} 的合作网络**（Top {len(results)}）\n",
    ]

    for i, r in enumerate(results, 1):
        fields_str = "、".join(r["co_fields"]) if r["co_fields"] else "未知领域"
        lines.append(f"**{i}. {r['name']}**")
        lines.append(f"   合作论文：{r['collab_count']} 篇 | 总发文：{r['co_total_papers']} 篇")
        lines.append(f"   研究领域：{fields_str}")
        if r["shared_papers"]:
            lines.append(f"   代表合作论文：《{r['shared_papers'][0][:60]}...》")
        lines.append("")

    return "\n".join(lines)
