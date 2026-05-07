# CLAUDE.md — Scholar Compass 项目说明

## 项目架构

```
webpage/
├── graph/                    # LangGraph 核心层 ⭐ 已稳定，谨慎修改
│   ├── graph.py              # 主流程定义
│   ├── nodes.py              # 节点实现（handler 函数）
│   ├── edges.py              # 路由逻辑
│   ├── state.py              # AgentState 定义
│   ├── schemas.py            # Pydantic 数据契约
│   └── node_helpers/         # 辅助模块
│       ├── author_resolver.py
│       ├── disambiguation_handler.py
│       └── llm_factory.py
│
├── tools/
│   ├── _new/                 # ✅ 新工具（当前使用）
│   │   ├── factual_query.py  # ✅ 已完成，勿动
│   │   ├── semantic_search.py# ✅ 已完成，勿动
│   │   └── query_templates.py# ✅ 已完成，勿动
│   └── (旧工具，待废弃)      # ❌ 不要调用这些
│       ├── author_analysis.py
│       ├── collaboration_analyzer.py
│       └── ...
│
├── prompts/
│   ├── routing_prompt.py     # ⭐ 路由层 prompt，谨慎修改
│   └── system_prompt.py
│
├── utils/
│   ├── session_store.py      # ✅ 已完成，勿动
│   ├── query_rewriter.py     # ❌ 已废弃，勿调用
│   └── task_classifier.py    # ❌ 已废弃，勿调用
│
├── eval/                     # 评估脚本
│   ├── benchmark.json
│   └── run_eval.py
│
└── app.py                    # Flask 入口
```

## 当前开发阶段

**正在做：4B — 新增 ANALYSIS 类型工具**

待实现的工具（放在 `tools/_new/` 下）：
1. `analyze_author_trajectory.py` — 作者研究方向随时间变化
2. `analyze_collaboration.py` — 合作网络分析
3. `compare_scholars.py` — 多学者对比
4. `recommend_advisors.py` — 导师推荐

## 关键技术约束

### LLM 选型（固定，不要改）
- **路由层**：Claude Haiku 4.5，通过 `_get_routing_llm()` 调用
- **text2cypher fallback**：Claude Haiku 4.5，通过 `_get_text2cypher_llm()` 调用
- **embedding**：BGE-M3 本地模型，MPS 加速
- **禁止**：在新工具里随意引入新的 LLM 调用，必须复用 llm_factory.py

### Neo4j 连接
- URI: bolt://localhost:7688（注意不是默认 7687）
- Database: neo4j（不是 academic_graph）
- 通过 `tools/neo4j_connector.py` 的 `get_neo4j_driver()` 获取连接

### 图数据模型
```
节点：Paper, Author, Subfield, Field, Source
关系：
  (Author)-[:AUTHORED]->(Paper)
  (Paper)-[:IN_SUBFIELD]->(Subfield)
  (Subfield)-[:IN_FIELD]->(Field)
  (Paper)-[:PUBLISHED_IN]->(Source)
  (Paper)-[:REFERENCES]->(Paper)

Paper 属性：id, title, publication_year, fwci, cited_by_count,
           abstract, embedding, embedding_quality
Author 属性：id, display_name
Subfield 属性：id, display_name
```

### Pydantic 版本
- 使用 **Pydantic v2**
- 用 `model_validate` 而不是 `parse_obj`
- 用 `model_dump_json()` 而不是 `.json()`

### 新工具接口规范
所有新工具必须遵循：

```python
from langchain_core.tools import tool
from tools.neo4j_connector import get_neo4j_driver
import os

@tool
def my_new_tool(
    resolved_query: str,
    entities_json: str,       # EntitySet.model_dump_json() 的结果
    extra_param: str = None,
) -> str:
    """工具描述"""
    from graph.schemas import EntitySet
    entities = EntitySet.model_validate_json(entities_json)
    # ... 实现
    return "格式化后的结果字符串"
```

### 禁止操作（Claude Code 硬约束）
- ❌ 禁止修改 `tools/_new/factual_query.py`
- ❌ 禁止修改 `tools/_new/semantic_search.py`
- ❌ 禁止修改 `tools/_new/query_templates.py`
- ❌ 禁止修改 `graph/schemas.py` 的已有字段（可以新增）
- ❌ 禁止修改 `graph/node_helpers/author_resolver.py`
- ❌ 禁止调用 `tools/` 根目录下的旧工具
- ❌ 禁止执行任何删除数据库数据的操作
- ❌ 禁止执行 `docker rm -v`、`docker volume rm`
- ❌ 禁止用 `importlib.util` 动态加载（用标准 import）

### 测试要求
- 每个新工具必须先跑单元测试再集成
- 单元测试放在 `tools/_new/test_<tool_name>.py`
- 测试用真实 Neo4j 数据（不用 mock）
- 如果 API 调不通，直接说，不要编造输出

## 常见问题

**Q: Neo4j 连不上？**
```bash
docker ps | grep neo4j          # 确认容器在跑
docker restart academic_graph_v2  # 如果没跑，重启（不是删除）
```

**Q: Anthropic API 429 rate limit？**
等 10-20 秒重试，不要改代码。

**Q: embedding 模型加载慢？**
第一次加载 BGE-M3 约 6 秒，之后复用缓存，正常现象。