"""
Author Resolver Module

This module handles the resolution of author names to database IDs,
including handling of duplicate names through topic-based filtering.

Author: Scholar Compass Team
Date: 2025-04-20
Updated: 2025-04-22 (修正为精确匹配 + 按引用数排序)
"""

from typing import List, Optional, Dict, Any
from graph.schemas import AuthorCandidate
from tools.neo4j_connector import neo4j_connector
import re
import logging

logger = logging.getLogger(__name__)


def _sanitize_title(title: str) -> str:
    """
    清洗论文标题，移除非法字符。

    Args:
        title: 原始标题

    Returns:
        清洗后的标题
    """
    if not title:
        return "(无标题)"

    # 移除不可打印字符和替换字符
    cleaned = "".join(c for c in title if c.isprintable() and c != "\ufffd")
    # 合并多余空白
    cleaned = " ".join(cleaned.split())

    if not cleaned:
        return "(标题含非法字符)"

    # 限制长度
    return cleaned[:200]


def resolve_author_name_to_id(
    name: str,
    topic_hints: Optional[List[str]] = None
) -> List[AuthorCandidate]:
    """
    根据姓名查 Neo4j，返回候选列表。

    策略：
    1. 精确匹配作者 display_name（因为用户输入通常是完整姓名）
    2. 按总引用数排序，返回所有匹配项
    3. 返回 List[AuthorCandidate]，包含 sample_titles

    返回格式：
    - 空列表：无匹配
    - 单元素：唯一匹配
    - 多元素：重名，需要反问用户

    Args:
        name: 作者姓名（精确匹配）
        topic_hints: 研究主题关键词（预留，当前未使用）

    Returns:
        List[AuthorCandidate]: 候选作者列表

    Example:
        >>> candidates = resolve_author_name_to_id("Yao Xie")
        >>> print(candidates[0].author_id)
        'https://openalex.org/A5047736740'
    """
    if not name or not name.strip():
        return []

    # 清理输入
    name = name.strip()

    # 精确匹配 Cypher 查询，按引用数排序
    query = """
    MATCH (a:Author {display_name: $name})
    OPTIONAL MATCH (a)-[:AUTHORED]->(p:Paper)
    WITH a, p
    ORDER BY coalesce(p.cited_by_count, 0) DESC
    WITH a, collect(p) AS papers
    WITH a,
         size(papers) AS paper_count,
         [x IN papers[..3] | x.title] AS sample_titles,
         reduce(s = 0, x IN papers | s + coalesce(x.cited_by_count, 0)) AS total_citations,
         coalesce(papers[0].cited_by_count, 0) AS max_citations
    RETURN a.id AS author_id,
           a.display_name AS name,
           paper_count,
           sample_titles,
           total_citations,
           max_citations
    ORDER BY total_citations DESC
    """

    try:
        logger.info(f"[AuthorResolver] Querying for author: {name}")
        results = neo4j_connector.execute_query(query, {"name": name})
        logger.info(f"[AuthorResolver] Found {len(results)} candidates for {name}")

        if not results:
            return []

        candidates = []
        for r in results:
            # 清洗 sample_titles 中的每个标题
            raw_titles = r.get("sample_titles", [])
            cleaned_titles = [_sanitize_title(t) for t in raw_titles if t]

            candidates.append(AuthorCandidate(
                author_id=r.get("author_id", ""),  # 保持完整 URL 格式
                name=r.get("name", ""),
                paper_count=r.get("paper_count", 0),
                total_citations=r.get("total_citations", 0),
                max_citations=r.get("max_citations", 0),
                sample_titles=cleaned_titles,
                affiliation=None,  # 图数据库中没有 affiliation 字段
                research_areas=[]  # 图数据库中没有领域关系
            ))

        return candidates

    except Exception as e:
        logger.error(f"[AuthorResolver] Query failed for {name}: {str(e)}")
        return []


