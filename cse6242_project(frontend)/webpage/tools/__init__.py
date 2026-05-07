"""
Scholar Compass Tools

新工具（当前使用）在 tools/_new/ 下：
  - factual_query.py
  - semantic_search.py
  - query_templates.py
  - analyze_author_trajectory.py
  - analyze_collaboration.py
  - compare_scholars.py
  - recommend_advisors.py

旧工具已标记为 _deprecated_，保留备查但不再调用。
"""

# 不导出任何内容，各模块直接 from tools._new.xxx import xxx
# 新工具通过 graph/nodes.py 中的 handler 直接调用
