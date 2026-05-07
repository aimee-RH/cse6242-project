"""
Query Templates Module

预定义的 Cypher 模板库，用于高频查询模式。
模板命中可避免 LLM 调用，提高响应速度和稳定性。

Author: Scholar Compass Team
Date: 2025-04-22
"""

import re
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from graph.schemas import EntitySet


def _extract_limit_from_query(query: str, default: int = 5) -> int:
    """从查询中提取数字 N（用于 top N 查询）"""
    # 匹配 "top 5"、"top5"、"前 5"、"前5"、"5 篇" 等模式
    patterns = [
        r'top\s*(\d+)',
        r'前\s*(\d+)',
        r'(\d+)\s*篇',
        r'最高?\s*(\d+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            try:
                return min(int(match.group(1)), 20)  # 最多返回 20 条
            except ValueError:
                pass
    return default


def _has_time_query(query: str) -> bool:
    """检查查询是否涉及时间范围"""
    time_keywords = [
        '最近', '近几年', '近年', '近期',
        '2020', '2021', '2022', '2023', '2024', '2025', '2026',
        '到', '至', '期间', '以来'
    ]
    query_lower = query.lower()
    for keyword in time_keywords:
        if keyword in query_lower:
            return True
    return False


def _check_top_papers_keywords(query: str) -> bool:
    """检查是否是 top papers 查询"""
    keywords = [
        'top', '高被引', '最高引用', '引用最多', '被引最多',
        '排名', '前', '热门', '知名'
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in keywords)


def _check_paper_count_keywords(query: str) -> bool:
    """检查是否是论文数统计查询"""
    keywords = [
        '多少篇', '几篇', '发过', '发表了', '论文数',
        'publication count', 'number of papers', 'how many'
    ]
    query_lower = query.lower()
    return any(kw in query_lower for kw in keywords)


def try_match_template(query: str, entities: Any, query_shape: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    按优先级尝试匹配模板。

    Args:
        query: 用户查询
        entities: 路由层解析的实体
        query_shape: 查询形态 hint

    Returns:
        命中的模板信息，包含 cypher、params、output_hint
        未命中返回 None
    """
    # 模板 1: author_top_papers - 作者高被引论文
    if _match_author_top_papers(query, entities, query_shape):
        return _build_author_top_papers_template(query, entities)

    # 模板 2: author_paper_count - 作者论文数统计
    if _match_author_paper_count(query, entities, query_shape):
        return _build_author_paper_count_template(entities)

    # 模板 3: author_recent_papers - 作者近期论文
    if _match_author_recent_papers(query, entities):
        return _build_author_recent_papers_template(entities)

    # 模板 4: multi_author_duplicate_info - 重名作者对比
    if _match_multi_author_duplicate(entities):
        return _build_multi_author_duplicate_template(entities)

    # 模板 5: single_paper_details - 论文详情
    if _match_single_paper(entities):
        return _build_single_paper_template(entities)

    # 未命中任何模板
    return None


# ==================== 模板匹配函数 ====================

def _match_author_top_papers(query: str, entities: Any, query_shape: Optional[str]) -> bool:
    """匹配条件：top papers 查询 + 单个已解析作者"""
    if not _check_top_papers_keywords(query):
        return False
    if len(entities.authors) != 1:
        return False
    author = entities.authors[0]
    if not author.author_id or author.candidates:
        return False
    return True


def _match_author_paper_count(query: str, entities: Any, query_shape: Optional[str]) -> bool:
    """匹配条件：论文数统计查询 + 单个已解析作者"""
    if not _check_paper_count_keywords(query):
        return False
    if len(entities.authors) != 1:
        return False
    author = entities.authors[0]
    if not author.author_id or author.candidates:
        return False
    # 排除包含 "top" 的查询（可能命中 top_papers 模板）
    if 'top' in query.lower() or '高被引' in query.lower():
        return False
    return True


def _match_author_recent_papers(query: str, entities: Any) -> bool:
    """匹配条件：有时间范围 + 单个已解析作者"""
    if not entities.time_range:
        return False
    if len(entities.authors) != 1:
        return False
    author = entities.authors[0]
    if not author.author_id or author.candidates:
        return False
    return True


def _match_multi_author_duplicate(entities: Any) -> bool:
    """匹配条件：有候选作者（用户刚经历重名澄清）"""
    if len(entities.authors) != 1:
        return False
    author = entities.authors[0]
    return len(author.candidates) > 0


def _match_single_paper(entities: Any) -> bool:
    """匹配条件：有 paper_id"""
    return len(entities.paper_ids) > 0


# ==================== 模板构建函数 ====================

def _build_author_top_papers_template(query: str, entities: Any) -> Dict[str, Any]:
    """构建作者高被引论文模板"""
    author = entities.authors[0]
    limit = _extract_limit_from_query(query, default=5)

    return {
        "cypher": """
MATCH (a:Author {id: $author_id})-[:AUTHORED]->(p:Paper)
RETURN p.title AS title,
       p.cited_by_count AS citations,
       p.publication_year AS year,
       p.id AS paper_id
ORDER BY p.cited_by_count DESC
LIMIT $limit
        """.strip(),
        "params": {
            "author_id": author.author_id,
            "limit": limit,
        },
        "output_hint": "top_papers",
    }


def _build_author_paper_count_template(entities: Any) -> Dict[str, Any]:
    """构建作者论文数统计模板"""
    author = entities.authors[0]

    return {
        "cypher": """
MATCH (a:Author {id: $author_id})-[:AUTHORED]->(p:Paper)
RETURN count(p) AS paper_count,
       sum(p.cited_by_count) AS total_citations,
       max(p.cited_by_count) AS max_citations,
       avg(p.fwci) AS avg_fwci
        """.strip(),
        "params": {
            "author_id": author.author_id,
        },
        "output_hint": "paper_count",
    }


def _build_author_recent_papers_template(entities: Any) -> Dict[str, Any]:
    """构建作者近期论文模板"""
    author = entities.authors[0]
    time_range = entities.time_range

    return {
        "cypher": """
MATCH (a:Author {id: $author_id})-[:AUTHORED]->(p:Paper)
WHERE p.publication_year >= $start_year AND p.publication_year <= $end_year
RETURN p.title AS title,
       p.cited_by_count AS citations,
       p.publication_year AS year,
       p.id AS paper_id
ORDER BY p.publication_year DESC, p.cited_by_count DESC
LIMIT 20
        """.strip(),
        "params": {
            "author_id": author.author_id,
            "start_year": time_range.start_year,
            "end_year": time_range.end_year,
        },
        "output_hint": "recent_papers",
    }


def _build_multi_author_duplicate_template(entities: Any) -> Dict[str, Any]:
    """
    构建重名作者对比模板。
    这个模板直接从 candidates 构造结果，不执行 Cypher。
    """
    author = entities.authors[0]

    return {
        "cypher": None,  # 标记不需要执行 Cypher
        "params": {},
        "output_hint": "duplicate_authors",
        "candidates": author.candidates,  # 直接使用已解析的 candidates
    }


def _build_single_paper_template(entities: Any) -> Dict[str, Any]:
    """构建单篇论文详情模板"""
    paper_id = entities.paper_ids[0]

    return {
        "cypher": """
MATCH (p:Paper {id: $paper_id})
OPTIONAL MATCH (a:Author)-[:AUTHORED]->(p)
RETURN p.title AS title,
       p.cited_by_count AS citations,
       p.publication_year AS year,
       p.fwci AS fwci,
       collect(a.display_name)[..5] AS authors
        """.strip(),
        "params": {
            "paper_id": paper_id,
        },
        "output_hint": "paper_details",
    }
