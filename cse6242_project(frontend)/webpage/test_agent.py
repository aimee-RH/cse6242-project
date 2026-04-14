#!/usr/bin/env python3
"""
Test script for LangGraph Agent
Tests basic functionality without starting the Flask server
"""

import os
import sys

# Set API key for testing (empty by default, user should set this)
os.environ.setdefault("OPENAI_API_KEY", "")

def test_imports():
    """Test that all modules can be imported"""
    print("Testing imports...")

    try:
        from tools.neo4j_connector import neo4j_connector
        print("✓ Neo4j connector imported")
    except Exception as e:
        print(f"✗ Neo4j connector failed: {e}")
        return False

    try:
        from tools import TOOLS
        print(f"✓ Tools imported ({len(TOOLS)} tools available)")
        for tool in TOOLS:
            print(f"  - {tool.name}")
    except Exception as e:
        print(f"✗ Tools failed: {e}")
        return False

    try:
        from graph.state import AgentState
        print("✓ AgentState imported")
    except Exception as e:
        print(f"✗ AgentState failed: {e}")
        return False

    try:
        from graph.nodes import call_model, tool_node, llm
        print("✓ Graph nodes imported")
    except Exception as e:
        print(f"✗ Graph nodes failed: {e}")
        return False

    try:
        from graph.edges import should_continue
        print("✓ Graph edges imported")
    except Exception as e:
        print(f"✗ Graph edges failed: {e}")
        return False

    try:
        from graph.graph import graph_app
        print("✓ LangGraph app compiled successfully")
    except Exception as e:
        print(f"✗ Graph compilation failed: {e}")
        return False

    return True

def test_neo4j_connection():
    """Test Neo4j connection (optional)"""
    print("\nTesting Neo4j connection...")

    try:
        from tools.neo4j_connector import neo4j_connector

        # Try a simple query
        query = "MATCH (n) RETURN count(n) as total_nodes LIMIT 1"
        results = neo4j_connector.execute_query(query)

        if results:
            print(f"✓ Neo4j connection successful")
            print(f"  Total nodes in database: {results[0]['total_nodes']}")
            return True
        else:
            print("⚠ Neo4j connected but no results returned")
            return False

    except Exception as e:
        print(f"⚠ Neo4j connection test skipped: {e}")
        print("  (Make sure Neo4j is running on bolt://localhost:7688)")
        return False

def test_tool_schemas():
    """Test that tool schemas are properly defined"""
    print("\nTesting tool schemas...")

    try:
        from tools import TOOLS

        for tool in TOOLS:
            schema = tool.args_schema
            print(f"✓ {tool.name}: {schema.__name__ if hasattr(schema, '__name__') else 'No schema'}")

        return True
    except Exception as e:
        print(f"✗ Tool schema test failed: {e}")
        return False

def main():
    print("=" * 60)
    print("LangGraph Agent Test Suite")
    print("=" * 60)
    print()

    all_passed = True

    # Test 1: Imports
    if not test_imports():
        all_passed = False
        print("\n❌ Import tests failed")
        sys.exit(1)

    # Test 2: Neo4j connection (optional)
    test_neo4j_connection()

    # Test 3: Tool schemas
    if not test_tool_schemas():
        all_passed = False

    print()
    print("=" * 60)
    if all_passed:
        print("✅ All critical tests passed!")
        print()
        print("Next steps:")
        print("1. Set your Qwen API key: export OPENAI_API_KEY='your-key'")
        print("2. Start Neo4j: cd backend/academic_graph_project && docker-compose up -d")
        print("3. Run the app: python app.py")
        print("4. Open browser: http://localhost:5001")
    else:
        print("❌ Some tests failed")
        sys.exit(1)
    print("=" * 60)

if __name__ == "__main__":
    main()
