from langchain_core.tools import tool
from tools.neo4j_connector import neo4j_connector
from typing import Optional
import json
import os

def load_featured_scholars():
    """Load featured scholars from JSON file"""
    try:
        featured_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'featured_scholars.json')
        with open(featured_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('featured_scholars', {})
    except Exception as e:
        print(f"Warning: Could not load featured scholars: {e}")
        return {}

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

    # 加载featured scholars
    featured_scholars_map = load_featured_scholars()

    # 检查是否有匹配的featured scholars
    featured_scholars = []
    for field_key, field_scholars in featured_scholars_map.items():
        if research_field.lower() in field_key.lower() or field_key.lower() in research_field.lower():
            featured_scholars.extend(field_scholars)

    # 合并数据库结果和featured scholars
    all_scholars = []

    # 添加数据库结果
    seen_author_ids = set()
    for scholar in results:
        all_scholars.append({
            'type': 'database',
            'name': scholar['name'],
            'paper_count': scholar['paper_count'],
            'total_citations': scholar['total_citations'],
            'author_id': scholar['author_id']
        })
        seen_author_ids.add(scholar['author_id'])

    # 添加featured scholars（避免重复）
    for featured in featured_scholars:
        if featured['author_id'] not in seen_author_ids:
            # 获取featured scholar的实际论文数
            paper_count_query = """
            MATCH (a:Author {id: $author_id})-[:AUTHORED]->(p:Paper)
            RETURN count(p) as paper_count, sum(p.cited_by_count) as total_citations
            """
            paper_result = neo4j_connector.execute_query(
                paper_count_query,
                {"author_id": featured['author_id']}
            )

            paper_count = 0
            total_citations = 0
            if paper_result:
                paper_count = paper_result[0]['paper_count']
                total_citations = paper_result[0].get('total_citations', 0)

            all_scholars.append({
                'type': 'featured',
                'name': featured['name'],
                'paper_count': paper_count,
                'total_citations': total_citations,
                'author_id': featured['author_id'],
                'institution': featured.get('institution', 'N/A'),
                'research_interests': featured.get('research_interests', []),
                'description': featured.get('description', '')
            })
            seen_author_ids.add(featured['author_id'])

    # 按论文数排序
    all_scholars.sort(key=lambda x: x['paper_count'], reverse=True)

    if not all_scholars:
        return f"未找到领域 '{research_field}' 的学者，请尝试其他相关领域名称"

    # 格式化输出
    output = f"在 {research_field} 领域找到 {len(all_scholars)} 位学者：\\n\\n"
    for i, scholar in enumerate(all_scholars[:limit], 1):
        output += f"{i}. **{scholar['name']}**"

        # 标记featured学者
        if scholar.get('type') == 'featured':
            output += " ⭐ Featured"

        output += "\\n"
        output += f"   - 论文数: {scholar['paper_count']}\\n"
        output += f"   - 总引用: {scholar['total_citations']}\\n"

        if scholar.get('type') == 'featured':
            if scholar.get('institution'):
                output += f"   - 机构: {scholar['institution']}\\n"
            if scholar.get('research_interests'):
                output += f"   - 研究兴趣: {', '.join(scholar['research_interests'])}\\n"
            if scholar.get('description'):
                output += f"   - 简介: {scholar['description']}\\n"

        output += f"   - ID: {scholar['author_id']}\\n\\n"

    return output
