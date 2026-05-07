#!/usr/bin/env python3
"""
Text2Cypher Module - Dynamic Graph Retrieval Core

This module implements Text-to-Cypher generation using LLM, enabling
dynamic graph queries that go beyond hardcoded Cypher statements.

Key Features:
1. Schema-aware Cypher generation
2. Automatic error retry mechanism
3. Scholar name disambiguation
4. Query result formatting and validation
5. Detailed execution logging
6. NEW: Entity-aware generation (receives pre-resolved entities from routing layer)

Author: Scholar Compass Team
Date: 2025-04-16
Updated: 2025-04-22 (added generate_cypher_with_entities)
"""

from langchain_core.tools import tool
import time
from utils.logger import get_logger, log_cypher_generation, log_cypher_execution
from tools.neo4j_connector import neo4j_connector
from langchain_openai import ChatOpenAI
import os
import json
import re
import logging
from typing import Optional, List, Dict, Any, Tuple

# 配置日志备用
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)

# 导入 EntitySet 用于新接口
from graph.schemas import EntitySet


# Initialize LLM for Cypher generation
# Supports multiple models: MiniMax, gpt-4o, qwen-plus, etc.
def _get_cypher_llm():
    """Initialize LLM for Cypher generation with environment-aware configuration"""
    api_key = os.getenv("MINIMAX_API_KEY", "")
    base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
    model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.7")

    if not api_key:
        raise ValueError(
            "❌ MINIMAX_API_KEY not set!\n"
            "Please set: export MINIMAX_API_KEY='your-api-key'\n"
            "Get your key at: https://platform.minimaxi.com/"
        )

    return ChatOpenAI(
        model=model,
        temperature=0,  # Temperature 0 for deterministic Cypher generation
        top_p=1.0,  # Disable nucleus sampling for more deterministic output
        api_key=api_key,
        base_url=base_url,
        model_kwargs={
            "seed": 42  # Fixed seed for reproducibility (if supported by API)
        }
    )


# Global LLM instance (lazy initialization)
_cypher_llm = None


def get_cypher_llm():
    """Get or create LLM instance (singleton pattern)"""
    global _cypher_llm
    if _cypher_llm is None:
        _cypher_llm = _get_cypher_llm()
    return _cypher_llm


def _get_graph_schema() -> str:
    """
    Get Neo4j graph schema and format it as a prompt.

    Returns:
        Formatted schema description for LLM
    """
    return """
【Neo4j Graph Database Schema】

📊 Node Labels and Properties:

1. Author (Scholar Node)
   - id: Unique identifier (OpenAlex ID)
   - display_name: Full name of the scholar

2. Paper (Publication Node)
   - id: Unique identifier
   - title: Paper title
   - publication_year: Year published
   - cited_by_count: Citation count
   - fwci: Field Weighted Citation Impact (normalized impact metric)

3. Subfield (Research Area Node)
   - id: Unique identifier
   - display_name: Name of research subfield

4. Source (Venue Node - Journal/Conference)
   - id: Unique identifier
   - display_name: Name of journal or conference

🔗 Relationship Types:

- (:Author)-[:AUTHORED]->(:Paper): Scholar authored a paper
- (:Paper)-[:IN_SUBFIELD]->(:Subfield): Paper belongs to a research field
- (:Paper)-[:PUBLISHED_IN]->(:Source): Paper published in a venue

📋 Query Rules (CRITICAL):

1. Schema Strictness:
   - ONLY use nodes, relationships, and properties defined above
   - NEVER invent non-existent labels, relationships, or properties
   - ALL queries must be executable without errors

2. Scholar Name Matching:
   - Use fuzzy matching: toLower(a.display_name) CONTAINS toLower($name)
   - For duplicate names, rank by paper count: count(p) DESC
   - Example: WHERE toLower(a.display_name) CONTAINS toLower('Yao Xie')

3. Performance & Limits:
   - All queries MUST have LIMIT clause (max 20-50 results)
   - Avoid full table scans - always use WHERE clauses
   - Use ORDER BY for meaningful results

4. Syntax Requirements:
   - Compatible with Neo4j 5.x Cypher syntax
   - Use parameterized queries where possible
   - Return meaningful aliases for readability

⚠️ Common Mistakes to Avoid:
- Using non-existent properties like 'author_name' (use 'display_name')
- Forgetting LIMIT clause (causes performance issues)
- Missing relationship direction ([:AUTHORED] is directed)
- Case-sensitive string comparisons (use toLower() for matching)
"""


