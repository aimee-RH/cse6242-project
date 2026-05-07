# Graph module for LangGraph agent
"""
LangGraph Agent Module

This module provides the main graph application for the Scholar Compass system.
It exports the compiled LangGraph workflow, state definitions, and routing schemas.

Usage:
    from graph import graph_app, RoutingDecision
    result = graph_app.invoke({"messages": [user_message]})
"""

__version__ = "2.0.0"  # Bumped for routing layer addition

# Import state and schemas first (they don't depend on graph_app)
from graph.state import AgentState

# Import routing layer schemas
from graph.schemas import (
    RoutingDecision,
    EntitySet,
    ResolvedAuthor,
    AuthorCandidate,
    TimeRange,
)

# Lazy-load graph_app to avoid circular import issues
_graph_app = None

def get_graph_app():
    """Get or create the graph application instance."""
    global _graph_app
    if _graph_app is None:
        from graph.graph import create_graph
        _graph_app = create_graph()
    return _graph_app

# For backward compatibility, expose graph_app as a property
class _GraphAppProxy:
    """Proxy for lazy-loading graph_app."""
    def __getattr__(self, name):
        return getattr(get_graph_app(), name)

    def __call__(self, *args, **kwargs):
        return get_graph_app()(*args, **kwargs)

graph_app = _GraphAppProxy()

__all__ = [
    'graph_app',
    'AgentState',
    'RoutingDecision',
    'EntitySet',
    'ResolvedAuthor',
    'AuthorCandidate',
    'TimeRange',
]
