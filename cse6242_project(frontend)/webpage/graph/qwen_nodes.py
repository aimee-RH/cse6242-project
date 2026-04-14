from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from graph.state import AgentState
from tools import TOOLS
import os

# Initialize LLM (Qwen Plus)
# Get API key from environment variable
api_key = os.environ.get("OPENAI_API_KEY", "")

if not api_key:
    raise ValueError(
        "❌ API密钥未设置！\n"
        "请先设置你的Qwen API密钥：\n"
        "  export OPENAI_API_KEY='sk-your-api-key-here'\n"
        "或者在阿里云DashScope获取: https://dashscope.aliyuncs.com/"
    )

llm = ChatOpenAI(
    model="qwen-plus",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
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