def _get_few_shot_examples() -> str:
    """
    Get few-shot examples for Text2Cypher generation.

    Returns:
        Formatted examples demonstrating various query types
    """
    return """
【Query Examples - Few-Shot Learning】

Example 1: Author lookup (with potential duplicates) - FIXED LIMIT for consistency
User Question: "Find information about Tuo Zhao"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)
WHERE toLower(a.display_name) CONTAINS toLower('Tuo Zhao')
WITH a, count(p) as paper_count,
     sum(p.cited_by_count) as total_citations,
     avg(p.fwci) as avg_fwci
WHERE paper_count >= 1
ORDER BY paper_count DESC, total_citations DESC
LIMIT 10
```
Note: Always use LIMIT 10 for author queries to ensure consistent results across multiple runs.

Example 2: High-cited papers query
User Question: "What are Yao Xie's Top 3 most cited papers?"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)
WHERE toLower(a.display_name) CONTAINS toLower('Yao Xie')
RETURN p.title as title, p.cited_by_count as citations
ORDER BY p.cited_by_count DESC
LIMIT 3
```

Example 2: Research field analysis
User Question: "Find the top 10 scholars in Machine Learning field"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
WHERE toLower(s.display_name) CONTAINS toLower('Machine Learning')
WITH a, count(p) as paper_count, sum(p.cited_by_count) as total_citations
WHERE paper_count >= 5
RETURN a.display_name as name, paper_count, total_citations
ORDER BY paper_count DESC, total_citations DESC
LIMIT 10
```

Example 3: Collaboration network
User Question: "Who are Jing Liu's top 5 collaborators?"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(co:Author)
WHERE toLower(a.display_name) CONTAINS toLower('Jing Liu')
  AND co.id <> a.id
WITH co, count(p) as collaboration_strength
RETURN co.display_name as collaborator_name, collaboration_strength
ORDER BY collaboration_strength DESC
LIMIT 5
```

Example 4: Topic evolution over time
User Question: "How has Yao Xie's research focus evolved from 2018 to 2023?"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
WHERE toLower(a.display_name) CONTAINS toLower('Yao Xie')
  AND p.publication_year >= 2018
  AND p.publication_year <= 2023
RETURN p.publication_year as year,
       s.display_name as research_topic,
       count(p) as papers_count
ORDER BY year ASC, papers_count DESC
LIMIT 50
```

Example 5: Recent publications
User Question: "Show me the latest 5 papers by scholars in Computer Vision field"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
WHERE toLower(s.display_name) CONTAINS toLower('Computer Vision')
RETURN a.display_name as author_name,
       p.title as paper_title,
       p.publication_year as year,
       p.cited_by_count as citations
ORDER BY p.publication_year DESC
LIMIT 5
```

Example 6: Impact analysis
User Question: "Which scholars have the highest average FWCI in Database field?"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
WHERE toLower(s.display_name) CONTAINS toLower('Database')
WITH a, avg(p.fwci) as avg_fwci, count(p) as paper_count
WHERE paper_count >= 10
RETURN a.display_name as name, avg_fwci, paper_count
ORDER BY avg_fwci DESC
LIMIT 10
```
"""


def _get_comparison_few_shot_examples() -> str:
    """
    Get few-shot examples specifically for comparison queries.

    Returns:
        Formatted comparison query examples
    """
    return """
【Comparison Query Examples - Multi-Scholar Analysis】⭐

Example 1: Three scholars comparison
User Question: "对比 Yao Xie、Kai Wang、Tuo Zhao 三位学者的学术指标，包括论文数、引用数和研究领域"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)
WHERE ANY(n IN ['yao xie', 'kai wang', 'tuo zhao']
          WHERE toLower(a.display_name) CONTAINS n)
WITH a, count(p) as paper_count,
     sum(p.cited_by_count) as total_citations,
     avg(p.fwci) as avg_fwci
RETURN a.display_name as scholar_name,
       paper_count,
       total_citations,
       avg_fwci
ORDER BY paper_count DESC
// ⚠️ CRITICAL: Comparison queries MUST NOT use LIMIT in the middle!
// Each entity must be returned for proper comparison.
```

Example 2: Two scholars collaboration network comparison
User Question: "对比 Yao Xie 和 Jing Liu 的主要合作者"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(co:Author)
WHERE ANY(n IN ['yao xie', 'jing liu']
          WHERE toLower(a.display_name) CONTAINS n)
WITH a, co, count(p) as collaboration_count
RETURN a.display_name as scholar_name,
       collect({
         collaborator: co.display_name,
         count: collaboration_count
       })[0..5] as top_collaborators
ORDER BY scholar_name
// ⚠️ Return ALL specified scholars, do NOT limit to single result
```

Example 3: Multiple scholars research field comparison
User Question: "对比 Yao Xie、Kai Wang、Tuo Zhao 的研究领域分布"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
WHERE ANY(n IN ['yao xie', 'kai wang', 'tuo zhao']
          WHERE toLower(a.display_name) CONTAINS n)
WITH a, s.display_name as field_name, count(p) as paper_count
RETURN a.display_name as scholar_name,
       collect({
         field: field_name,
         papers: paper_count
       })[0..5] as research_fields
ORDER BY scholar_name
// Return ALL scholars with their field distributions
```

⚠️ COMPARISON QUERY CRITICAL RULES:
1. NEVER use LIMIT in the middle of the query - MUST return ALL comparison entities
2. Use WHERE ANY(...) IN [...] for fuzzy matching (handles name variants)
3. Use WITH to aggregate per entity, then RETURN ALL entities
4. Final ORDER BY is OK, but intermediate LIMIT will break comparison
5. Each comparison entity (scholar/paper) must have its own data row
6. For scholar matching: ANY(n IN ['name1', 'name2'] WHERE toLower(a.display_name) CONTAINS n)
"""


def _get_multi_hop_few_shot_examples() -> str:
    """
    Get few-shot examples for multi-hop queries.

    Returns:
        Formatted multi-hop query examples
    """
    return """
【Multi-Hop Query Examples - Complex Relationship Traversal】

Example 1: Collaborators of collaborators (2-hop)
User Question: "Yao Xie 的合作者中，哪些人也和 Jing Liu 合作过？"
Generated Cypher:
```cypher
MATCH (a1:Author)-[:AUTHORED]->(p1:Paper)<-[:AUTHORED]-(co:Author)
WHERE toLower(a1.display_name) CONTAINS toLower('Yao Xie')
MATCH (co)-[:AUTHORED]->(p2:Paper)<-[:AUTHORED]-(a2:Author)
WHERE toLower(a2.display_name) CONTAINS toLower('Jing Liu')
  AND co.id <> a1.id AND co.id <> a2.id
WITH co, count(DISTINCT p1) + count(DISTINCT p2) as total_collab
RETURN co.display_name as collaborator_name,
       total_collab
ORDER BY total_collab DESC
LIMIT 10
```

Example 2: Cross-field collaboration analysis (3-hop)
User Question: "从 Yao Xie 的研究主题到 Machine Learning 领域的关联路径"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p1:Paper)-[:IN_SUBFIELD]->(s1:Subfield)
WHERE toLower(a.display_name) CONTAINS toLower('Yao Xie')
MATCH (p1)-[:IN_SUBFIELD]->(s2:Subfield)
WHERE toLower(s2.display_name) CONTAINS toLower('Machine Learning')
  AND s1 <> s2
RETURN DISTINCT s1.display_name as from_topic,
                s2.display_name as to_topic,
                count(p1) as paper_bridge_count
ORDER BY paper_bridge_count DESC
LIMIT 20
```

⚠️ MULTI-HOP CRITICAL RULES:
1. Use separate variable names for each hop (p1, p2 instead of reusing p)
2. Limit hops to 2-3 max for performance
3. ALWAYS use LIMIT at the end (multi-hop can explode)
4. Use DISTINCT to avoid duplicates
5. Only use relationships defined in schema (AUTHORED, IN_SUBFIELD, PUBLISHED_IN)
"""


