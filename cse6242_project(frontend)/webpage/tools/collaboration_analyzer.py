from langchain_core.tools import tool
from tools.neo4j_connector import neo4j_connector

@tool
def analyze_collaborations(author_id: str, limit: int = 10) -> str:
    """分析学者的合作网络

    Args:
        author_id: 作者的 OpenAlex ID
        limit: 返回合作者数量，默认 10

    Returns:
        JSON 字符串，包含主要合作者及其合作次数
    """
    query = """
    MATCH (a1:Author {id: $author_id})-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(a2:Author)
    WHERE a1.id <> a2.id
    WITH a2, count(p) as collaboration_count
    RETURN a2.display_name as collaborator_name,
           collaboration_count,
           a2.id as collaborator_id
    ORDER BY collaboration_count DESC
    LIMIT $limit
    """

    try:
        results = neo4j_connector.execute_query(
            query,
            {"author_id": author_id, "limit": limit}
        )

        if not results:
            return f"未找到作者 {author_id} 的合作者信息。\\n\\n可能原因：\\n1. 作者 ID 不正确\\n2. 该作者没有发表论文\\n3. 数据库中暂无该作者的合作记录"

        # 格式化输出
        output = f"**合作者分析**（共 {len(results)} 位）：\\n\\n"
        for i, collab in enumerate(results, 1):
            output += f"{i}. **{collab['collaborator_name']}**\\n"
            output += f"   - 合作论文数: {collab['collaboration_count']} 篇\\n"
            output += f"   - ID: {collab['collaborator_id']}\\n\\n"

        return output

    except Exception as e:
        return f"查询合作者信息时出错: {str(e)}\\n\\n建议使用搜索功能重新查找该作者。"
