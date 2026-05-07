#!/bin/bash
# 端到端 API 回归测试
# 运行前确保 Flask 应用已启动: python app.py

BASE_URL="http://localhost:5000"
SESSION_ID="test_session_$(date +%s)"

echo "========================================"
echo "步骤 4C: API 集成测试"
echo "Session ID: $SESSION_ID"
echo "========================================"

echo ""
echo "=== Turn 1: 触发消歧 ==="
curl -s -X POST $BASE_URL/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"介绍一下 Yao Xie\", \"session_id\": \"$SESSION_ID\"}" \
  | python -m json.tool

echo ""
echo ""
echo "=== Turn 2: 消歧响应（应该快速路径 <100ms）==="
time curl -s -X POST $BASE_URL/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"1\", \"session_id\": \"$SESSION_ID\"}" \
  | python -m json.tool

echo ""
echo ""
echo "=== Turn 3: 后续提问（应该使用 session 实体）==="
curl -s -X POST $BASE_URL/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"她的 top 5 高被引论文\", \"session_id\": \"$SESSION_ID\"}" \
  | python -m json.tool

echo ""
echo ""
echo "=== Turn 4: 另一个查询（验证 session 持久化）==="
curl -s -X POST $BASE_URL/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"她合作最多的 3 个人\", \"session_id\": \"$SESSION_ID\"}" \
  | python -m json.tool

echo ""
echo ""
echo "========================================"
echo "验证 Neo4j Session 节点状态"
echo "========================================"
echo "请在 Neo4j Browser 执行:"
echo ""
echo "MATCH (s:Session {session_id: '$SESSION_ID'})"
echo "RETURN s.session_id AS session_id,"
echo "       s.routing_resolved_entities_json AS entities,"
echo "       s.routing_pending_clarification_json AS pending,"
echo "       s.routing_updated_at AS updated_at"
echo ""