def _get_aggregation_few_shot_examples() -> str:
    """
    Get few-shot examples for aggregation queries.

    Returns:
        Formatted aggregation query examples
    """
    return """
【Aggregation Query Examples - Statistical Analysis】

Example 1: Top scholars by paper count
User Question: "Machine Learning 领域论文数最多的前 10 位学者"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
WHERE toLower(s.display_name) CONTAINS toLower('Machine Learning')
WITH a, count(p) as paper_count
ORDER BY paper_count DESC
LIMIT 10
RETURN a.display_name as scholar_name, paper_count
```

Example 2: Average FWCI calculation
User Question: "Computer Vision 领域学者的平均 FWCI 是多少？"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
WHERE toLower(s.display_name) CONTAINS toLower('Computer Vision')
WITH a, avg(p.fwci) as avg_fwci, count(p) as paper_count
WHERE paper_count >= 5  // Only active scholars
RETURN avg(avg_fwci) as field_avg_fwci,
       count(a) as total_scholars
```

Example 3: Distribution statistics
User Question: "统计学者论文数的分布情况"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)
WITH a, count(p) as paper_count
WITH CASE
        WHEN paper_count <= 10 THEN '1-10'
        WHEN paper_count <= 50 THEN '11-50'
        WHEN paper_count <= 100 THEN '51-100'
        ELSE '100+'
     END as range_category,
     count(a) as scholar_count
RETURN range_category, scholar_count
ORDER BY range_category
```

⚠️ AGGREGATION CRITICAL RULES:
1. Use aggregation functions: count(), sum(), avg(), max(), min()
2. Use GROUP BY for grouping
3. Use ORDER BY + LIMIT for top-N results
4. Handle NULL values with coalesce() if needed
"""


def _build_task_specific_prompt(
    query_type: str,
    schema: str,
    examples: str,
    referenced_scholars: Optional[List[str]] = None
) -> str:
    """
    Build task-specific system prompt for Cypher generation.

    Args:
        query_type: Type of query (single_lookup/comparison/aggregation/multi_hop/recommendation)
        schema: Graph schema description
        examples: Few-shot examples
        referenced_scholars: Optional list of mentioned scholars

    Returns:
        Task-specific system prompt
    """
    # Base instructions
    base_instructions = f"""You are an expert Neo4j Cypher query generator.

{schema}

{examples}

🎯 Your Task:
Generate a Cypher query to answer the user's question."""

    # Task-specific instructions
    if query_type == "comparison":
        task_rules = """

📝 COMPARISON QUERY REQUIREMENTS ⭐:
1. **CRITICAL**: NEVER use LIMIT in the middle of the query!
2. MUST return ALL comparison entities (every scholar/paper mentioned)
3. Use WHERE ANY(...) IN [...] for fuzzy matching (handles name variants)
4. Use WITH to aggregate per entity, then RETURN all entities
5. Final ORDER BY is acceptable, but intermediate LIMIT will break comparison
6. Use meaningful aliases: scholar_name, paper_count, total_citations, etc.

⚠️ COMPARISON QUERY CRITICAL RULES:
- NEVER do: WITH ... ORDER BY ... LIMIT 1 (this returns only 1 entity!)
- ALWAYS do: WITH ... (aggregate per entity) ... RETURN ... (all entities)
- If comparing 3 scholars, MUST return 3 rows (one per scholar)
- Use fuzzy matching: ANY(n IN ['A', 'B', 'C'] WHERE toLower(a.display_name) CONTAINS n)

❌ WRONG (returns only 1 scholar):
```cypher
MATCH ...
WHERE ... OR ... OR ...
WITH a, count(p) ... ORDER BY ... LIMIT 1  // ❌ DON'T DO THIS!
RETURN ...
```

✅ CORRECT (returns all 3 scholars):
```cypher
MATCH ...
WHERE ANY(n IN ['A', 'B', 'C'] WHERE toLower(a.display_name) CONTAINS n)
WITH a, count(p) as paper_count
RETURN a.display_name, paper_count  // ✅ Returns all 3 scholars
```
"""
    elif query_type == "multi_hop":
        task_rules = """

📝 MULTI-HOP QUERY REQUIREMENTS:
1. Use variable-length paths: (a)-[:REL*1..N]->(b)
2. Limit hops to 2-3 max for performance
3. ALWAYS use LIMIT at the end (multi-hop can explode)
4. Use DISTINCT to avoid duplicates
5. Consider performance - use selective WHERE clauses

⚠️ MULTI-HOP CRITICAL RULES:
- Test with 1 hop first, then extend to 2-3 hops
- Always LIMIT results (recommended: 10-20)
- Use path only when necessary, prefer direct matches when possible
"""
    elif query_type == "aggregation":
        task_rules = """

📝 AGGREGATION QUERY REQUIREMENTS:
1. Use aggregation functions: count(), sum(), avg(), max(), min()
2. Use GROUP BY for grouping
3. Use ORDER BY + LIMIT for top-N results
4. Handle NULL values with coalesce()

⚠️ AGGREGATION CRITICAL RULES:
- Always LIMIT aggregation results (recommended: 10-50)
- Use coalesce() for potentially NULL values
- Consider performance when aggregating large datasets
"""
    else:  # single_lookup
        task_rules = """

📝 SINGLE LOOKUP QUERY REQUIREMENTS:
1. Query single entity (scholar/paper/field)
2. Use LIMIT to restrict results (recommended: 10-20)
3. Use ORDER BY to return most relevant results
4. Use fuzzy matching for scholar names

⚠️ GENERAL CRITICAL RULES:
- ALWAYS include LIMIT clause
- Use toLower() for case-insensitive matching
- Use meaningful aliases for returned columns
"""

    # Common rules
    common_rules = """

📝 GENERAL OUTPUT REQUIREMENTS:
1. **IMPORTANT**: Output ONLY the Cypher query - NO reasoning, explanations
2. Start your response immediately with a Cypher keyword (MATCH, CREATE, MERGE, WITH)
3. Query must be directly executable in Neo4j 5.x
4. Must follow all schema rules defined above
5. Use meaningful aliases for returned columns

⚠️ GENERAL CRITICAL RULES:
- NEVER invent nodes, relationships, or properties not in the schema
- ALWAYS use toLower() for case-insensitive string matching
- If query involves a specific scholar, use fuzzy name matching
- For duplicate names, order by paper count DESC, total_citations DESC
- **DO NOT** include any text before the Cypher query
- **DO NOT** explain your thought process
- **ALWAYS use fixed LIMIT value: LIMIT 10** (for comparison queries, return all entities without LIMIT)
- For author name queries, ALWAYS include: ORDER BY paper_count DESC, total_citations DESC LIMIT 10

❌ Wrong format:
"Let me think about this... First I need to MATCH..."
"Here's the query that will help: MATCH..."

✅ Correct format:
"MATCH (a:Author)-[:AUTHORED]->(p:Paper) WHERE..."

Now, generate the Cypher query for the user's question. Start immediately with a Cypher keyword."""

    return base_instructions + task_rules + common_rules


