from langchain_core.tools import tool
from tools.neo4j_connector import neo4j_connector
from typing import Optional

@tool
def search_scholars_by_field(
    research_field: str,
    limit: int = 10,
    min_papers: int = 5
) -> str:
    """根据研究领域搜索相关学者

    Args:
        research_field: 研究领域名称（如 "Machine Learning", "Computer Vision", "Statistics"）
        limit: 返回结果数量，默认 10
        min_papers: 最少论文数，默认 5

    Returns:
        学者列表，包含姓名、论文数、引用数等
    """
    query = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
    WHERE toLower(s.display_name) CONTAINS toLower($research_field)
    WITH a, count(p) as paper_count, sum(p.cited_by_count) as total_citations
    WHERE paper_count >= $min_papers
    RETURN a.display_name as name,
           paper_count,
           total_citations,
           a.id as author_id
    ORDER BY paper_count DESC, total_citations DESC
    LIMIT $limit
    """

    results = neo4j_connector.execute_query(
        query,
        {
            "research_field": research_field,
            "limit": limit,
            "min_papers": min_papers
        }
    )

    if not results:
        return f"未找到领域 '{research_field}' 的学者，请尝试其他相关领域名称"

    # 格式化输出
    output = f"在 {research_field} 领域找到 {len(results)} 位学者：\\n\\n"
    for i, scholar in enumerate(results, 1):
        output += f"{i}. **{scholar['name']}**\\n"
        output += f"   - 论文数: {scholar['paper_count']}\\n"
        output += f"   - 总引用: {scholar['total_citations']}\\n"
        output += f"   - ID: {scholar['author_id']}\\n\\n"

    return output
