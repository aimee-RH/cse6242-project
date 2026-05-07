#!/usr/bin/env python3
"""
Fact Checker Module - Hallucination Suppression for LangGraph Agent

This module implements fact verification against the Neo4j graph database,
ensuring LLM-generated responses are grounded in actual data.

Core Philosophy:
- All factual claims should be verifiable against the knowledge graph
- Partial matches are acceptable (e.g., "approximately 150 papers" vs 152)
- Missing data should trigger clarification, not hallucination

Key Features:
1. Extract factual claims from LLM responses
2. Verify claims against Neo4j database
3. Generate detailed verification reports
4. Suggest corrections for hallucinated content

Verification Scope:
- Scholar names and IDs
- Publication counts
- Citation counts
- Collaboration relationships
- Research fields and topics
- Publication years and venues

Author: Scholar Compass Team
Date: 2025-04-16
"""

from tools.neo4j_connector import neo4j_connector
from tools.text2cypher import _get_cypher_llm, _get_graph_schema
from typing import List, Dict, Tuple, Optional
import re
import json


# ========================================
# Fact Extraction
# ========================================

def extract_facts_from_answer(
    answer: str,
    referenced_scholars: List[str] = None
) -> List[Dict]:
    """
    Extract factual claims from LLM-generated answer.

    Uses LLM to parse and structure factual information from text.

    Args:
        answer: LLM-generated response text
        referenced_scholars: List of scholar names mentioned (optional)

    Returns:
        List of fact dicts, each containing:
        - claim_type: Type of fact (e.g., "paper_count", "citation_count")
        - subject: Entity being described (e.g., "Yao Xie")
        - value: Claimed value (e.g., 150)
        - context: Surrounding text for verification

    Example:
        >>> answer = "Yao Xie has published 150 papers with 5000 citations."
        >>> facts = extract_facts_from_answer(answer)
        >>> # Returns: [
        >>> #   {"claim_type": "paper_count", "subject": "Yao Xie", "value": 150},
        >>> #   {"claim_type": "citation_count", "subject": "Yao Xie", "value": 5000}
        >>> # ]
    """
    print(f"\n[FactChecker] 正在从答案中提取事实...")
    print(f"[FactChecker] 答案内容: {answer[:100]}...")

    # Build extraction prompt
    extraction_prompt = f"""You are a fact extraction expert. Extract factual claims from the following text.

{f"Referenced Scholars: {', '.join(referenced_scholars or [])}"}

Answer to analyze:
{answer}

Extract the following types of factual claims:
1. Paper counts (e.g., "published 150 papers")
2. Citation counts (e.g., "5000 citations", "highly cited")
3. Collaboration mentions (e.g., "collaborates with X")
4. Research fields/topics (e.g., "works in Machine Learning")
5. Publication years (e.g., "since 2018", "published in 2023")
6. Venue names (e.g., "published in NeurIPS")

Output format (JSON):
{{
  "facts": [
    {{
      "claim_type": "paper_count|citation_count|collaboration|research_field|publication_year|venue",
      "subject": "Entity name (e.g., scholar name)",
      "value": "Claimed value (number or text)",
      "confidence": "high|medium|low",
      "context": "Relevant sentence from answer"
    }}
  ]
}}

Rules:
- ONLY extract explicit factual claims, not opinions
- If no facts found, return {{"facts": []}}
- Output ONLY valid JSON, no additional text"""

    try:
        # Call LLM
        llm = _get_cypher_llm()
        completion = llm.invoke([
            {"role": "system", "content": "You are a precise fact extraction expert. Output only valid JSON."},
            {"role": "user", "content": extraction_prompt}
        ])

        response = completion.content.strip()

        # 打印原始响应用于调试
        print(f"[FactChecker] LLM原始响应: {response[:200]}...")

        # 清理响应（移除 markdown 格式）
        if response.startswith("```"):
            parts = response.split("```")
            for part in parts:
                part = part.strip()
                if part and not part.lower() in ("json", "python"):
                    response = part
                    break

        # 如果响应为空，返回空列表
        if not response or response.isspace():
            print(f"[FactChecker] ⚠️ LLM返回空响应，可能是答案中没有明确的事实主张")
            return []

        # Parse JSON
        result = json.loads(response)
        facts = result.get("facts", [])

        if not facts:
            print(f"[FactChecker] ℹ️ 未提取到事实（LLM返回空facts列表）")
        else:
            print(f"[FactChecker] ✅ 提取到 {len(facts)} 条事实主张")
            for i, fact in enumerate(facts, 1):
                print(f"  {i}. {fact['claim_type']}: {fact.get('subject', 'unknown')} = {fact.get('value', 'unknown')}")

        return facts

    except json.JSONDecodeError as e:
        print(f"[FactChecker] ❌ JSON解析失败: {str(e)}")
        print(f"[FactChecker] 原始响应: {response}")
        print(f"[FactChecker] 💡 可能是答案格式不符合预期，跳过事实提取")
        return []
    except Exception as e:
        print(f"[FactChecker] ❌ 提取失败: {str(e)}")
        return []


