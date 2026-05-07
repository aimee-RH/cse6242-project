from langchain_core.tools import tool
from tools.neo4j_connector import neo4j_connector

@tool
def find_trending_topics(field: str, year_threshold: int = 2020) -> str:
    """Discover popular research topics in a specific field

    Args:
        field: Research field name
        year_threshold: Only consider papers after this year, default 2020

    Returns:
        JSON string containing highly cited papers and their topics
    """
    query = """
    MATCH (p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
    WHERE toLower(s.display_name) CONTAINS toLower($field)
      AND p.publication_year >= $year_threshold
    RETURN p.title as paper_title,
           p.cited_by_count as citations,
           p.publication_year as year,
           s.display_name as subfield
    ORDER BY p.cited_by_count DESC
    LIMIT 20
    """

    results = neo4j_connector.execute_query(
        query,
        {"field": field, "year_threshold": year_threshold}
    )
    return str(results)
