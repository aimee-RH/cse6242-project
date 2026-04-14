# LangGraph Academic Advisor Agent

A LangGraph-based intelligent agent for academic advisor recommendation and research analysis, powered by Neo4j graph database and Qwen LLM.

## 🎯 Features

- **Scholar Search**: Find scholars by research field with publication and citation metrics
- **Author Analysis**: Get detailed scholar information including research fields and impact metrics
- **Collaboration Network**: Analyze collaboration networks between scholars
- **Trend Analysis**: Discover trending research topics in various fields
- **Advisor Recommendations**: Smart advisor recommendations based on research interests and impact metrics
- **Multi-turn Conversations**: Context-aware dialogue with tool calling capabilities

## 🏗️ Architecture

```
User Query
    ↓
Flask Backend (/api/chat)
    ↓
LangGraph StateGraph
    ├─→ Agent Node (LLM + Tool Binding)
    │       ↓
    │   Decision: Use Tools?
    │       ↓
    │   [Yes] → Tools Node → Neo4j Database
    │       ↓
    │   Tool Results → Agent Node (Generate Response)
    │       ↓
    │   [No] → End
    ↓
Final Response to User
```

## 📁 Project Structure

```
webpage/
├── app.py                          # Flask main application
├── app.js                          # Frontend JavaScript
├── index.html                      # Frontend interface
├── requirements.txt                # Python dependencies
├── test_agent.py                   # Test script
│
├── tools/                          # LangChain tools
│   ├── __init__.py
│   ├── neo4j_connector.py          # Neo4j connection manager
│   ├── scholar_search.py           # Scholar search tool
│   ├── author_analysis.py          # Author details tool
│   ├── collaboration_analyzer.py   # Collaboration network tool
│   ├── trend_analyzer.py           # Trend analysis tool
│   └── advisor_recommender.py      # Advisor recommendation tool
│
├── graph/                          # LangGraph components
│   ├── __init__.py
│   ├── state.py                    # Agent state definition
│   ├── nodes.py                    # Graph nodes (agent, tools)
│   ├── edges.py                    # Graph edges (conditional routing)
│   └── graph.py                    # StateGraph construction
│
└── prompts/                        # System prompts
    ├── __init__.py
    └── system_prompt.py            # Agent system prompt
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Set your Qwen API key (from Alibaba Cloud DashScope):

```bash
export OPENAI_API_KEY='your-qwen-api-key-here'
```

Or edit `graph/nodes.py` and set the `api_key` parameter directly.

### 3. Start Neo4j Database

```bash
cd backend/academic_graph_project
docker-compose up -d
```

Verify Neo4j is running:
```bash
curl http://localhost:7474
```

### 4. Test the Setup

```bash
python test_agent.py
```

Expected output:
```
✓ Neo4j connector imported
✓ Tools imported (5 tools available)
✓ AgentState imported
✓ Graph nodes imported
✓ Graph edges imported
✓ LangGraph app compiled successfully
✅ All critical tests passed!
```

### 5. Run the Application

```bash
python app.py
```

Open your browser and navigate to: http://localhost:5001

## 🔧 Available Tools

### 1. search_scholars_by_field
Search for scholars by research field.

**Parameters:**
- `research_field` (str): Research field name
- `limit` (int, optional): Number of results (default: 10)
- `min_papers` (int, optional): Minimum paper count (default: 5)

**Example:**
```
User: "Find scholars in machine learning"
Agent: Calls search_scholars_by_field(research_field="machine learning")
```

### 2. get_author_details
Get detailed information about a scholar.

**Parameters:**
- `author_id` (str): OpenAlex author ID

**Example:**
```
User: "Tell me about author https://openalex.org/A1234567890"
Agent: Calls get_author_details(author_id="https://openalex.org/A1234567890")
```

### 3. analyze_collaborations
Analyze a scholar's collaboration network.

**Parameters:**
- `author_id` (str): OpenAlex author ID
- `limit` (int, optional): Number of collaborators (default: 10)

**Example:**
```
User: "Who are the main collaborators of Dr. Zhang?"
Agent: Calls analyze_collaborations(author_id="...")
```

### 4. find_trending_topics
Discover popular research topics in a field.

**Parameters:**
- `field` (str): Research field name
- `year_threshold` (int, optional): Only papers after this year (default: 2020)

**Example:**
```
User: "What are trending topics in computer vision?"
Agent: Calls find_trending_topics(field="computer vision")
```

### 5. recommend_advisors
Recommend advisors based on research interests.

**Parameters:**
- `research_interest` (str): Research interest keywords
- `limit` (int, optional): Number of recommendations (default: 5)
- `min_fwci` (float, optional): Minimum FWCI score (default: 1.0)

**Example:**
```
User: "Recommend advisors for deep learning research"
Agent: Calls recommend_advisors(research_interest="deep learning")
```

## 💬 Example Conversations

### Scenario 1: Simple Search
```
User: "I'm looking for machine learning scholars"

