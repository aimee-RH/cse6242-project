#!/usr/bin/env python3
"""
Few-Shot Examples Validator for Text2Cypher

This script validates all few-shot Cypher examples used in the Text2Cypher module.
It performs static analysis to catch common issues before running on the database.

Validation Checks:
1. Syntax validation (Cypher keywords, structure)
2. Schema validation (only uses defined nodes/relationships)
3. toLower() symmetry check
4. LIMIT clause presence
5. Variable naming conflicts
6. Relationship existence

Author: Scholar Compass Team
Date: 2026-04-16
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Optional logger - will work if utils is available
logger = None  # Logger not required for this script


# Valid schema elements
VALID_NODES = ['Author', 'Paper', 'Subfield', 'Source']
VALID_RELATIONSHIPS = ['AUTHORED', 'IN_SUBFIELD', 'PUBLISHED_IN']
VALID_PROPERTIES = {
    'Author': ['id', 'display_name'],
    'Paper': ['id', 'title', 'publication_year', 'cited_by_count', 'fwci'],
    'Subfield': ['id', 'display_name'],
    'Source': ['id', 'display_name']
}


class CypherValidator:
    """Validates Cypher queries against schema and best practices"""

    def __init__(self, query: str, example_name: str):
        self.query = query.strip()
        self.example_name = example_name
        self.errors = []
        self.warnings = []
        self.info = []

    def validate(self) -> Tuple[bool, List[str], List[str], List[str]]:
        """Run all validation checks"""
        self._check_syntax()
        self._check_schema_compliance()
        self._check_to_lower_symmetry()
        self._check_limit_clause()
        self._check_variable_reuse()
        self._check_dangerous_operations()

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings, self.info

    def _check_syntax(self):
        """Check basic Cypher syntax"""
        if not self.query:
            self.errors.append("❌ Empty query")
            return

        # Check for required keywords
        cypher_keywords = ['MATCH', 'CREATE', 'MERGE', 'WITH', 'RETURN']
        if not any(kw in self.query.upper() for kw in cypher_keywords):
            self.errors.append("❌ Missing Cypher keyword (MATCH, RETURN, etc.)")

        # Check for balanced parentheses
        open_parens = self.query.count('(')
        close_parens = self.query.count(')')
        if open_parens != close_parens:
            self.errors.append(f"❌ Unbalanced parentheses: {open_parens} open, {close_parens} close")

        # Check for balanced brackets
        open_brackets = self.query.count('[')
        close_brackets = self.query.count(']')
        if open_brackets != close_brackets:
            self.errors.append(f"❌ Unbalanced brackets: {open_brackets} open, {close_brackets} close")

    def _check_schema_compliance(self):
        """Check that query only uses defined schema elements"""
        # Extract node labels
        node_pattern = r'\((\w+):(\w+)\)'
        nodes = re.findall(node_pattern, self.query)

        for var, label in nodes:
            if label not in VALID_NODES:
                self.errors.append(f"❌ Invalid node label: :{label}. Valid nodes: {VALID_NODES}")

        # Extract relationship types - more precise pattern
        # Match: -[:REL_TYPE]- or -[:REL_TYPE]-> or <-[:REL_TYPE]-
        rel_pattern = r'-\[?:([A-Z_]+)\]?-'
        relationships = re.findall(rel_pattern, self.query)

        for rel in relationships:
            if rel not in VALID_RELATIONSHIPS:
                self.errors.append(f"❌ Invalid relationship: :{rel}. Valid: {VALID_RELATIONSHIPS}")

        # Check property access
        prop_pattern = r'(\w+)\.(\w+)'
        props = re.findall(prop_pattern, self.query)

        for var_name, prop in props:
            # Skip common built-ins
            if var_name in ['node', 'count', 'sum', 'avg', 'max', 'min']:
                continue
            # This is a simplified check - real validation would need to track variable types
            pass

    def _check_to_lower_symmetry(self):
        """Check toLower() usage for common anti-patterns"""
        # Pattern: toLower(...) IN [...] with uppercase strings in list
        tolower_in_pattern = r"toLower\([^)]+\)\s+IN\s+\[([^\]]+)\]"
        matches = re.findall(tolower_in_pattern, self.query, re.IGNORECASE)

        for match in matches:
            # Check if list contains uppercase letters
            if re.search(r'[A-Z]', match):
                self.errors.append(f"❌ toLower() asymmetry detected: toLower(...) IN [{match}]. "
                                 f"Left side is lowercase, right side has uppercase. "
                                 f"Fix: Use ANY(...) with CONTAINS or lowercase all list items.")

        # Also check for toLower(... ) = 'UPPERCASE' pattern
        tolower_equals_pattern = r"toLower\([^)]+\)\s*=\s*['\"]([^'\"]*)['\"]"
        matches = re.findall(tolower_equals_pattern, self.query)

        for match in matches:
            if re.search(r'[A-Z]', match):
                self.warnings.append(f"⚠️  toLower() = '{match}' - right side has uppercase. "
                                    f"Consider: toLower(...) = toLower('{match}')")

    def _check_limit_clause(self):
        """Check for LIMIT clause"""
        # Skip if this is a comparison query (they explicitly don't use LIMIT)
        if 'COMPARISON' in self.example_name.upper():
            self.info.append("ℹ️  Comparison query - LIMIT check skipped")
            return

        if 'LIMIT' not in self.query.upper():
            self.warnings.append("⚠️  Missing LIMIT clause - may return large result sets")

    def _check_variable_reuse(self):
        """Check for potential variable reuse issues"""
        # Find all MATCH clauses
        match_pattern = r'MATCH\s+([^:]+?)(?:\s+(?:WHERE|WITH|RETURN|LIMIT|$))'
        matches = re.findall(match_pattern, self.query, re.IGNORECASE)

        # Extract variable names from first MATCH
        if len(matches) > 1:
            # Multiple MATCH clauses - check for variable reuse
            first_match_vars = set(re.findall(r'\((\w+)\)', matches[0]))
            second_match_vars = set(re.findall(r'\((\w+)\)', matches[1]))

            reused = first_match_vars & second_match_vars
            if reused:
                self.warnings.append(f"⚠️  Variables reused across MATCH clauses: {reused}. "
                                    f"This creates implicit equality constraints.")

    def _check_dangerous_operations(self):
        """Check for dangerous operations"""
        dangerous = ['DELETE', 'DETACH', 'DROP', 'CREATE INDEX', 'DROP INDEX']
        query_upper = self.query.upper()

        for op in dangerous:
            if op in query_upper:
                self.errors.append(f"❌ Dangerous operation: {op}")


def extract_cypher_from_markdown(markdown_text: str) -> List[str]:
    """Extract Cypher queries from markdown code blocks"""
    pattern = r'```cypher\s+(.*?)```'
    matches = re.findall(pattern, markdown_text, re.DOTALL)
    return [m.strip() for m in matches]


def test_comparison_examples():
    """Test comparison few-shot examples"""
    print("\n" + "="*60)
    print("Testing Comparison Few-Shot Examples")
    print("="*60)

    examples = """
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
```
"""

    queries = extract_cypher_from_markdown(examples)
    print(f"\nFound {len(queries)} comparison examples\n")

    all_valid = True
    for i, query in enumerate(queries, 1):
        validator = CypherValidator(query, f"Comparison Example {i}")
        is_valid, errors, warnings, info = validator.validate()

        print(f"\n--- Comparison Example {i} ---")
        if is_valid:
            print("✅ PASSED")
        else:
            print("❌ FAILED")
            all_valid = False

        for error in errors:
            print(error)
        for warning in warnings:
            print(warning)

    return all_valid


def test_multi_hop_examples():
    """Test multi-hop few-shot examples"""
    print("\n" + "="*60)
    print("Testing Multi-Hop Few-Shot Examples")
    print("="*60)

    examples = """
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
"""

    queries = extract_cypher_from_markdown(examples)
    print(f"\nFound {len(queries)} multi-hop examples\n")

    all_valid = True
    for i, query in enumerate(queries, 1):
        validator = CypherValidator(query, f"Multi-Hop Example {i}")
        is_valid, errors, warnings, info = validator.validate()

        print(f"\n--- Multi-Hop Example {i} ---")
        if is_valid:
            print("✅ PASSED")
        else:
            print("❌ FAILED")
            all_valid = False

        for error in errors:
            print(error)
        for warning in warnings:
            print(warning)

    return all_valid


def test_basic_examples():
    """Test basic few-shot examples"""
    print("\n" + "="*60)
    print("Testing Basic Few-Shot Examples")
    print("="*60)

    examples = """
Example 1: High-cited papers query
User Question: "What are Yao Xie's Top 3 most cited papers?"
Generated Cypher:
```cypher
MATCH (a:Author)-[:AUTHORED]->(p:Paper)
WHERE toLower(a.display_name) CONTAINS toLower('Yao Xie')
RETURN p.title as title, p.cited_by_count as citations
ORDER BY p.cited_by_count DESC
LIMIT 3
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
"""

    queries = extract_cypher_from_markdown(examples)
    print(f"\nFound {len(queries)} basic examples\n")

    all_valid = True
    for i, query in enumerate(queries, 1):
        validator = CypherValidator(query, f"Basic Example {i}")
        is_valid, errors, warnings, info = validator.validate()

        print(f"\n--- Basic Example {i} ---")
        if is_valid:
            print("✅ PASSED")
        else:
            print("❌ FAILED")
            all_valid = False

        for error in errors:
            print(error)
        for warning in warnings:
            print(warning)

    return all_valid


def main():
    """Run all validation tests"""
    print("\n" + "="*60)
    print("Few-Shot Examples Validator")
    print("Text2Cypher Static Analysis")
    print("="*60)

    results = {
        'Basic Examples': test_basic_examples(),
        'Comparison Examples': test_comparison_examples(),
        'Multi-Hopxamples': test_multi_hop_examples()
    }

    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    for category, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{category}: {status}")

    all_passed = all(results.values())
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED")
    else:
        print("❌ SOME TESTS FAILED - Please review errors above")
    print("="*60 + "\n")

    return all_passed


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
