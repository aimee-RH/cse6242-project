#!/usr/bin/env python3
"""
Request Tracer Module - Complete Request Lifecycle Tracking

This module provides detailed tracing for each request through the entire pipeline:
- HTTP Request
- Session Management
- Query Rewriter
- Task Classifier
- LangGraph Agent
- Tool Execution
- Neo4j Queries
- Fact Checker
- Response Generation

Author: Scholar Compass Team
Date: 2025-04-17
"""

import uuid
import time
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from contextlib import contextmanager
from pathlib import Path


# ========================================
# Data Structures
# ========================================

@dataclass
class TraceEvent:
    """单个追踪事件"""
    timestamp: float
    level: str  # INFO, DEBUG, WARNING, ERROR
    component: str  # API, Memory, Rewriter, Classifier, Agent, Tool, Neo4j, FactCheck
    event_type: str  # request_start, session_created, query_rewritten, tool_call, etc.
    message: str
    data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "timestamp": datetime.fromtimestamp(self.timestamp).isoformat(),
            "level": self.level,
            "component": self.component,
            "event_type": self.event_type,
            "message": self.message,
            "data": self.data
        }


@dataclass
class RequestTrace:
    """完整的请求追踪"""
    trace_id: str
    session_id: Optional[str]
    start_time: float
    end_time: Optional[float] = None
    original_query: Optional[str] = None
    rewritten_query: Optional[str] = None
    query_type: Optional[str] = None
    referenced_scholars: List[str] = field(default_factory=list)
    events: List[TraceEvent] = field(default_factory=list)

    # 统计信息
    tool_calls: int = 0
    cypher_queries: int = 0
    llm_calls: int = 0

    def add_event(self, level: str, component: str, event_type: str,
                  message: str, data: Dict = None):
        """添加事件"""
        self.events.append(TraceEvent(
            timestamp=time.time(),
            level=level,
            component=component,
            event_type=event_type,
            message=message,
            data=data or {}
        ))

    def get_duration(self) -> float:
        """获取总耗时"""
        end = self.end_time or time.time()
        return end - self.start_time

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "trace_id": self.trace_id,
            "session_id": self.session_id,
            "duration": f"{self.get_duration():.3f}s",
            "duration_raw": self.get_duration(),
            "original_query": self.original_query,
            "rewritten_query": self.rewritten_query,
            "query_type": self.query_type,
            "referenced_scholars": self.referenced_scholars,
            "event_count": len(self.events),
            "tool_calls": self.tool_calls,
            "cypher_queries": self.cypher_queries,
            "llm_calls": self.llm_calls,
            "events": [e.to_dict() for e in self.events]
        }

    def print_summary(self):
        """打印追踪摘要"""
        duration = self.get_duration()

        print(f"\n{'='*70}")
        print(f"📊 Trace: {self.trace_id[:8]}... | "
              f"Duration: {duration:.3f}s | "
              f"Events: {len(self.events)}")

        if self.query_type:
            print(f"📋 Query Type: {self.query_type}")
        if self.referenced_scholars:
            print(f"👥 Scholars: {', '.join(self.referenced_scholars)}")
        if self.original_query != self.rewritten_query:
            print(f"🔄 Query: {self.original_query[:40]}... → {self.rewritten_query[:40]}...")

        print(f"{'='*70}\n")

    def print_detailed(self):
        """打印详细追踪"""
        self.print_summary()

        for event in self.events:
            time_str = datetime.fromtimestamp(event.timestamp).strftime("%H:%M:%S.%f")[:-3]

            # 图标
            if event.level == "ERROR":
                icon = "❌"
            elif event.level == "WARNING":
                icon = "⚠️ "
            elif event.component == "API":
                icon = "📨"
            elif event.component == "Memory":
                icon = "💾"
            elif event.component == "Rewriter":
                icon = "🔄"
            elif event.component == "Classifier":
                icon = "🏷️ "
            elif event.component == "Agent":
                icon = "🧠"
            elif event.component == "Tool":
                icon = "🔧"
            elif event.component == "Neo4j":
                icon = "⚡"
            elif event.component == "FactCheck":
                icon = "✅"
            else:
                icon = "  "

            print(f"{icon} [{event.component}] {time_str} │ {event.message}")

            if event.data:
                for key, value in event.data.items():
                    if key == "cypher":
                        print(f"   Cypher: {value[:100]}...")
                    elif key == "result_count":
                        print(f"   Results: {value}")
                    elif key == "execution_time":
                        print(f"   Time: {value}")
                    else:
                        print(f"   {key}: {value}")

        print(f"\n{'='*70}\n")


# ========================================
# Tracer Class
# ========================================