Agent: "I'll help you find machine learning scholars.
       Let me search the database..."

[Uses tool: search_scholars_by_field]

Agent: "Found 10 scholars in machine learning:
       1. Dr. Zhang San - 45 papers, 1234 citations
       2. Dr. Li Si - 38 papers, 987 citations
       ..."
```

### Scenario 2: Multi-turn Analysis
```
User: "Recommend some AI advisors"

Agent: [Uses recommend_advisors]
       "Based on research impact and publications, I recommend:
       1. Prof. Wang - FWCI: 2.5, Papers: 52
       2. Prof. Chen - FWCI: 2.3, Papers: 48
       ..."

User: "Tell me more about Prof. Wang"

Agent: [Uses get_author_details]
       "Prof. Wang specializes in:
       - Machine Learning
       - Computer Vision
       - Natural Language Processing
       Total citations: 5,432
       Average FWCI: 2.5"
```

### Scenario 3: Trend Analysis
```
User: "What's hot in natural language processing?"

Agent: [Uses find_trending_topics]
       "Here are trending NLP topics (2020-2024):
       1. Large Language Models - 2,341 citations
       2. Transformer Architectures - 1,987 citations
       3. Multimodal Learning - 1,654 citations
       ..."
```

## 🔍 LangGraph Workflow

### State Management
The agent uses a `messages` array that accumulates the conversation history:

```python
state = {
    "messages": [
        SystemMessage("You are a helpful assistant..."),
        HumanMessage("Find ML scholars"),
        AIMessage(
            content="",
            tool_calls=[{
                "name": "search_scholars_by_field",
                "args": {"research_field": "machine learning"}
            }]
        ),
        ToolMessage("Search results: [...]"),
        AIMessage("Found 10 scholars...")
    ]
}
```

### Conditional Routing
The `should_continue` function determines workflow:

```python
def should_continue(state):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tools"  # Execute tools
    return "end"  # Finish
```

### Graph Execution
```
Entry → agent → (has tool calls?) → [Yes] → tools → agent → (has tool calls?) → ...
                    ↓
                   [No] → END
```

## 🛠️ Customization

### Adding New Tools

1. Create a new tool in `tools/`:

```python
# tools/my_custom_tool.py
from langchain_core.tools import tool
from tools.neo4j_connector import neo4j_connector

@tool
def my_custom_tool(param1: str, param2: int = 10) -> str:
    """Tool description that LLM can see"""
    query = "MATCH (n) RETURN n LIMIT $limit"
    results = neo4j_connector.execute_query(query, {"limit": param2})
    return str(results)
```

2. Export in `tools/__init__.py`:

```python
from tools.my_custom_tool import my_custom_tool

TOOLS = [
    ...,
    my_custom_tool
]
```

### Modifying System Prompt

Edit `prompts/system_prompt.py` to change agent behavior:

```python
SYSTEM_PROMPT = """You are a specialized assistant...
Available tools:
- tool1: description
- tool2: description

Guidelines:
- Be helpful and informative
- Always use tools for data queries
...
"""
```

### Changing Neo4j Connection

Edit `tools/neo4j_connector.py`:

```python
class Neo4jConnector:
    def __init__(self):
        self.uri = "bolt://your-neo4j-host:7687"
        self.user = "your-username"
        self.password = "your-password"
```

## 🐛 Troubleshooting

### Neo4j Connection Failed
```
Error: Couldn't connect to localhost:7688
```
**Solution**: Start Neo4j database
```bash
cd backend/academic_graph_project
docker-compose up -d
```

### API Key Not Set
```
Error: OPENAI_API_KEY not found
```
**Solution**: Set the environment variable
```bash
export OPENAI_API_KEY='your-qwen-api-key'
```

### Import Errors
```
ModuleNotFoundError: No module named 'langgraph'
```
**Solution**: Install dependencies
```bash
pip install -r requirements.txt
```

### Tool Execution Errors
```
Error: Invalid tool input
```
**Solution**: Check tool parameter names and types match the schema

## 📊 Performance Notes

- **First query**: ~2-5 seconds (LLM + Neo4j + Tool execution)
- **Subsequent queries**: ~1-3 seconds (conversation context maintained)
- **Neo4j queries**: Optimized with indexes on `id` and `display_name` fields
- **LLM calls**: Using Qwen Plus (fast, cost-effective)

## 📚 References

- [LangGraph Documentation](https://python.langchain.com/docs/langgraph)
- [LangChain Tools](https://python.langchain.com/docs/modules/tools)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/)
- [Qwen API Documentation](https://help.aliyun.com/zh/model-studio/getting-started/models)

## 📝 License

This project is part of CSE 6242 course work.

## 👥 Authors

- Original Implementation: [Your Names]
- LangGraph Refactor: Claude Code + Human Collaboration

---

**Last Updated**: April 2025
**Version**: 1.0.0
