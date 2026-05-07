"""
recommend_advisors.py

基于研究方向推荐 GT 导师。
流程：
  1. BGE-M3 embed query（复用 semantic_search 的模型单例）
  2. Neo4j 向量检索 top-K 相关论文
  3. 从论文聚合到作者，计算综合评分
  4. 返回 top-N 导师推荐列表

综合评分公式：
  score = 0.4 * avg_semantic_sim   （语义相关度）
        + 0.3 * normalized_citations （引用影响力）
        + 0.2 * normalized_fwci      （领域标准化影响力）
        + 0.1 * normalized_recency   （近期活跃度）
"""

import os
import logging
import math
from typing import List, Dict
from langchain_core.tools import tool
from tools.neo4j_connector import get_neo4j_driver

logger = logging.getLogger(__name__)

VECTOR_INDEX_NAME = "paper_embedding_idx"
LOW_CONFIDENCE_THRESHOLD = 0.75


def _normalize(values: List[float]) -> List[float]:
    """Min-max 归一化"""
    if not values:
        return values
    min_v = min(values)
    max_v = max(values)
    if max_v == min_v:
        return [1.0] * len(values)
    return [(v - min_v) / (max_v - min_v) for v in values]


@tool
def recommend_advisors(
    resolved_query: str,
    entities_json: str,
    top_advisors: int = 5,
    candidate_papers: int = 50,
) -> str:
    """
    基于研究方向推荐 GT 导师。适用于：
    - "我想做 federated learning，有哪些老师合适？"
    - "推荐几个做 computer vision 的导师"
    - "哪位教授最适合做 NLP 方向？"

    Args:
        resolved_query: 路由层消解后的查询（包含研究方向关键词）
        entities_json: EntitySet 的 JSON
        top_advisors: 推荐导师数量，默认 5
        candidate_papers: 向量检索候选论文数，默认 50
    """
    from graph.schemas import EntitySet
    from tools._new.semantic_search import _embed_query

    entities = EntitySet.model_validate_json(entities_json)

    # 提取研究方向：优先用 topics，其次用 resolved_query
    topics = entities.topics if entities.topics else []
    search_text = " ".join(topics) if topics else resolved_query

    logger.info(f"[recommend_advisors] Search text: '{search_text}'")
    logger.info(f"[recommend_advisors] top_advisors={top_advisors}, "
                f"candidate_papers={candidate_papers}")

    # Step 1: 向量化 query
    try:
        query_emb = _embed_query(search_text)
    except Exception as e:
        logger.error(f"[recommend_advisors] Embedding error: {e}")
        return f"❌ 向量化失败：{e}"

    # Step 2: 向量检索 top 论文 + 聚合到作者
    cypher = """
    CALL db.index.vector.queryNodes($index_name, $candidate_papers, $emb)
    YIELD node AS paper, score AS semantic_score
    WHERE semantic_score >= $min_score
    MATCH (author:Author)-[:AUTHORED]->(paper)
    OPTIONAL MATCH (paper)-[:IN_SUBFIELD]->(s:Subfield)
    WITH author,
         avg(semantic_score) AS avg_sem_score,
         count(DISTINCT paper) AS matched_papers,
         collect(DISTINCT s.display_name)[..3] AS matched_subfields,
         collect(DISTINCT paper.title)[..2] AS sample_titles,
         max(semantic_score) AS max_sem_score
    WHERE matched_papers >= 1
    OPTIONAL MATCH (author)-[:AUTHORED]->(all_paper:Paper)
    WITH author,
         avg_sem_score,
         matched_papers,
         matched_subfields,
         sample_titles,
         max_sem_score,
         count(DISTINCT all_paper) AS total_papers,
         sum(all_paper.cited_by_count) AS total_citations,
         avg(all_paper.fwci) AS avg_fwci,
         max(all_paper.publication_year) AS latest_year
    RETURN author.id AS author_id,
           author.display_name AS name,
           avg_sem_score,
           max_sem_score,
           matched_papers,
           matched_subfields,
           sample_titles,
           total_papers,
           total_citations,
           avg_fwci,
           latest_year
    ORDER BY avg_sem_score DESC
    LIMIT $top_n
    """

    driver = get_neo4j_driver()
    database = os.getenv("NEO4J_DATABASE", "neo4j")

    try:
        with driver.session(database=database) as session:
            results = list(session.run(
                cypher,
                index_name=VECTOR_INDEX_NAME,
                candidate_papers=candidate_papers,
                emb=query_emb,
                min_score=LOW_CONFIDENCE_THRESHOLD - 0.05,
                top_n=top_advisors * 3,  # 多取一些用于重排序
            ))
    except Exception as e:
        logger.error(f"[recommend_advisors] Neo4j error: {e}", exc_info=True)
        return f"❌ 数据库查询失败：{e}"

    if not results:
        return (
            f"⚠️ 未找到与「{search_text}」高度相关的导师。\n"
            f"建议：尝试更具体的研究方向关键词，"
            f"或查看数据库覆盖的主要领域。"
        )

    # Step 3: 综合评分 + 重排序
    rows = [dict(r) for r in results]

    citations_list = [r["total_citations"] or 0 for r in rows]
    fwci_list = [r["avg_fwci"] or 0 for r in rows]
    recency_list = [r["latest_year"] or 2000 for r in rows]
    sem_list = [r["avg_sem_score"] or 0 for r in rows]

    norm_citations = _normalize(citations_list)
    norm_fwci = _normalize(fwci_list)
    norm_recency = _normalize(recency_list)
    norm_sem = _normalize(sem_list)

    for i, r in enumerate(rows):
        r["composite_score"] = (
            0.4 * norm_sem[i]
            + 0.3 * norm_citations[i]
            + 0.2 * norm_fwci[i]
            + 0.1 * norm_recency[i]
        )

    rows.sort(key=lambda x: x["composite_score"], reverse=True)
    top_rows = rows[:top_advisors]

    # Step 4: 格式化输出
    avg_top1_score = top_rows[0]["avg_sem_score"] if top_rows else 0
    confidence_marker = "✅" if avg_top1_score >= LOW_CONFIDENCE_THRESHOLD else "⚠️"

    lines = [
        f"{confidence_marker} **为「{search_text}」推荐 {len(top_rows)} 位导师**",
        f"   （语义相关度 top-1: {avg_top1_score:.2f}）\n",
    ]

    for i, r in enumerate(top_rows, 1):
        subfields_str = " | ".join(r["matched_subfields"]) if r["matched_subfields"] else "未知领域"
        latest = r["latest_year"] or "未知"
        fwci_str = f"{r['avg_fwci']:.1f}" if r["avg_fwci"] else "N/A"

        lines.append(f"**{i}. {r['name']}**  `综合评分 {r['composite_score']:.2f}`")
        lines.append(f"   🎯 相关论文：{r['matched_papers']} 篇  |  总发文：{r['total_papers']} 篇")
        lines.append(f"   📊 累计被引：{r['total_citations']}  |  FWCI：{fwci_str}  |  最近发文：{latest}")
        lines.append(f"   🏷️ 匹配领域：{subfields_str}")
        if r["sample_titles"]:
            lines.append(f"   📄 代表论文：《{r['sample_titles'][0][:70]}》")
        lines.append("")

    if avg_top1_score < LOW_CONFIDENCE_THRESHOLD:
        lines.append(
            f"⚠️ **注意**：相关度较低（{avg_top1_score:.2f} < {LOW_CONFIDENCE_THRESHOLD}），"
            f"数据库可能对「{search_text}」领域覆盖有限。"
        )

    return "\n".join(lines)