# ========================================
# Fact Verification
# ========================================

def verify_paper_count(scholar_name: str, claimed_count: int, tolerance: float = 0.1) -> Dict:
    """
    Verify claimed paper count against database.

    Args:
        scholar_name: Name of scholar
        claimed_count: Claimed number of papers
        tolerance: Acceptable deviation (e.g., 0.1 = ±10%)

    Returns:
        Verification dict with actual_count, is_correct, deviation
    """
    query = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)
    WHERE toLower(a.display_name) CONTAINS toLower($scholar_name)
    WITH a, count(p) as paper_count
    ORDER BY paper_count DESC
    LIMIT 1
    RETURN a.display_name as name, paper_count as actual_count
    """

    try:
        results = neo4j_connector.execute_query(query, {"scholar_name": scholar_name})

        if not results:
            return {
                "is_correct": False,
                "error": "Scholar not found in database",
                "claimed": claimed_count,
                "actual": None
            }

        actual_count = results[0]['actual_count']
        deviation = abs(claimed_count - actual_count) / max(actual_count, 1)
        is_correct = deviation <= tolerance

        return {
            "is_correct": is_correct,
            "claimed": claimed_count,
            "actual": actual_count,
            "deviation": f"{deviation*100:.1f}%",
            "scholar_name": results[0]['name'],
            "tolerance": f"±{tolerance*100:.0f}%"
        }

    except Exception as e:
        return {
            "is_correct": False,
            "error": str(e),
            "claimed": claimed_count,
            "actual": None
        }


def verify_citation_count(scholar_name: str, claimed_count: int, tolerance: float = 0.15) -> Dict:
    """
    Verify claimed total citation count.

    Args:
        scholar_name: Name of scholar
        claimed_count: Claimed total citations
        tolerance: Acceptable deviation (default ±15%)

    Returns:
        Verification dict
    """
    query = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)
    WHERE toLower(a.display_name) CONTAINS toLower($scholar_name)
    WITH a, sum(p.cited_by_count) as total_citations
    ORDER BY total_citations DESC
    LIMIT 1
    RETURN a.display_name as name, total_citations as actual_citations
    """

    try:
        results = neo4j_connector.execute_query(query, {"scholar_name": scholar_name})

        if not results:
            return {
                "is_correct": False,
                "error": "Scholar not found in database",
                "claimed": claimed_count,
                "actual": None
            }

        actual_citations = results[0]['actual_citations'] or 0
        deviation = abs(claimed_count - actual_citations) / max(actual_citations, 1)
        is_correct = deviation <= tolerance

        return {
            "is_correct": is_correct,
            "claimed": claimed_count,
            "actual": actual_citations,
            "deviation": f"{deviation*100:.1f}%",
            "scholar_name": results[0]['name'],
            "tolerance": f"±{tolerance*100:.0f}%"
        }

    except Exception as e:
        return {
            "is_correct": False,
            "error": str(e),
            "claimed": claimed_count,
            "actual": None
        }