def _extract_scholar_name(query: str) -> Optional[str]:
    """
    Extract scholar name from user query using simple patterns.

    Args:
        query: User's natural language question

    Returns:
        Extracted scholar name or None
    """
    # Pattern 1: "X的问题" or "X的..."
    pattern1 = r'([A-Z][a-z]+\s+[A-Z][a-z]+|[\u4e00-\u9fa5]{2,4})(的|的)?'
    matches = re.findall(pattern1, query)

    if matches:
        # Return the first matched name
        return matches[0][0]

    # Pattern 2: Explicit "scholar X" or "professor X"
    pattern2 = r'(?:scholar|professor|学者|教授)\s*[:：]?\s*([A-Z][a-z]+\s+[A-Z][a-z]+|[\u4e00-\u9fa5]{2,4})'
    match = re.search(pattern2, query, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


def _generate_cypher_from_query(
    user_query: str,
    scholar_name: Optional[str] = None,
    retry_count: int = 0,
    query_type: str = "single_lookup",
    referenced_scholars: Optional[List[str]] = None
) -> str:
    """
    Generate Cypher query from natural language using LLM.

    Args:
        user_query: User's natural language question
        scholar_name: Optional scholar name if mentioned in query
        retry_count: Current retry attempt number

    Returns:
        Generated Cypher query string
    """
    schema = _get_graph_schema()
    examples = _get_few_shot_examples()

    # Build system prompt
    system_prompt = f"""You are an expert Neo4j Cypher query generator.

{schema}

{examples}

🎯 Your Task:
Generate a Cypher query to answer the user's question.

📝 Output Requirements:
1. **IMPORTANT**: Output ONLY the Cypher query - NO reasoning, NO explanations, NO "Let me think", NO introductory text
2. Start your response immediately with a Cypher keyword (MATCH, CREATE, MERGE, WITH)
3. Query must be directly executable in Neo4j 5.x
4. Must follow all schema rules defined above
5. **ALWAYS use LIMIT 10** for single lookup queries (for stable, reproducible results)
6. Use meaningful aliases for returned columns

⚠️ Critical Rules:
- NEVER invent nodes, relationships, or properties not in the schema
- ALWAYS use toLower() for case-insensitive string matching
- ALWAYS include LIMIT clause with fixed value: LIMIT 10 (except for comparison queries)
- If query involves a specific scholar, use fuzzy name matching
- For author name queries (especially names with potential duplicates), ALWAYS include:
  * ORDER BY paper_count DESC, total_citations DESC
  * LIMIT 10 (to get consistent results every time)
- **DO NOT** include any text before the Cypher query
- **DO NOT** explain your thought process

❌ Wrong format:
"Let me think about this... First I need to MATCH..."
"Here's the query that will help: MATCH..."

✅ Correct format:
"MATCH (a:Author)-[:AUTHORED]->(p:Paper) WHERE..."

Now, generate the Cypher query for the user's question. Start immediately with a Cypher keyword.
"""

    # Enhance query with scholar context if provided
    enhanced_query = user_query
    if scholar_name:
        enhanced_query = f"About scholar {scholar_name}: {user_query}"

    # Add error context if retrying
    if retry_count > 0:
        enhanced_query += f"\n[Previous attempt failed. Please fix the error and regenerate.]"

    try:
        # Call LLM
        llm = get_cypher_llm()
        completion = llm.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": enhanced_query}
        ])

        cypher = completion.content.strip()

        # Clean up the output (remove markdown formatting if present)
        cypher = _clean_cypher_output(cypher)

        # 打印完整的 Cypher 语句
        print(f"\n{'='*60}")
        print(f"🔍 [Text2Cypher] 生成的 Cypher 语句 (尝试 {retry_count + 1}):")
        print(f"{'='*60}")
        print(f"{cypher}")
        print(f"{'='*60}\n")

        # 记录到日志文件
        log_cypher_generation(cypher, user_query, retry_count + 1)

        return cypher

    except Exception as e:
        print(f"[Text2Cypher] LLM generation error: {str(e)}")
        raise


