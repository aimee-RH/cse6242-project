from langchain_core.tools import tool
from tools.neo4j_connector import neo4j_connector
from typing import Optional

@tool
def search_authors_by_name(
    author_name: str,
    research_field: Optional[str] = None,
    min_papers: int = 5,
    limit: int = 10
) -> str:
    """根据作者姓名搜索，支持通过研究领域过滤重名作者

    这是解决同名作者问题的关键工具。当数据库中有多个同名作者时，
    可以通过研究领域来区分和精确定位。

    Args:
        author_name: 作者姓名（支持模糊匹配）
        research_field: 研究领域（可选，用于区分同名作者。例如："Machine Learning", "Computer Vision"）
        min_papers: 最少论文数，过滤掉不活跃的作者（默认5）
        limit: 返回结果数量（默认10）

    Returns:
        匹配的作者列表，包含姓名、ID、论文数、研究领域等关键区分信息

    使用场景：
        - 用户只提供姓名："查找 Jing Liu"
          -> 返回所有同名作者及其研究领域，让用户选择

        - 用户提供姓名+领域："查找做机器学习的 Jing Liu"
          -> 返回该领域特定作者

        - 用户想确认某人："Jing Liu 是做计算机视觉的吗？"
          -> 搜索并验证研究领域是否匹配
    """
    # 构建动态查询
    if research_field:
        # 有研究领域过滤 - 更精确的查询
        query = """
        MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
        WHERE toLower(a.display_name) CONTAINS toLower($author_name)
          AND toLower(s.display_name) CONTAINS toLower($research_field)
        WITH a, count(DISTINCT p) as paper_count,
             sum(p.cited_by_count) as total_citations,
             collect(DISTINCT s.display_name)[0..5] as fields
        WHERE paper_count >= $min_papers
        RETURN a.display_name as name,
               a.id as author_id,
               paper_count,
               total_citations,
               fields
        ORDER BY paper_count DESC, total_citations DESC
        LIMIT $limit
        """
        params = {
            "author_name": author_name,
            "research_field": research_field,
            "min_papers": min_papers,
            "limit": limit
        }
    else:
        # 没有研究领域过滤 - 返回所有同名作者
        query = """
        MATCH (a:Author)
        WHERE toLower(a.display_name) CONTAINS toLower($author_name)
        OPTIONAL MATCH (a)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
        WITH a, count(DISTINCT p) as paper_count,
             sum(p.cited_by_count) as total_citations,
             collect(DISTINCT s.display_name)[0..5] as fields
        WHERE paper_count >= $min_papers
        RETURN a.display_name as name,
               a.id as author_id,
               paper_count,
               total_citations,
               fields
        ORDER BY paper_count DESC, total_citations DESC
        LIMIT $limit
        """
        params = {
            "author_name": author_name,
            "min_papers": min_papers,
            "limit": limit
        }

    # 打印执行的 Cypher 语句
    print(f"\n{'='*60}")
    print(f"🔍 [search_authors_by_name] 执行的 Cypher 语句:")
    print(f"{'='*60}")
    print(f"查询类型: {'有领域过滤' if research_field else '无领域过滤'}")
    print(f"\n{query}")
    print(f"\n参数: {params}")
    print(f"{'='*60}\n")

    try:
        results = neo4j_connector.execute_query(query, params)

        if not results:
            if research_field:
                return f"""未找到匹配的作者。

搜索条件：
- 姓名: {author_name}
- 研究领域: {research_field}

建议：
1. 检查姓名拼写是否正确
2. 尝试使用更通用的领域名称
3. 不指定研究领域，查看所有同名作者
4. 降低 min_papers 阈值"""
            else:
                return f"""未找到名为 "{author_name}" 的作者。

建议：
1. 检查姓名拼写
2. 尝试使用部分姓名（如只用姓或名）
3. 降低 min_papers 阈值（可能有作者但论文数较少）"""

        # 格式化输出
        if research_field:
            # 有领域过滤 - 精确匹配
            output = f"""在 **{research_field}** 领域找到 **{len(results)}** 位匹配 "{author_name}" 的作者：

"""
        else:
            # 无领域过滤 - 可能是重名情况
            output = f"""找到 **{len(results)}** 位名为 "{author_name}" 的作者：
（可能存在重名，请通过研究领域区分）

"""

        for i, author in enumerate(results, 1):
            fields = author.get('fields', [])
            fields_str = ', '.join(fields) if fields else '未知'

            output += f"""**{i}. {author['name']}**
   - ID: `{author['author_id']}`
   - 论文数: {author['paper_count']} 篇
   - 总引用: {author['total_citations']} 次
   - 研究领域: {fields_str}

"""

        # 添加消歧提示
        if len(results) > 1 and not research_field:
            output += f"""
⚠️ **发现多个同名作者**

为了精确定位，请提供更多信息：
- 作者的研究领域
- 作者的主要研究方向

例如："查找做机器学习的 {author_name}"
"""

        return output

    except Exception as e:
        return f"搜索作者时出错: {str(e)}"


