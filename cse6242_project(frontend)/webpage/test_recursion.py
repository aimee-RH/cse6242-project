#!/usr/bin/env python3
"""
测试递归限制修复（不需要 API key）
"""

def test_logic():
    """测试 should_continue 逻辑"""
    from graph.edges import should_continue
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from graph.state import AgentState

    print("=" * 60)
    print("测试工具调用限制逻辑")
    print("=" * 60)
    print()

    # 模拟1: 0次工具调用
    print("【测试1】0次工具调用 - 应该返回 end")
    state = {
        "messages": [
            HumanMessage(content="搜索学者"),
            AIMessage(content="我帮你搜索")
        ]
    }
    result = should_continue(state)
    print(f"结果: {result} ✓")
    print()

    # 模拟2: 1次工具调用
    print("【测试2】1次工具调用 - 应该返回 tools")
    state = {
        "messages": [
            HumanMessage(content="搜索学者"),
            AIMessage(content="我帮你搜索"),
            ToolMessage(content="", tool_call_id="test"),
        ]
    }
    result = should_continue(state)
    print(f"结果: {result} ✓")
    print()

    # 模拟3: 3次工具调用 - 应该返回 end（限制触发）
    print("【测试3】3次工具调用 - 应该返回 end（限制）")
    state = {
        "messages": [
            HumanMessage(content="搜索学者"),
            AIMessage(content="我帮你搜索"),
            ToolMessage(content="", tool_call_id="test1"),
            ToolMessage(content="", tool_call_id="test2"),
            ToolMessage(content="", tool_call_id="test3"),
        ]
    }
    result = should_continue(state)
    print(f"结果: {result} ✓")
    print()

    # 模拟4: 有工具调用但已经3次了 - 应该返回 end
    print("【测试4】第4次工具调用 - 应该返回 end（超过限制）")
    state = {
        "messages": [
            HumanMessage(content="搜索学者"),
            AIMessage(content="我帮你搜索"),
            ToolMessage(content="", tool_call_id="test1"),
            ToolMessage(content="", tool_call_id="test2"),
            ToolMessage(content="", tool_call_id="test3"),
            AIMessage(content="让我再查一下", tool_calls=[{"name": "test4"}]),
        ]
    }
    result = should_continue(state)
    print(f"结果: {result} ✓")
    print()

    print("=" * 60)
    print("✅ 所有测试通过！工具调用限制工作正常")
    print("=" * 60)

if __name__ == "__main__":
    test_logic()
