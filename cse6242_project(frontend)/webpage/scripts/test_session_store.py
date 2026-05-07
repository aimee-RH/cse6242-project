"""
Test session_store module
"""
import os
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

from utils.session_store import load_routing_state, save_routing_state, ensure_session_constraint
from graph.schemas import ResolvedAuthor, PendingClarification, AuthorCandidate

# 测试 session_id
test_session = 'test_session_store_001'

print('=== 测试 1: 创建约束 ===')
try:
    ensure_session_constraint()
    print('✓ 约束创建成功')
except Exception as e:
    print(f'! 约束创建: {e}')

print()
print('=== 测试 2: 加载不存在的 session ===')
result = load_routing_state(test_session)
print(f'resolved_entities: {result["resolved_entities"]}')
print(f'pending_clarification: {result["pending_clarification"]}')

print()
print('=== 测试 3: 保存 routing state ===')
# 创建一个 ResolvedAuthor
resolved = ResolvedAuthor(
    name='Yao Xie',
    author_id='https://openalex.org/A5047736740',
    confidence=1.0,
    candidates=[]
)

save_routing_state(
    session_id=test_session,
    resolved_entities={'Yao Xie': resolved},
    pending_clarification=None
)
print('✓ 保存成功')

print()
print('=== 测试 4: 重新加载验证 ===')
result = load_routing_state(test_session)
print(f'resolved_entities: {list(result["resolved_entities"].keys())}')
if result.get("resolved_entities").get("Yao Xie"):
    print(f'Yao Xie author_id: {result["resolved_entities"]["Yao Xie"].author_id}')

print()
print('=== 测试 5: 保存 pending_clarification ===')
pending = PendingClarification(
    entity_name='Test Author',
    candidates=[
        AuthorCandidate(
            author_id='https://test.com/1',
            name='Test Author',
            paper_count=10,
            total_citations=100
        )
    ]
)
save_routing_state(
    session_id=test_session,
    resolved_entities={'Yao Xie': resolved},
    pending_clarification=pending
)
print('✓ 保存成功')

print()
print('=== 测试 6: 验证 pending_clarification ===')
result = load_routing_state(test_session)
if result.get("pending_clarification"):
    print(f'pending_clarification: {result["pending_clarification"].entity_name}')

print()
print('=== 所有测试完成 ===')
