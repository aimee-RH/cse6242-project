from langchain_core.tools import tool
from tools.neo4j_connector import neo4j_connector

@tool
def get_author_details(author_id: str) -> str:
    """获取学者的详细信息

    Args:
        author_id: 作者的 OpenAlex ID（如 "https://openalex.org/A1234567890"）

    Returns:
        JSON 字符串，包含作者的所有论文、研究领域、影响力指标等
    """
    # 使用精确ID查询
    query = """
    MATCH (a:Author {id: $author_id})
    OPTIONAL MATCH (a)-[r:AUTHORED]->(p:Paper)
    OPTIONAL MATCH (p)-[:IN_SUBFIELD]->(s:Subfield)
    WITH a, count(DISTINCT p) as total_papers,
         sum(p.cited_by_count) as total_citations,
         avg(p.fwci) as avg_fwci,
         collect(DISTINCT s.display_name)[0..10] as research_fields,
         collect(DISTINCT p.title)[0..5] as recent_papers
    RETURN a.display_name as name,
           a.id as author_id,
           total_papers,
           total_citations,
           avg_fwci,
           research_fields,
           recent_papers
    """

    try:
        results = neo4j_connector.execute_query(query, {"author_id": author_id})

        if not results:
            return f"未找到 ID 为 {author_id} 的作者。建议：1) 通过搜索功能查找该作者 2) 检查 ID 是否完整 3) 尝试使用作者姓名搜索"

        author_info = results[0]

        # 格式化返回结果
        fields = author_info.get('research_fields', [])
        papers = author_info.get('recent_papers', [])

        output = f"""**作者详细信息**

**姓名**: {author_info.get('name', 'N/A')}
**ID**: {author_info.get('author_id', 'N/A')}
**论文数**: {author_info.get('total_papers', 0)} 篇
**总引用数**: {author_info.get('total_citations', 0)} 次
**平均 FWCI**: {author_info.get('avg_fwci', 0):.2f}

**研究领域**:
{chr(10).join([f"- {field}" for field in fields])}

**部分论文**:
{chr(10).join([f"- {paper[:80]}..." for paper in papers[:3]])}
"""
        return output

    except Exception as e:
        return f"查询作者信息时出错: {str(e)}\\n\\n建议使用搜索功能重新查找该作者。"
