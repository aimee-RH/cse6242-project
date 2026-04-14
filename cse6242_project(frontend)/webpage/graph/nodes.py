from langchain_openai import ChatOpenAI
from langgraph.prebuilt import ToolNode
from graph.state import AgentState
from tools import TOOLS
import os

# Initialize LLM (MiniMax - using Anthropic SDK)
# Get API key from environment variable
api_key = os.environ.get("MINIMAX_API_KEY", "")

if not api_key:
    raise ValueError(
        "❌ MiniMax API密钥未设置！\n"
        "请先设置你的MiniMax API密钥：\n"
        "  export MINIMAX_API_KEY='your-minimax-api-key-here'\n"
        "或者在MiniMax官网获取: https://platform.minimaxi.com/\n"
        "\n"
        "如果想使用 Claude API，请运行：\n"
        "  ./switch_api.sh claude\n"
        "  export ANTHROPIC_API_KEY='sk-ant-your-key'\n"
        "\n"
        "如果想使用 Qwen API，请运行：\n"
        "  ./switch_api.sh qwen\n"
        "  export OPENAI_API_KEY='sk-qwen-your-key'"
    )

# MiniMax 使用 OpenAI 兼容的 API 端点
# 根据用户要求使用 https://api.minimaxi.com/v1
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="MiniMax-M2.7",  # MiniMax 官方模型名称
    temperature=0,
    api_key=api_key,
    base_url="https://api.minimaxi.com/v1",  # MiniMax OpenAI 兼容端点
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
