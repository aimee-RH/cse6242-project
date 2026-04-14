from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import ToolNode
from graph.state import AgentState
from tools import TOOLS
import os

# Initialize LLM (Claude)
# Get API key from environment variable
api_key = os.environ.get("ANTHROPIC_API_KEY", "")

if not api_key:
    raise ValueError(
        "❌ Claude API密钥未设置！\n"
        "请先设置你的Anthropic API密钥：\n"
        "  export ANTHROPIC_API_KEY='sk-ant-your-api-key-here'\n"
        "或者在Anthropic官网获取: https://console.anthropic.com/"
    )

llm = ChatAnthropic(
    model="claude-3-5-sonnet-20241022",  # 或 claude-3-opus-20240229
    temperature=0,
    api_key=api_key
)

# Bind tools to LLM
llm_with_tools = llm.bind_tools(TOOLS)

# Create tool node (automatically handles tool execution)
tool_node = ToolNode(TOOLS)

def call_model(state: AgentState) -> AgentState:
    """Node function that calls LLM"""
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}
