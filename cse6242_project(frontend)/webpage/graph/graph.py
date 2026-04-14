from langgraph.graph import StateGraph, END
from graph.state import AgentState
from graph.nodes import call_model, tool_node
from graph.edges import should_continue

def create_graph():
    """Create LangGraph StateGraph"""
    # Create state graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", call_model)
    workflow.add_node("tools", tool_node)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )

    # Add edge from tools node back to agent (loop)
    workflow.add_edge("tools", "agent")

    # Compile graph
    # Note: recursion_limit is set in invoke(), not compile()
    app = workflow.compile()
    return app

# Create global graph instance
graph_app = create_graph()