class RequestTracer:
    """请求追踪器"""

    _current: RequestTrace = None
    _log_dir: Path = None
    _enabled: bool = True

    @classmethod
    def set_log_dir(cls, log_dir: str):
        """设置日志目录"""
        cls._log_dir = Path(log_dir)
        cls._log_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def enable(cls):
        """启用追踪"""
        cls._enabled = True

    @classmethod
    def disable(cls):
        """禁用追踪"""
        cls._enabled = False

    @classmethod
    @contextmanager
    def trace_request(cls, original_query: str, session_id: str = None):
        """
        追踪一个完整的请求

        Usage:
            with RequestTracer.trace_request(user_message, session_id) as trace:
                # ... 处理逻辑
                trace.original_query = original_query
                trace.rewritten_query = rewritten_query
                trace.query_type = query_type
        """
        if not cls._enabled:
            # 创建空的 trace 上下文
            class DummyTrace:
                def __enter__(self): return self
                def __exit__(self, *args): return None
            dummy = DummyTrace()
            yield dummy
            return

        trace = RequestTrace(
            trace_id=str(uuid.uuid4()),
            session_id=session_id,
            start_time=time.time(),
            original_query=original_query
        )
        cls._current = trace

        trace.add_event("INFO", "API", "request_start",
                        f"Request received: {original_query[:80]}...")

        try:
            yield trace
        finally:
            trace.end_time = time.time()
            trace.add_event("INFO", "API", "request_end",
                            f"Request completed in {trace.get_duration():.3f}s")

            # 保存到文件
            cls._save_trace(trace)

            # 打印摘要
            trace.print_summary()

            cls._current = None

    @classmethod
    def get_current(cls) -> Optional[RequestTrace]:
        """获取当前追踪"""
        return cls._current

    @classmethod
    def log_step(cls, component: str, event_type: str, message: str,
                 level: str = "INFO", data: Dict = None):
        """
        记录一个步骤

        Args:
            component: 组件名称 (API, Memory, Rewriter, Classifier, Agent, Tool, Neo4j, FactCheck)
            event_type: 事件类型 (request_start, session_created, query_rewritten, tool_call, etc.)
            message: 日志消息
            level: 日志级别 (INFO, DEBUG, WARNING, ERROR)
            data: 额外数据
        """
        if cls._current and cls._enabled:
            cls._current.add_event(level, component, event_type, message, data)

            # 实时打印关键事件
            if level in ["INFO", "WARNING", "ERROR"]:
                icon = {
                    "API": "📨",
                    "Memory": "💾",
                    "Rewriter": "🔄",
                    "Classifier": "🏷️ ",
                    "Agent": "🧠",
                    "Tool": "🔧",
                    "Neo4j": "⚡",
                    "FactCheck": "✅",
                }.get(component, "  ")

                print(f"{icon} [{component}] {message}")

    @classmethod
    def _save_trace(cls, trace: RequestTrace):
        """保存追踪到文件"""
        if not cls._log_dir:
            return

        log_file = cls._log_dir / f"traces_{datetime.now().strftime('%Y%m%d')}.jsonl"

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Warning: Failed to save trace: {e}")

    @classmethod
    def log_tool_call(cls, tool_name: str, parameters: Dict):
        """记录工具调用"""
        if cls._current and cls._enabled:
            cls._current.tool_calls += 1
            cls.log_step("Tool", "tool_call", f"Tool called: {tool_name}",
                       data={"tool": tool_name, "parameters": parameters})

    @classmethod
    def log_cypher(cls, cypher: str, result_count: int, execution_time: float):
        """记录 Cypher 查询"""
        if cls._current and cls._enabled:
            cls._current.cypher_queries += 1
            cls.log_step("Neo4j", "cypher_executed", "Cypher query executed",
                       data={
                           "cypher": cypher[:200],
                           "result_count": result_count,
                           "execution_time": f"{execution_time:.3f}s"
                       })

    @classmethod
    def log_llm_call(cls, prompt: str, response: str, tokens: int = None):
        """记录 LLM 调用"""
        if cls._current and cls._enabled:
            cls._current.llm_calls += 1
            cls.log_step("Agent", "llm_call", f"LLM call (tokens: {tokens or 'N/A'})",
                       data={"prompt_length": len(prompt), "response_length": len(response)})


# ========================================
# Convenience Functions
# ========================================

def trace_step(component: str, event_type: str, message: str,
                level: str = "INFO", data: Dict = None):
    """便捷的追踪函数"""
    RequestTracer.log_step(component, event_type, message, level, data)


def trace_tool_call(tool_name: str, parameters: Dict):
    """追踪工具调用"""
    RequestTracer.log_tool_call(tool_name, parameters)


def trace_cypher(cypher: str, result_count: int, execution_time: float):
    """追踪 Cypher 查询"""
    RequestTracer.log_cypher(cypher, result_count, execution_time)


# ========================================
# Testing
# ========================================

if __name__ == "__main__":
    """测试追踪器"""

    # 设置日志目录
    RequestTracer.set_log_dir("logs/traces")

    print("Testing RequestTracer...")

    # 模拟一个请求
    with RequestTracer.trace_request("Yao Xie 的 Top 5 高被引论文是什么？", "session_123") as trace:
        trace.original_query = "Yao Xie 的 Top 5 高被引论文是什么？"

        # 模拟各个步骤
        trace_step("Memory", "session_loaded", "Session loaded from database")
        trace_step("Rewriter", "query_checked", "No coreference detected")
        trace_step("Classifier", "query_classified", "Query type: single_lookup",
                 data={"confidence": "high", "entity_count": 1})

        trace_step("Agent", "agent_start", "Starting LangGraph Agent")
        trace_step("Tool", "tool_call", "dynamic_graph_retrieval called")
        trace_step("Neo4j", "cypher_executed", "Cypher query executed",
                 data={"result_count": 5, "execution_time": "0.123s"})
        trace_step("Agent", "agent_complete", "Agent completed")

        trace.rewritten_query = "Yao Xie 的 Top 5 高被引论文是什么？"
        trace.query_type = "single_lookup"
        trace.referenced_scholars = ["Yao Xie"]

        # 模拟耗时
        time.sleep(0.1)

    print("\n✅ Test complete! Check logs/traces/ for the trace file.")