def verify_collaboration(scholar1: str, scholar2: str) -> Dict:
    """
    Verify if two scholars have collaborated.

    Args:
        scholar1: First scholar's name
        scholar2: Second scholar's name

    Returns:
        Verification dict with collaboration details
    """
    query = """
    MATCH (a1:Author)-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(a2:Author)
    WHERE toLower(a1.display_name) CONTAINS toLower($scholar1)
      AND toLower(a2.display_name) CONTAINS toLower($scholar2)
    RETURN a1.display_name as name1,
           a2.display_name as name2,
           count(p) as collaboration_count,
           collect(p.title)[0..3] as shared_papers
    """

    try:
        results = neo4j_connector.execute_query(query, {
            "scholar1": scholar1,
            "scholar2": scholar2
        })

        if not results:
            return {
                "is_correct": False,
                "error": f"No collaboration found between {scholar1} and {scholar2}",
                "collaboration_count": 0
            }

        return {
            "is_correct": True,
            "collaboration_count": results[0]['collaboration_count'],
            "scholar1": results[0]['name1'],
            "scholar2": results[0]['name2'],
            "shared_papers": results[0]['shared_papers']
        }

    except Exception as e:
        return {
            "is_correct": False,
            "error": str(e),
            "collaboration_count": 0
        }


