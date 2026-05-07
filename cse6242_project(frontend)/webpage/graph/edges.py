from typing import Literal
from langchain_core.messages import AIMessage, ToolMessage
from graph.state import AgentState

def _get_tool_name(tool_call) -> str:
    """安全地获取工具名称，兼容对象和字典类型"""
    if isinstance(tool_call, dict):
        return tool_call.get('name', 'unknown')
    return getattr(tool_call, 'name', 'unknown')

def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """决定是否继续执行工具

    路由函数：
    - 如果 LLM 返回工具调用 → 转到 tools 节点
    - 如果已经调用了多次工具 → 结束
    - 如果检测到重复调用相同工具 → 结束
    - 否则 → 结束
    """
    messages = state["messages"]
    last_message = messages[-1]

    # 统计已经调用的工具次数
    tool_call_count = sum(1 for msg in messages if isinstance(msg, ToolMessage))

    # 如果最后一条消息包含工具调用
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        # ⚠️ 严格限制：最多调用 2 次工具
        if tool_call_count >= 2:
            print(f"[Edge] ⚠️ 已达到最大工具调用次数限制 (2次)，强制结束")
            return "end"

        # 检测是否在重复调用 dynamic_graph_retrieval
        if last_message.tool_calls:
            current_tool = _get_tool_name(last_message.tool_calls[0])
            if current_tool == "dynamic_graph_retrieval":
                # 检查之前是否已经调用过这个工具
                for msg in messages[-5:]:  # 检查最近5条消息
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        if _get_tool_name(msg.tool_calls[0]) == "dynamic_graph_retrieval":
                            print(f"[Edge] ⚠️ 检测到重复调用 dynamic_graph_retrieval，强制结束")
                            return "end"

        return "tools"

    # 否则结束
    return "end"