def _clean_cypher_output(cypher: str) -> str:
    """
    Clean up Cypher output by removing markdown formatting, reasoning text, and extra text.

    FIXED: Enhanced to handle LLM models that output ````thinking`` tags before Cypher.

    Args:
        cypher: Raw output from LLM

    Returns:
        Cleaned Cypher query
    """
    import re

    if not cypher:
        return ""

    original = cypher
    cypher = cypher.strip()

    # === Step 0: Remove thinking/reasoning tags FIRST ===
    # Remove <thinking>...</thinking> tags (with closing tag)
    cypher = re.sub(r'<thinking>.*?</thinking>', '', cypher, flags=re.DOTALL | re.IGNORECASE)
    # Handle unclosed <thinking> tags (remove everything after opening tag)
    cypher = re.sub(r'<thinking>.*', '', cypher, flags=re.DOTALL | re.IGNORECASE)
    # Remove any remaining </thinking> closing tags
    cypher = re.sub(r'</thinking>', '', cypher, flags=re.IGNORECASE)

    # Remove ```thinking...``` blocks (with closing ```)
    cypher = re.sub(r'```thinking\s*\n.*?\n```', '', cypher, flags=re.DOTALL | re.IGNORECASE)
    # Handle unclosed ```thinking blocks (remove only up to the Cypher keyword)
    unclosed_thinking = re.search(r'```thinking\s*\n(.*?)(?=MATCH|CREATE|MERGE|WITH|RETURN|$)', cypher, flags=re.DOTALL | re.IGNORECASE)
    if unclosed_thinking and unclosed_thinking.group(1):
        # Remove only the thinking part, keep what follows (the Cypher query)
        cypher = cypher[unclosed_thinking.end():] if unclosed_thinking.end() < len(cypher) else cypher
        # Also remove the ```thinking marker itself if it remains
        cypher = re.sub(r'```thinking\s*\n?', '', cypher, flags=re.IGNORECASE)

    # Remove <reasoning>...</reasoning> tags
    cypher = re.sub(r'<reasoning>.*?</reasoning>', '', cypher, flags=re.DOTALL | re.IGNORECASE)

    # === Step 1: Handle markdown code blocks ===
    if "```" in cypher:
        parts = cypher.split("```")
        # Find the part that contains the actual Cypher code
        # Structure is usually: text ```[lang] code ``` text
        for i, part in enumerate(parts):
            part = part.strip()
            # Skip empty parts and language identifiers
            if not part or part.lower() in ("cypher", "sql", "python", "graphql"):
                continue
            # Check if this part contains Cypher keywords
            part_upper = part.upper()
            if any(keyword in part_upper for keyword in ["MATCH", "CREATE", "MERGE", "WITH", "RETURN"]):
                cypher = part
                break

    # === Step 2: Find the first Cypher keyword and extract from there ===
    # This removes any reasoning text before the actual query
    cypher_keywords = ["MATCH", "CREATE", "MERGE", "WITH", "RETURN"]

    # Find the earliest occurrence of any Cypher keyword
    lines = cypher.split('\n')
    start_line = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Check if line starts with a Cypher keyword
        for keyword in cypher_keywords:
            if stripped.upper().startswith(keyword):
                start_line = i
                break
        else:
            continue
        break

    # Extract only from the first Cypher keyword
    if start_line > 0:
        cypher = '\n'.join(lines[start_line:])

    # === Step 3: Remove common explanatory phrases ===
    remove_phrases = [
        "Here's the Cypher query:",
        "The Cypher query is:",
        "Query:",
        "Here is the query:",
        "The query is:",
        "Cypher query:",
    ]
    for phrase in remove_phrases:
        cypher = cypher.replace(phrase, "")

    # === Step 4: Remove any text after the query ends ===
    # Look for common patterns that indicate end of query
    end_patterns = [
        '\n\nExplanation:',
        '\n\nNote:',
        '\n\nThis query',
        '\n---',
    ]
    for pattern in end_patterns:
        if pattern in cypher:
            cypher = cypher.split(pattern)[0]

    cleaned = cypher.strip()
    
    # Validation: must start with a Cypher keyword
    if not cleaned or not any(kw in cleaned.upper() for kw in cypher_keywords):
        print(f"[CleanCypher] ⚠️ Cleaned output doesn't contain Cypher keywords")
        print(f"[CleanCypher] Original (first 200 chars): {original[:200]}")
        return ""

    return cleaned



def _format_query_results(results: List[Dict[str, Any]], max_display: int = 10) -> str:
    """
    Format query results into human-readable text.

    Args:
        results: List of result records from Neo4j
        max_display: Maximum number of results to display

    Returns:
        Formatted text output
    """
    if not results:
        return "❌ 未找到匹配的信息。请尝试：\n1. 检查学者姓名拼写\n2. 使用更通用的关键词\n3. 扩大搜索范围"

    total_count = len(results)
    display_count = min(total_count, max_display)

    output = f"✅ 查询成功！共找到 {total_count} 条记录：\n\n"

    for i, record in enumerate(results[:display_count], 1):
        output += f"{i}. "

        # Format each record
        items = []
        for key, value in record.items():
            if value is not None:
                # Truncate long strings
                if isinstance(value, str) and len(value) > 80:
                    value = value[:77] + "..."
                items.append(f"{key}: {value}")

        output += " | ".join(items)
        output += "\n"

    if total_count > max_display:
        output += f"\n... 还有 {total_count - max_display} 条记录未显示"

    return output


def _validate_cypher_syntax(cypher: str) -> tuple[bool, Optional[str]]:
    """
    Basic Cypher syntax validation before execution.

    Args:
        cypher: Cypher query string

    Returns:
        (is_valid, error_message)
    """
    if not cypher or not cypher.strip():
        return False, "Empty Cypher query"

    cypher = cypher.strip().upper()

    # Check for required keywords
    if not cypher.startswith(("MATCH", "MATCH", "CREATE", "MERGE", "WITH")):
        return False, "Cypher must start with MATCH, CREATE, MERGE, or WITH"

    # Check for LIMIT clause (prevent large result sets)
    if "LIMIT" not in cypher.upper():
        print("⚠️  Warning: Cypher query missing LIMIT clause")

    # Check for dangerous operations
    dangerous_keywords = ["DELETE", "DETACH", "DROP", "CREATE INDEX", "DROP INDEX"]
    for keyword in dangerous_keywords:
        if keyword in cypher.upper():
            return False, f"Dangerous operation detected: {keyword}"

    return True, None