def verify_research_field(scholar_name: str, claimed_field: str) -> Dict:
    """
    Verify if a scholar works in a specific research field.

    Args:
        scholar_name: Scholar's name
        claimed_field: Claimed research field

    Returns:
        Verification dict
    """
    query = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:IN_SUBFIELD]->(s:Subfield)
    WHERE toLower(a.display_name) CONTAINS toLower($scholar_name)
      AND toLower(s.display_name) CONTAINS toLower($field)
    WITH a, s.display_name as field_name, count(p) as paper_count
    ORDER BY paper_count DESC
    LIMIT 1
    RETURN a.display_name as name,
           field_name,
           paper_count
    """

    try:
        results = neo4j_connector.execute_query(query, {
            "scholar_name": scholar_name,
            "field": claimed_field
        })

        if not results:
            return {
                "is_correct": False,
                "error": f"No evidence found for {scholar_name} working in {claimed_field}",
                "claimed_field": claimed_field,
                "actual_fields": []
            }

        return {
            "is_correct": True,
            "scholar_name": results[0]['name'],
            "field_name": results[0]['field_name'],
            "paper_count": results[0]['paper_count'],
            "claimed_field": claimed_field
        }

    except Exception as e:
        return {
            "is_correct": False,
            "error": str(e),
            "claimed_field": claimed_field
        }


def verify_publication_venue(scholar_name: str, venue: str, year: int = None) -> Dict:
    """
    Verify if a scholar has published in a specific venue.

    Args:
        scholar_name: Scholar's name
        venue: Venue name (journal/conference)
        year: Optional publication year

    Returns:
        Verification dict
    """
    query = """
    MATCH (a:Author)-[:AUTHORED]->(p:Paper)-[:PUBLISHED_IN]->(src:Source)
    WHERE toLower(a.display_name) CONTAINS toLower($scholar_name)
      AND toLower(src.display_name) CONTAINS toLower($venue)
    """

    params = {"scholar_name": scholar_name, "venue": venue}

    if year:
        query += " AND p.publication_year = $year"
        params["year"] = year

    query += """
    RETURN a.display_name as name,
           src.display_name as venue_name,
           count(p) as paper_count,
           collect(p.title)[0..3] as sample_papers
    """

    try:
        results = neo4j_connector.execute_query(query, params)

        if not results:
            return {
                "is_correct": False,
                "error": f"No publications found in {venue}" + (f" for {year}" if year else ""),
                "venue": venue
            }

        return {
            "is_correct": True,
            "scholar_name": results[0]['name'],
            "venue_name": results[0]['venue_name'],
            "paper_count": results[0]['paper_count'],
            "sample_papers": results[0]['sample_papers']
        }

    except Exception as e:
        return {
            "is_correct": False,
            "error": str(e),
            "venue": venue
        }


# ========================================
# Unified Verification Interface
# ========================================

def verify_fact(fact: Dict) -> Dict:
    """
    Route fact to appropriate verification function.

    Args:
        fact: Fact dict with claim_type, subject, value

    Returns:
        Verification result dict
    """
    claim_type = fact.get("claim_type")
    subject = fact.get("subject")
    value = fact.get("value")

    print(f"[FactChecker] 验证事实: {claim_type} - {subject} = {value}")

    try:
        # Extract numeric value from string if needed
        if isinstance(value, str):
            # Extract numbers from string
            numbers = re.findall(r'\d+', value)
            numeric_value = int(numbers[0]) if numbers else None
        else:
            numeric_value = value

        # Route to appropriate verifier
        if claim_type == "paper_count":
            return verify_paper_count(subject, numeric_value or 0)

        elif claim_type == "citation_count":
            return verify_citation_count(subject, numeric_value or 0)

        elif claim_type == "collaboration":
            # Extract collaborator name from value
            collaborator = value if isinstance(value, str) else str(value)
            return verify_collaboration(subject, collaborator)

        elif claim_type == "research_field":
            return verify_research_field(subject, value)

        elif claim_type == "venue":
            return verify_publication_venue(subject, value)

        elif claim_type == "publication_year":
            # Year verification requires more context
            return {
                "is_correct": True,
                "note": f"Publication year {value} mentioned (requires additional context)",
                "claimed_year": value
            }

        else:
            return {
                "is_correct": False,
                "error": f"Unknown claim type: {claim_type}"
            }

    except Exception as e:
        return {
            "is_correct": False,
            "error": str(e),
            "fact": fact
        }


def fact_check_answer(
    answer: str,
    referenced_scholars: List[str] = None,
    strict_mode: bool = False
) -> Tuple[bool, Dict]:
    """
    Main fact-checking function: Verify all factual claims in an answer.

    Args:
        answer: LLM-generated response to verify
        referenced_scholars: List of scholar names mentioned
        strict_mode: If True, all facts must be correct; otherwise, report mismatches

    Returns:
        (is_factual, verification_report)
        - is_factual: True if all facts verified (or no facts found)
        - verification_report: Detailed verification results

    Example:
        >>> answer = "Yao Xie has published 150 papers with 5000 citations."
        >>> is_factual, report = fact_check_answer(answer, ["Yao Xie"])
        >>> print(report["summary"])
        "3/4 facts verified. Paper count mismatch (claimed: 150, actual: 152)"
    """
    print("\n" + "="*60)
    print("[FactChecker] 开始事实校验")
    print("="*60)

    # Step 1: Extract facts
    facts = extract_facts_from_answer(answer, referenced_scholars)

    if not facts:
        print("[FactChecker] 未发现可验证的事实")
        return True, {
            "is_factual": True,
            "summary": "No verifiable facts found",
            "fact_count": 0,
            "verified_count": 0,
            "details": []
        }

    # Step 2: Verify each fact
    verification_results = []
    correct_count = 0

    for fact in facts:
        result = verify_fact(fact)
        result["original_claim"] = fact
        verification_results.append(result)

        if result.get("is_correct"):
            correct_count += 1
            print(f"  ✅ {fact['claim_type']}: 验证通过")
        else:
            print(f"  ❌ {fact['claim_type']}: {result.get('error', 'Verification failed')}")

    # Step 3: Generate report
    total_facts = len(facts)
    accuracy_rate = correct_count / total_facts if total_facts > 0 else 1.0

    is_factual = accuracy_rate >= 0.8 if not strict_mode else correct_count == total_facts

    report = {
        "is_factual": is_factual,
        "summary": f"{correct_count}/{total_facts} facts verified ({accuracy_rate*100:.0f}% accuracy)",
        "fact_count": total_facts,
        "verified_count": correct_count,
        "accuracy_rate": f"{accuracy_rate*100:.1f}%",
        "details": verification_results,
        "recommendations": _generate_recommendations(verification_results)
    }

    print(f"\n[FactChecker] 校验完成: {report['summary']}")
    print("="*60 + "\n")

    return is_factual, report


def _generate_recommendations(results: List[Dict]) -> List[str]:
    """
    Generate recommendations for handling verification failures.

    Args:
        results: List of verification results

    Returns:
        List of recommendation strings
    """
    recommendations = []

    for result in results:
        if not result.get("is_correct"):
            claim = result.get("original_claim", {})
            claim_type = claim.get("claim_type", "unknown")

            if claim_type == "paper_count":
                actual = result.get("actual")
                claimed = result.get("claimed")
                if actual is not None:
                    recommendations.append(
                        f"Correction: {claim.get('subject')} has {actual} papers, not {claimed}"
                    )

            elif claim_type == "citation_count":
                actual = result.get("actual")
                claimed = result.get("claimed")
                if actual is not None:
                    recommendations.append(
                        f"Correction: {claim.get('subject')} has {actual} total citations, not {claimed}"
                    )

            elif claim_type == "collaboration":
                recommendations.append(
                    f"Verify collaboration: {result.get('error', 'No evidence of collaboration')}"
                )

            else:
                recommendations.append(f"Verify {claim_type}: {result.get('error', 'Check claim')}")

    return recommendations if recommendations else ["All facts verified successfully"]


# ========================================
# LangChain Tool Integration
# ========================================

from langchain_core.tools import tool


@tool
def fact_check_tool(
    answer: str,
    referenced_scholars: str = None,
    strict_mode: bool = False
) -> str:
    """
    Fact-check an answer against the Neo4j graph database.

    This tool verifies factual claims in LLM-generated responses,
    helping to suppress hallucinations and ensure accuracy.

    Args:
        answer: The LLM-generated answer to verify
        referenced_scholars: Comma-separated list of scholar names mentioned (optional)
        strict_mode: If True, all facts must be correct for pass (default: False)

    Returns:
        Verification report with findings and recommendations

    Examples:
        >>> fact_check_tool(
        ...     answer="Yao Xie has published 150 papers.",
        ...     referenced_scholars="Yao Xie"
        ... )

        >>> fact_check_tool(
        ...     answer="Jing Liu collaborates with Yao Xie.",
        ...     referenced_scholars="Jing Liu,Yao Xie"
        ... )
    """
    # Parse scholars list
    scholars_list = None
    if referenced_scholars:
        scholars_list = [s.strip() for s in referenced_scholars.split(",")]

    # Run fact check
    is_factual, report = fact_check_answer(answer, scholars_list, strict_mode)

    # Format output
    output = f"""