@tool
def analyze_collaborations_by_name(
    author_name: str,
    research_field: Optional[str] = None,
    limit: int = 10
) -> str:
    """根据作者姓名查找其合作者（不需要 author_id）

    当你只知道作者姓名而想知道他的合作网络时，使用此工具。
    工具会自动找到作者并列出其主要合作者。

    Args:
        author_name: 作者姓名
        research_field: 研究领域（可选，用于区分同名作者）
        limit: 返回合作者数量，默认10

    Returns:
        作者的合作者列表，包含合作次数和合作者信息

    使用场景：
        - 用户问："Yao Xie 的合作者有哪些？"
        - 用户问："做机器学习的 Jing Liu 和谁合作最多？"
    """
    # 先找到作者
    search_query = """
    MATCH (a:Author)
    WHERE toLower(a.display_name) CONTAINS toLower($author_name)
    """

    if research_field:
        search_query += """
        MATCH (a)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
        WHERE toLower(s.display_name) CONTAINS toLower($research_field)
        """

    search_query += """
    WITH a, count(DISTINCT p) as paper_count
    ORDER BY paper_count DESC
    LIMIT 1
    RETURN a.id as author_id, a.display_name as name
    """

    # 打印执行的 Cypher 语句
    print(f"\n{'='*60}")
    print(f"🔍 [analyze_collaborations_by_name] 执行的 Cypher 语句:")
    print(f"{'='*60}")
    print(f"第一步：查找作者ID\n{search_query}")
    print(f"\n参数: author_name={author_name}, research_field={research_field}")
    print(f"{'='*60}\n")

    try:
        # 第一步：找到作者ID
        author_results = neo4j_connector.execute_query(
            search_query,
            {"author_name": author_name, "research_field": research_field}
        )

        if not author_results:
            if research_field:
                return f"""未找到在 {research_field} 领域名为 "{author_name}" 的作者。

建议：
1. 检查姓名拼写
2. 尝试不指定研究领域，查看所有同名作者
"""
            else:
                return f"""未找到名为 "{author_name}" 的作者。

建议：
1. 检查姓名拼写
2. 尝试使用部分姓名
"""

        author = author_results[0]
        author_id = author['author_id']
        author_real_name = author['name']

        # 第二步：查找合作者
        collab_query = """
        MATCH (a1:Author {id: $author_id})-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(a2:Author)
        WHERE a1.id <> a2.id
        WITH a2, count(p) as collaboration_count
        RETURN a2.display_name as collaborator_name,
               collaboration_count,
               a2.id as collaborator_id
        ORDER BY collaboration_count DESC
        LIMIT $limit
        """

        collab_results = neo4j_connector.execute_query(
            collab_query,
            {"author_id": author_id, "limit": limit}
        )

        if not collab_results:
            return f"""**{author_real_name}** 的合作网络

未找到合作者信息。可能原因：
1. 该作者主要以独立作者身份发表论文
2. 数据库中暂未收录其合作者数据
3. 该作者的合作者不在 Georgia Tech 数据库覆盖范围内

（找到作者：{author_real_name}，但无合作者记录）
"""

        # 格式化输出
        output = f"""**{author_real_name}** 的主要合作者（共 {len(collab_results)} 位）：

"""
        for i, collab in enumerate(collab_results, 1):
            output += f"""**{i}. {collab['collaborator_name']}**
   - 合作论文数: {collab['collaboration_count']} 篇
   - ID: {collab['collaborator_id']}

"""

        return output.strip()

    except Exception as e:
        return f"查询合作者时出错: {str(e)}"