@tool
def dynamic_graph_retrieval(
    query: str,
    scholar_name: str = None,
    max_retry: int = 3,
    max_results: int = 20,
    query_type: str = "single_lookup",
    referenced_scholars: Optional[List[str]] = None
) -> str:
    """
    Dynamic Graph Retrieval Tool - Automatically generates and executes Cypher queries with task-type awareness

    This is the CORE tool for dynamic graph queries. Unlike hardcoded tools,
    it uses LLM to understand natural language and generate appropriate Cypher queries.

    Args:
        query: Natural language question (e.g., "Yao Xie的Top5高被引论文是什么？")
        scholar_name: Optional - If the question is about a specific scholar, provide their name
        max_retry: Maximum retry attempts if Cypher execution fails (default: 3)
        max_results: Maximum number of results to return (default: 20)
        query_type: Query type for prompt optimization (single_lookup/comparison/aggregation/multi_hop/recommendation)
        referenced_scholars: List of scholar names mentioned (for comparison queries)

    Returns:
        Formatted query results in human-readable text

    Examples:
        >>> # Query about a specific scholar's papers
        >>> dynamic_graph_retrieval("Yao Xie的Top5高被引论文是什么？", "Yao Xie")

        >>> # Comparison query (multiple scholars)
        >>> dynamic_graph_retrieval(
        ...     "对比 Yao Xie、Kai Wang、Tuo Zhao 三位学者",
        ...     query_type="comparison",
        ...     referenced_scholars=["Yao Xie", "Kai Wang", "Tuo Zhao"]
        ... )

        >>> # Query about research field
        >>> dynamic_graph_retrieval("Machine Learning领域最活跃的10位学者是谁？")
    """
    print(f"\n{'='*60}")
    print(f"[Text2Cypher] 动态图检索工具已调用")
    print(f"[Text2Cypher] 用户问题: {query}")
    print(f"[Text2Cypher] 任务类型: {query_type}")
    if scholar_name:
        print(f"[Text2Cypher] 目标学者: {scholar_name}")
    if referenced_scholars:
        print(f"[Text2Cypher] 引用学者: {', '.join(referenced_scholars)}")
    print(f"{'='*60}\n")

    # Auto-extract scholar name if not provided
    if not scholar_name:
        scholar_name = _extract_scholar_name(query)
        if scholar_name:
            print(f"[Text2Cypher] 自动识别学者: {scholar_name}")

    # Retry loop for Cypher generation and execution
    for attempt in range(max_retry):
        try:
            # Step 1: Generate Cypher (with task-type awareness)
            print(f"[Text2Cypher] 第 {attempt + 1}/{max_retry} 次尝试生成Cypher...")
            cypher = _generate_cypher_from_query(
                query,
                scholar_name,
                attempt,
                query_type=query_type,
                referenced_scholars=referenced_scholars
            )

            # Step 2: Validate syntax
            is_valid, error_msg = _validate_cypher_syntax(cypher)
            if not is_valid:
                raise ValueError(f"Syntax validation failed: {error_msg}")

            # Step 3: Execute query
            print(f"[Text2Cypher] ⚡ 正在执行 Cypher 查询...")
            start_time = time.time()
            results = neo4j_connector.execute_query(cypher)
            execution_time = time.time() - start_time

            if not results:
                # 记录空结果
                log_cypher_execution(cypher, 0, execution_time)
                return "❌ 未找到相关信息。建议：\n" \
                       "1. 检查学者姓名拼写\n" \
                       "2. 尝试使用更通用的关键词\n" \
                       "3. 确认数据库中是否有该学者的数据"

            # Step 3.5: Completeness validation (for comparison queries)
            if query_type == "comparison" and referenced_scholars:
                is_complete, validation_msg = _validate_comparison_completeness(
                    results,
                    referenced_scholars
                )
                print(f"[Text2Cypher] {validation_msg}")

                if not is_complete:
                    # Log warning but continue (don't fail)
                    print(f"[Text2Cypher] ⚠️  警告：部分学者数据可能缺失")

            # Step 4: Format results
            print(f"[Text2Cypher] ✅ 查询成功！返回 {len(results)} 条记录 (耗时 {execution_time:.3f}秒)")
            print(f"{'='*60}\n")

            # 记录执行结果到日志
            log_cypher_execution(cypher, len(results), execution_time)

            # For comparison queries, use special formatting
            if query_type == "comparison":
                formatted_output = _format_comparison_results(results, referenced_scholars, max_results)
            else:
                formatted_output = _format_query_results(results, max_results)

            return formatted_output

        except Exception as e:
            error_msg = str(e)
            print(f"[Text2Cypher] ❌ 第 {attempt + 1} 次尝试失败: {error_msg}")

            # If not the last attempt, continue retry
            if attempt < max_retry - 1:
                print(f"[Text2Cypher] 准备重试...")
                # Modify query to include error context for next attempt
                query = f"{query}\n[Error in previous attempt: {error_msg} - Please fix the Cypher query]"
                continue
            else:
                # All retries exhausted
                return f"❌ 查询失败：{error_msg}\n\n" \
                       f"建议：\n" \
                       f"1. 简化问题或换种表述方式\n" \
                       f"2. 尝试使用其他工具（如 search_scholars_by_field）\n" \
                       f"3. 联系管理员检查数据库连接"


