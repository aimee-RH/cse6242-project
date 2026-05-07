from typing import TypedDict, Annotated, Sequence, Optional, Dict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

# Import schemas for type hints resolution (needed by LangGraph's get_type_hints)
# These are used in forward references below
from graph.schemas import RoutingDecision, ResolvedAuthor, PendingClarification


class AgentState(TypedDict):
    """Agent state definition

    Uses add_messages to ensure messages are appended rather than overwritten
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 路由层输出（由 route_query_node 填充）
    routing_decision: Optional["RoutingDecision"]

    # 新增：session 内已消歧实体缓存
    # key 是作者姓名（display_name），value 是 ResolvedAuthor
    # 例: {"Yao Xie": ResolvedAuthor(name="Yao Xie", author_id="https://...", confidence=1.0)}
    resolved_entities: Dict[str, "ResolvedAuthor"]

    # 新增：上一轮的待澄清候选（用于处理数字选择）
    # 当 routing_decision.task_type == CLARIFICATION_NEEDED 时填充
    # 下一轮如果用户回复"1"/"2"等，从这里取对应的 candidate
    pending_clarification: Optional["PendingClarification"]
