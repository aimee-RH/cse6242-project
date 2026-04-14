from tools.scholar_search import search_scholars_by_field
from tools.author_analysis import get_author_details
from tools.collaboration_analyzer import analyze_collaborations
from tools.trend_analyzer import find_trending_topics
from tools.advisor_recommender import recommend_advisors

# Export all tools
TOOLS = [
    search_scholars_by_field,
    get_author_details,
    analyze_collaborations,
    find_trending_topics,
    recommend_advisors,
]