@tool
def multi_hop_query(
    query: str,
    scholar_name: str = None,
    max_hops: int = 3
) -> str:
    """
    Multi-hop Graph Query Tool - For complex queries requiring multiple relationship traversals

    Use this tool for questions like:
    - "Who are the co-authors of Yao Xie's collaborators?" (2-hop)
    - "Which research topics are connected to both scholar A and scholar B?" (3-hop)

    Args:
        query: Natural language question requiring multi-hop traversal
        scholar_name: Optional starting scholar name
        max_hops: Maximum number of relationship hops (default: 3, recommended)

    Returns:
        Query results with hop information

    Examples:
        >>> # 2-hop query: collaborators of collaborators
        >>> multi_hop_query("Yao Xie的合作者的合作者有哪些？", "Yao Xie", max_hops=2)

        >>> # 3-hop query: research topic connections
        >>> multi_hop_query("和Jing Liu有共同研究主题的学者有哪些？", "Jing Liu", max_hops=3)
    """
    print(f"\n[MultiHop] 多跳查询工具已调用")
    print(f"[MultiHop] 查询: {query}")
    print(f"[MultiHop] 最大跳数: {max_hops}")

    # Build multi-hop prompt
    multi_hop_prompt = f"""{query}

[Special Requirement: This is a MULTI-HOP query]
- You may need to traverse multiple relationships (up to {max_hops} hops)
- Use variable-length path patterns: (a)-[:AUTHORED*1..{max_hops}]->(b)
- Be careful with performance - always use LIMIT
- Example: MATCH (a:Author)-[*1..2]-(b:Author) WHERE toLower(a.display_name) CONTAINS toLower('X')
"""

    # Reuse dynamic_graph_retrieval with enhanced prompt
    return dynamic_graph_retrieval.invoke({
        "query": multi_hop_prompt,
        "scholar_name": scholar_name,
        "max_retry": 3
    })


def _validate_comparison_completeness(
    results: List[Dict[str, Any]],
    expected_scholars: List[str]
) -> Tuple[bool, str]:
    """
    Validate that comparison query results include all expected scholars.

    Args:
        results: Cypher query results
        expected_scholars: List of scholar names that should be in results

    Returns:
        Tuple of (is_complete, message)
    """
    if not results:
        return False, f"⚠️  完整性校验：查询返回空结果，期望 {len(expected_scholars)} 位学者"

    # Extract scholar names from results
    found_scholars = set()
    for record in results:
        # Try different possible field names
        for field in ['scholar_name', 'name', 'display_name', 'a.display_name']:
            if field in record:
                scholar_name = record[field]
                if isinstance(scholar_name, str):
                    found_scholars.add(scholar_name.strip())
                break

    expected_set = set(expected_scholars)
    missing = expected_set - found_scholars

    if missing:
        return False, f"⚠️  完整性校验：部分学者数据缺失。期望 {len(expected_set)} 位，实际找到 {len(found_scholars)} 位。缺失：{', '.join(missing)}"

    return True, f"✅ 完整性校验通过：找到所有 {len(expected_set)} 位学者的数据"


def _format_comparison_results(
    results: List[Dict[str, Any]],
    referenced_scholars: Optional[List[str]] = None,
    max_display: int = 20
) -> str:
    """
    Format comparison query results into a human-readable table.

    Args:
        results: Cypher query results
        referenced_scholars: Expected scholars (for validation message)
        max_display: Maximum results to display

    Returns:
        Formatted comparison table
    """
    if not results:
        return "❌ 未找到匹配的信息。请检查学者姓名拼写或尝试其他查询。"

    # Extract all unique keys from results
    all_keys = set()
    for record in results:
        all_keys.update(record.keys())

    # Filter out internal keys
    display_keys = [k for k in all_keys if not k.startswith('_')]

    # Build header
    output = "✅ **查询成功！学者对比分析**\n\n"

    # Check if we have comparison data
    if 'scholar_name' in results[0] or 'name' in results[0]:
        # Get scholar name field
        scholar_field = 'scholar_name' if 'scholar_name' in results[0] else 'name'

        # Group by scholar
        scholar_data = {}
        for record in results:
            scholar = record.get(scholar_field, 'Unknown')
            scholar_data[scholar] = record

        # Create markdown table
        output += "| 指标 | " + " | ".join(scholar_data.keys()) + " |\n"
        output += "|" + "---|" * (len(scholar_data) + 1) + "\n"

        # Add rows for each metric
        metrics = ['paper_count', 'total_citations', 'avg_fwci', 'research_fields']
        metric_labels = {
            'paper_count': '论文数',
            'total_citations': '总引用',
            'avg_fwci': '平均 FWCI',
            'research_fields': '研究领域'
        }

        for metric in metrics:
            if metric in metric_labels:
                output += f"| {metric_labels[metric]} |"
                for scholar in scholar_data.keys():
                    value = scholar_data[scholar].get(metric, 'N/A')
                    if isinstance(value, list):
                        value = ', '.join(str(v) for v in value[:3])
                    elif value is None:
                        value = 'N/A'
                    output += f" {value} |"
                output += "\n"

        output += "\n**详细数据**：\n\n"

    # Display individual records
    for i, record in enumerate(results[:max_display], 1):
        output += f"**{i}.** "
        items = []
        for key, value in record.items():
            if not key.startswith('_'):
                if isinstance(value, list):
                    value = ', '.join(str(v) for v in value[:3])
                elif value is None:
                    value = 'N/A'
                items.append(f"{key}: {value}")
        output += " | ".join(items)
        output += "\n"

    # Add completeness warning if needed
    if referenced_scholars:
        is_complete, msg = _validate_comparison_completeness(results, referenced_scholars)
        if not is_complete:
            output += f"\n⚠️  {msg}"

    return output


# ========================================
# New Entity-Aware Text2Cypher Interface
# ========================================

