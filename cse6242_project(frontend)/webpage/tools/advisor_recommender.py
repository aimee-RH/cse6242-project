from langchain_core.tools import tool
from tools.neo4j_connector import neo4j_connector

@tool
def recommend_advisors(
    research_interest: str,
    limit: int = 5,
    min_fwci: float = 1.0
) -> str:
    """Recommend potential advisors based on research interests

    Args:
        research_interest: Research interest keywords
        limit: Number of recommendations, default 5
        min_fwci: Minimum FWCI (impact metric), default 1.0

    Returns:
        JSON string containing recommended advisor list and reasoning
    """
    query = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
    WHERE toLower(s.display_name) CONTAINS toLower($research_interest)
      OR toLower(p.title) CONTAINS toLower($research_interest)
    WITH a, avg(p.fwci) as avg_fwci, count(p) as paper_count
    WHERE avg_fwci >= $min_fwci AND paper_count >= 10
    RETURN a.display_name as name,
           avg_fwci,
           paper_count,
           a.id as author_id
    ORDER BY avg_fwci DESC, paper_count DESC
    LIMIT $limit
    """

    results = neo4j_connector.execute_query(
        query,
        {
            "research_interest": research_interest,
            "limit": limit,
            "min_fwci": min_fwci
        }
    )
    return str(results)
