from typing import Literal
from langchain_core.messages import AIMessage, ToolMessage
from graph.state import AgentState

def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """决定是否继续执行工具

    路由函数：
    - 如果 LLM 返回工具调用 → 转到 tools 节点
    - 如果已经调用了多次工具 → 结束
    - 否则 → 结束
    """
    messages = state["messages"]
    last_message = messages[-1]

    # 统计已经调用的工具次数
    tool_call_count = sum(1 for msg in messages if isinstance(msg, ToolMessage))

    # 如果最后一条消息包含工具调用
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        # 如果已经调用了3次或更多工具，强制结束
        if tool_call_count >= 3:
            return "end"
        return "tools"

    # 否则结束
    return "end"
