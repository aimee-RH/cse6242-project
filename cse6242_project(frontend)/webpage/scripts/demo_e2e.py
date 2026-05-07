"""
End-to-End Demo Script

Simulates a 4-turn conversation to verify the full LangGraph flow.
This tests the routing layer, disambiguation, and session entity persistence.

Author: Scholar Compass Team
Date: 2025-04-22
"""

import os
import sys
import time

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Check environment variables
assert os.getenv("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY not set"
print(f"[ENV] ANTHROPIC_API_KEY: {'✓' if os.getenv('ANTHROPIC_API_KEY') else '✗'}")
# MINIMAX_API_KEY is optional (fallback to Haiku)
print(f"[ENV] MINIMAX_API_KEY: {'✓' if os.getenv('MINIMAX_API_KEY') else 'optional (fallback to Haiku)'}")

# Import graph app
from graph import graph_app
from langchain_core.messages import HumanMessage

# Simulate session state accumulation
state = {
    "messages": [],
    "routing_decision": None,
    "resolved_entities": {},
    "pending_clarification": None,
}

turns = [
    "介绍一下 Yao Xie",                               # CLARIFICATION（重名）
    "1",                                               # 快速路径
    "她的 top 5 高被引论文",                           # FACTUAL 模板
    "她合作最多的 3 个人",                             # FACTUAL fallback
    "找一些做 federated learning 相关的论文",           # SEMANTIC_SEARCH
    "推荐几篇关于 change point detection 的论文",        # SEMANTIC_SEARCH
    "谁在做 computer vision 方向的研究？",              # SEMANTIC_SEARCH
    "Yao Xie 的研究方向随时间有什么变化？",             # ANALYSIS: trajectory
    "她和谁合作最多？",                                 # ANALYSIS: collaboration (contextual)
    "推荐几个做 reinforcement learning 的导师",         # ANALYSIS: recommend_advisors
    "哪位老师适合做 federated learning 方向？",         # ANALYSIS: recommend_advisors
]

for i, user_input in enumerate(turns, 1):
    print(f"\n{'='*70}")
    print(f"TURN {i}: {user_input}")
    print('='*70)

    # Accumulate message history
    state["messages"] = state["messages"] + [HumanMessage(content=user_input)]

    print(f"[Input] Messages before invoke: {len(state['messages'])}")

    t0 = time.time()
    try:
        result = graph_app.invoke(state, config={"recursion_limit": 10})
        elapsed = time.time() - t0

        # Update state (LangGraph merges returned fields)
        state.update(result)

        # Output key information for each turn
        decision = result.get("routing_decision")

        print(f"\n[Elapsed] {elapsed:.2f}s")
        print(f"[Task Type] {decision.task_type if decision else 'N/A'}")

        if decision:
            print(f"[Resolved Query] {decision.resolved_query[:80] if decision.resolved_query else 'N/A'}...")

            # Show clarification question if present
            if decision.clarification_question:
                print(f"[Clarification Needed]")
                print(decision.clarification_question[:500])

            # Show entities
            if decision.entities and decision.entities.authors:
                print(f"[Entities] {len(decision.entities.authors)} author(s)")
                for a in decision.entities.authors:
                    if a.author_id:
                        print(f"  - {a.name}: {a.author_id[:50]}...")
                    elif a.candidates:
                        print(f"  - {a.name}: {len(a.candidates)} candidates")

        # Take last AI message as system reply
        ai_messages = [m for m in result.get("messages", []) if m.type == "ai"]
        if ai_messages:
            reply = ai_messages[-1].content
            print(f"\n[System Reply]")
            print(reply[:800] if len(reply) > 800 else reply)
            if len(reply) > 800:
                print(f"... (truncated, total {len(reply)} chars)")
        else:
            print("\n[System Reply] (无 AI 消息)")

        # State snapshot
        print(f"\n[Session State]")
        resolved_keys = list(state.get('resolved_entities', {}).keys())
        print(f"  - resolved_entities: {resolved_keys if resolved_keys else '[]'}")
        pending = state.get('pending_clarification')
        if pending:
            print(f"  - pending_clarification: {pending.entity_name} ({len(pending.candidates)} candidates)")
        else:
            print(f"  - pending_clarification: None")

    except Exception as e:
        elapsed = time.time() - t0
        print(f"\n[ERROR after {elapsed:.2f}s]")
        print(f"Exception: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        break

print(f"\n{'='*70}")
print("DEMO COMPLETE")
print('='*70)
