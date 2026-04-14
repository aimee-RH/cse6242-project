from typing import TypedDict, Annotated, Sequence
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """Agent state definition

    Uses add_messages to ensure messages are appended rather than overwritten
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