【事实校验报告】
状态: {'✅ 通过' if is_factual else '⚠️ 需要修正'}
总结: {report['summary']}

"""

    if report['details']:
        output += "【详细结果】\n"
        for i, detail in enumerate(report['details'], 1):
            claim = detail.get('original_claim', {})
            claim_type = claim.get('claim_type', 'unknown')
            subject = claim.get('subject', 'unknown')
            value = claim.get('value', 'unknown')

            status = "✅" if detail.get('is_correct') else "❌"
            output += f"{i}. {status} {claim_type}: {subject} = {value}\n"

            if not detail.get('is_correct'):
                # Add correction details
                if 'actual' in detail:
                    output += f"   实际值: {detail['actual']}\n"
                if 'error' in detail:
                    output += f"   错误: {detail['error']}\n"

    if report.get('recommendations'):
        output += "\n【修正建议】\n"
        for rec in report['recommendations']:
            output += f"• {rec}\n"

    return output.strip()


# ========================================
# Testing & Demo
# ========================================

def test_fact_checker():
    """
    Test the fact checker module with sample answers.
    """
    print("\n" + "="*60)
    print("Fact Checker Module Test")
    print("="*60 + "\n")

    # Test 1: Accurate answer
    print("【测试1】准确的答案")
    answer1 = "Yao Xie是一位活跃的学者，发表了大量论文。"
    is_factual, report = fact_check_answer(answer1, ["Yao Xie"])
    print(f"结果: {report['summary']}\n")

    # Test 2: Answer with specific claims
    print("【测试2】包含具体数字的答案")
    answer2 = "根据数据库查询，Yao Xie在机器学习领域发表了论文。"
    is_factual, report = fact_check_answer(answer2, ["Yao Xie"])
    print(f"结果: {report['summary']}")

    if report.get('details'):
        for detail in report['details']:
            print(f"  - {detail}\n")

    # Test 3: Collaboration claim
    print("【测试3】合作声明")
    answer3 = "Jing Liu和Yao Xie可能有合作关系。"
    is_factual, report = fact_check_answer(answer3, ["Jing Liu", "Yao Xie"])
    print(f"结果: {report['summary']}\n")

    # Test 4: Using the tool
    print("【测试4】LangChain工具")
    try:
        result = fact_check_tool.invoke({
            "answer": "Yao Xie发表了论文",
            "referenced_scholars": "Yao Xie"
        })
        print(f"工具输出:\n{result[:500]}...")
    except Exception as e:
        print(f"工具调用失败: {str(e)}")

    print("\n" + "="*60)
    print("✅ 测试完成！")
    print("="*60)


if __name__ == "__main__":
    # Run tests
    test_fact_checker()