def generate_cypher_with_entities(
    query: str,
    entities: EntitySet,
    max_retry: int = 3,
) -> tuple:
    """
    新的 text2cypher 入口。接收路由层已解析的 entities，
    在 prompt 中作为 context 明确告诉 LLM 这些实体的 ID 已经解析好了。

    相比原版：
    - 不再做 NER（entity extraction）——路由层已做
    - 不再做重名消歧——路由层已做
    - Prompt 更短、更聚焦（只需生成 Cypher 结构）
    - 使用参数化查询（$author_id_0, $author_id_1 等）

    Args:
        query: 用户查询（自然语言）
        entities: 路由层解析的实体（EntitySet）
        max_retry: 最大重试次数

    Returns:
        (cypher: str, params: dict) 元组

    Raises:
        Exception: 所有重试失败后抛出异常
    """
    _logger.info(f"[text2cypher_with_entities] Query: {query[:100]}...")
    _logger.info(f"[text2cypher_with_entities] Authors: {len(entities.authors)}, "
                f"Topics: {entities.topics}, Time range: {entities.time_range}")

    # 构造 entity context
    entity_context = _build_entity_context(entities)

    # 构造简化的 prompt（Haiku 优化版）
    prompt = f"""你是 Neo4j Cypher 查询生成器。根据用户问题生成一条可执行的 Cypher。

## Graph Schema
{_get_graph_schema()}

## 已解析实体（直接使用这些 ID，不需要再匹配）
{entity_context}

## 少样本示例
{_get_few_shot_examples()}

## 用户问题
{query}

## 输出要求
- 直接输出 Cypher 查询语句
- 不要用 ```cypher ``` 代码块包裹
- 不要添加任何解释、注释或前后缀
- 第一个字符必须是 MATCH / WITH / CALL / RETURN 之一
- 如果涉及已解析作者，直接使用 $author_id_0, $author_id_1 等参数（已在上下文中绑定）
- 使用参数化查询，不要硬编码字符串
- 必须包含 LIMIT 子句（防止性能问题）
"""

    # 重试机制
    for attempt in range(max_retry):
        try:
            # 使用 Haiku（新接口）
            cypher = _call_text2cypher_llm(prompt, use_haiku=True)
            cypher = _clean_cypher_output(cypher)

            print(f"\n{'='*60}")
            print(f"🔍 [Text2Cypher+Entities] 生成的 Cypher (尝试 {attempt + 1}):")
            print(f"{'='*60}")
            print(f"{cypher}")
            print(f"{'='*60}\n")

            # 构造参数字典
            params = _build_params_from_entities(entities)

            return cypher, params

        except Exception as e:
            _logger.warning(f"[text2cypher_with_entities] Attempt {attempt+1} failed: {e}")
            if attempt == max_retry - 1:
                raise


def _build_entity_context(entities: EntitySet) -> str:
    """
    将 EntitySet 格式化为 Cypher prompt 中的实体上下文。

    Args:
        entities: 路由层解析的实体

    Returns:
        格式化的实体上下文字符串
    """
    lines = []

    # 已解析的作者（有 author_id 的）
    for i, author in enumerate(entities.authors):
        if author.author_id:
            lines.append(f"- $author_id_{i} = '{author.author_id}' (作者: {author.name})")

    # 时间范围
    if entities.time_range:
        lines.append(f"- $start_year = {entities.time_range.start_year}")
        lines.append(f"- $end_year = {entities.time_range.end_year}")

    # 研究主题关键词
    if entities.topics:
        lines.append(f"- 研究主题关键词: {', '.join(entities.topics)}")

    # 论文 ID
    for i, paper_id in enumerate(entities.paper_ids):
        lines.append(f"- $paper_id_{i} = '{paper_id}'")

    return "\n".join(lines) if lines else "（无已解析实体）"


def _build_params_from_entities(entities: EntitySet) -> dict:
    """
    从 entities 构造 Cypher 查询参数字典。

    Args:
        entities: 路由层解析的实体

    Returns:
        参数字典，如 {"author_id_0": "...", "author_id_1": "..."}
    """
    params = {}

    for i, author in enumerate(entities.authors):
        if author.author_id:
            params[f"author_id_{i}"] = author.author_id

    if entities.time_range:
        params["start_year"] = entities.time_range.start_year
        params["end_year"] = entities.time_range.end_year

    for i, paper_id in enumerate(entities.paper_ids):
        params[f"paper_id_{i}"] = paper_id

    return params


def _call_text2cypher_llm(prompt: str, use_haiku: bool = False) -> str:
    """
    调用 LLM 生成 Cypher（提取为独立函数供新接口复用）。

    Args:
        prompt: 完整的 prompt
        use_haiku: 是否使用 Haiku（新接口用 Haiku，旧接口用 MiniMax）

    Returns:
        LLM 生成的 Cypher（原始输出）
    """
    if use_haiku:
        # 新接口：使用 Haiku（通过 llm_factory）
        from graph.node_helpers.llm_factory import _get_text2cypher_llm
        llm = _get_text2cypher_llm()
    else:
        # 旧接口：继续使用 MiniMax
        llm = get_cypher_llm()

    completion = llm.invoke(prompt)
    return completion.content


# ========================================
# Legacy Test Function
# ========================================

# Test function
def test_text2cypher():
    """Test Text2Cypher module with sample queries"""
    print("\n" + "="*60)
    print("Text2Cypher Module Test")
    print("="*60 + "\n")

    test_queries = [
        ("Yao Xie的Top5高被引论文是什么？", "Yao Xie"),
        ("Machine Learning领域最活跃的10位学者", None),
        ("Jing Liu的主要合作者有哪些？", "Jing Liu"),
    ]

    for i, (query, scholar) in enumerate(test_queries, 1):
        print(f"\n【测试 {i}】")
        print(f"问题: {query}")

        try:
            result = dynamic_graph_retrieval.invoke({
                "query": query,
                "scholar_name": scholar,
                "max_retry": 2,
                "max_results": 5
            })
            print(f"\n结果:\n{result[:500]}...")
        except Exception as e:
            print(f"❌ 测试失败: {str(e)}")

        print("\n" + "-"*60)


if __name__ == "__main__":
    # Run tests if executed directly
    test_text2cypher()