def _calculate_topic_similarity(
    research_areas: List[str],
    topic_hints: List[str]
) -> float:
    """
    计算研究主题与提示关键词的相似度。

    Args:
        research_areas: 作者的研究领域列表
        topic_hints: 提示的关键词列表

    Returns:
        float: 相似度分数 0-1
    """
    if not research_areas or not topic_hints:
        return 0.0

    areas_lower = [area.lower() for area in research_areas]
    hints_lower = [hint.lower() for hint in topic_hints]

    matches = 0
    for hint in hints_lower:
        for area in areas_lower:
            if hint in area or area in hint:
                matches += 1
                break

    return min(matches / len(hints_lower), 1.0)


def resolve_authors_from_decision(
    authors: List[str],
    topic_hints: Optional[List[str]] = None
) -> Dict[str, List[AuthorCandidate]]:
    """
    批量解析作者名。

    Args:
        authors: 作者名列表
        topic_hints: 研究主题关键词

    Returns:
        Dict[str, List[AuthorCandidate]]: 作者名到候选列表的映射
    """
    results = {}
    for author_name in authors:
        candidates = resolve_author_name_to_id(author_name, topic_hints)
        results[author_name] = candidates
    return results


def filter_candidates_by_topic(
    candidates: List[AuthorCandidate],
    topic_hints: List[str]
) -> List[AuthorCandidate]:
    """
    根据研究主题过滤候选作者。

    Args:
        candidates: 候选作者列表
        topic_hints: 研究主题关键词

    Returns:
        List[AuthorCandidate]: 过滤后的候选列表
    """
    if not topic_hints:
        return candidates

    filtered = []
    for candidate in candidates:
        score = _calculate_topic_similarity(
            candidate.research_areas,
            topic_hints
        )
        if score > 0.3:  # 相似度阈值
            candidate_copy = candidate.model_copy()
            candidate_copy.similarity_score = score
            filtered.append(candidate_copy)

    return filtered if filtered else candidates


def build_clarification_for_duplicate_authors(
    name: str,
    candidates: List[AuthorCandidate]
) -> str:
    """
    构建重名澄清问题。

    Args:
        name: 作者姓名
        candidates: 候选作者列表

    Returns:
        澄清问题文本
    """
    lines = [f"数据库中有 {len(candidates)} 位学者名叫「{name}」，请问您要找的是哪一位？\n"]

    for i, c in enumerate(candidates, 1):
        top_paper = c.sample_titles[0] if c.sample_titles else "(暂无代表作)"
        lines.append(
            f"{i}. 共 {c.paper_count} 篇论文，累计被引 {c.total_citations} 次\n"
            f"   代表作:《{top_paper}》"
        )

    lines.append("\n请回复编号 1/2/... 或直接说明特征（如机构、研究方向）。")
    return "\n".join(lines)


# ========================================
# Testing
# ========================================

def test_author_resolver():
    """Test author resolver with sample queries"""
    print("\n" + "="*60)
    print("Author Resolver Module Test")
    print("="*60 + "\n")

    test_names = ["Yao Xie", "Kai Wang", "Tuo Zhao"]

    for name in test_names:
        print(f"【查询】{name}")
        candidates = resolve_author_name_to_id(name)

        if not candidates:
            print("  ❌ 未找到匹配的作者")
        elif len(candidates) == 1:
            c = candidates[0]
            print(f"  ✅ 唯一匹配: {c.name}")
            print(f"     ID: {c.author_id[:40]}...")
            print(f"     论文数: {c.paper_count}")
            print(f"     研究领域: {', '.join(c.research_areas[:3])}")
        else:
            print(f"  ⚠️  找到 {len(candidates)} 个同名作者:")
            for i, c in enumerate(candidates[:3], 1):
                print(f"     {i}. {c.name}")
                print(f"        论文数: {c.paper_count}")
                print(f"        研究领域: {', '.join(c.research_areas[:3])}")
        print()

    print("="*60)


if __name__ == "__main__":
    test_author_resolver()
