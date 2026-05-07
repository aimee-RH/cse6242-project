#!/usr/bin/env python3
"""
Agent Execution Logger

This module provides detailed logging for Agent execution steps,
including Cypher queries, tool calls, and intermediate results.

Author: Scholar Compass Team
Date: 2025-04-16
"""

import logging
import os
import json
from datetime import datetime
from typing import Any, Dict
import functools

# ========================================
# Logger Configuration
# ========================================

class AgentLogger:
    """
    详细的Agent执行日志记录器

    Features:
    - 记录每个Agent步骤
    - 记录生成的Cypher语句
    - 记录工具调用过程
    - 记录查询结果统计
    - 支持彩色输出（终端）
    - 输出到文件和控制台
    """

    def __init__(self, log_file: str = "agent_execution.log"):
        """
        Initialize the logger

        Args:
            log_file: Path to the log file
        """
        self.log_file = log_file
        self.execution_id = None

        # 创建logger
        self.logger = logging.getLogger("AgentExecution")
        self.logger.setLevel(logging.DEBUG)

        # 清除已有的handlers
        self.logger.handlers.clear()

        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 控制台Handler（彩色）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

        # 文件Handler
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

        # 执行计数器
        self.step_count = 0
        self.cypher_count = 0
        self.tool_call_count = 0

    def start_execution(self, user_message: str, session_id: str = None):
        """开始一个新的执行记录"""
        self.execution_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.step_count = 0
        self.cypher_count = 0
        self.tool_call_count = 0

        self.log("="*80, level="INFO")
        self.log(f"🚀 新的执行开始", level="INFO")
        self.log(f"执行ID: {self.execution_id}", level="INFO")
        self.log(f"会话ID: {session_id[:8] if session_id else 'None'}...", level="INFO")
        self.log(f"用户消息: {user_message}", level="INFO")
        self.log("="*80, level="INFO")

    def log_step(self, step_name: str, details: Dict[str, Any] = None):
        """
        记录一个执行步骤

        Args:
            step_name: 步骤名称
            details: 详细信息字典
        """
        self.step_count += 1

        self.log("", level="DEBUG")
        self.log(f"📍 步骤 {self.step_count}: {step_name}", level="INFO")

        if details:
            for key, value in details.items():
                if key == "cypher":
                    self.log_cypher(value)
                elif key == "tool_call":
                    self.log_tool_call(value)
                elif key == "result":
                    self.log_result(value)
                else:
                    self.log(f"  {key}: {value}", level="DEBUG")

    def log_cypher(self, cypher: str, metadata: Dict[str, Any] = None):
        """
        记录Cypher查询

        Args:
            cypher: Cypher语句
            metadata: 元数据（如执行时间、结果数量）
        """
        self.cypher_count += 1

        self.log("", level="DEBUG")
        self.log(f"🔍 Cypher查询 #{self.cypher_count}", level="INFO")
        self.log("-" * 60, level="DEBUG")

        # 美化输出Cypher
        formatted_cypher = self._format_cypher(cypher)
        self.log(formatted_cypher, level="INFO")

        if metadata:
            self.log("", level="DEBUG")
            for key, value in metadata.items():
                self.log(f"  📊 {key}: {value}", level="DEBUG")

    def log_tool_call(self, tool_info: Dict[str, Any]):
        """
        记录工具调用

        Args:
            tool_info: 工具信息
        """
        self.tool_call_count += 1

        tool_name = tool_info.get("name", "Unknown")
        tool_params = tool_info.get("parameters", {})

        self.log("", level="DEBUG")
        self.log(f"🔧 工具调用 #{self.tool_call_count}: {tool_name}", level="INFO")
        self.log("-" * 60, level="DEBUG")

        if tool_params:
            self.log("参数:", level="DEBUG")
            for key, value in tool_params.items():
                if isinstance(value, str) and len(value) > 100:
                    value = value[:97] + "..."
                self.log(f"  - {key}: {value}", level="DEBUG")

    def log_result(self, result: Any, result_type: str = "result"):
        """
        记录结果

        Args:
            result: 结果数据
            result_type: 结果类型
        """
        self.log("", level="DEBUG")
        self.log(f"📊 {result_type}:", level="INFO")

        if isinstance(result, list):
            if not result:
                self.log("  (空结果)", level="DEBUG")
            elif len(result) <= 5:
                for i, item in enumerate(result, 1):
                    self.log(f"  {i}. {item}", level="DEBUG")
            else:
                self.log(f"  共 {len(result)} 条记录", level="DEBUG")
                # 显示前3条
                for i, item in enumerate(result[:3], 1):
                    self.log(f"  {i}. {item}", level="DEBUG")
                if len(result) > 3:
                    self.log(f"  ... 还有 {len(result)-3} 条记录", level="DEBUG")
        elif isinstance(result, dict):
            for key, value in result.items():
                if isinstance(value, str) and len(value) > 100:
                    value = value[:97] + "..."
                self.log(f"  {key}: {value}", level="DEBUG")
        else:
            # 字符串或其他类型
            result_str = str(result)
            if len(result_str) > 200:
                result_str = result_str[:197] + "..."
            self.log(f"  {result_str}", level="DEBUG")

    def log_llm_call(self, prompt: str, response: str, tokens: int = None):
        """
        记录LLM调用

        Args:
            prompt: 输入Prompt
            response: LLM响应
            tokens: Token数量
        """
        self.log("", level="DEBUG")
        self.log(f"🤖 LLM调用", level="INFO")
        self.log("-" * 60, level="DEBUG")

        # 显示Prompt（截断）
        prompt_preview = prompt[:300] + "..." if len(prompt) > 300 else prompt
        self.log(f"输入:\n{prompt_preview}", level="DEBUG")

        # 显示响应（截断）
        response_preview = response[:300] + "..." if len(response) > 300 else response
        self.log(f"输出:\n{response_preview}", level="DEBUG")

        if tokens:
            self.log(f"Tokens: {tokens}", level="DEBUG")

    def log_error(self, error: Exception, context: str = ""):
        """
        记录错误

        Args:
            error: 异常对象
            context: 错误上下文
        """
        self.log("", level="ERROR")
        self.log(f"❌ 错误: {context}", level="ERROR")
        self.log(f"错误类型: {type(error).__name__}", level="ERROR")
        self.log(f"错误信息: {str(error)}", level="ERROR")

    def log_summary(self):
        """记录执行摘要"""
        self.log("="*80, level="INFO")
        self.log(f"📊 执行摘要 - ID: {self.execution_id}", level="INFO")
        self.log("-" * 40, level="INFO")
        self.log(f"总步骤数: {self.step_count}", level="INFO")
        self.log(f"Cypher查询数: {self.cypher_count}", level="INFO")
        self.log(f"工具调用数: {self.tool_call_count}", level="INFO")
        self.log("="*80, level="INFO")

    def log(self, message: str, level: str = "INFO"):
        """
        简单的日志记录

        Args:
            message: 日志消息
            level: 日志级别
        """
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)

    def _format_cypher(self, cypher: str) -> str:
        """
        美化Cypher输出

        Args:
            cypher: Cypher语句

        Returns:
            格式化后的Cypher语句
        """
        # 移除多余的空白
        lines = cypher.split('\n')
        stripped_lines = [line.strip() for line in lines if line.strip()]

        # 关键字高亮（在终端中通过颜色实现）
        keywords = ['MATCH', 'WHERE', 'RETURN', 'ORDER BY', 'LIMIT', 'WITH']

        formatted_lines = []
        for line in stripped_lines:
            # 简单的缩进格式化
            if line.upper().startswith(('MATCH', 'RETURN', 'WITH')):
                formatted_lines.append(line)
            elif line.upper().startswith(('WHERE', 'ORDER BY')):
                formatted_lines.append("  " + line)
            else:
                formatted_lines.append("    " + line)

        return '\n'.join(formatted_lines)


# ========================================
# Colored Formatter for Terminal Output
# ========================================

class ColoredFormatter(logging.Formatter):
    """
    带颜色输出的日志格式化器
    """

    # ANSI颜色代码
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
        'RESET': '\033[0m'        # 重置
    }

    def format(self, record):
        # 保存原始的levelname
        original_levelname = record.levelname

        # 添加颜色到levelname
        if record.levelname in self.COLORS:
            color = self.COLORS[record.levelname]
            reset = self.COLORS['RESET']
            record.levelname = f"{color}{record.levelname}{reset}"

        # 调用父类格式化
        result = super().format(record)

        # 恢复原始levelname（避免影响其他handler）
        record.levelname = original_levelname

        return result


# ========================================
# 装饰器：自动记录工具调用
# ========================================

def log_tool_execution(logger: AgentLogger):
    """
    装饰器：自动记录工具执行的详细信息

    使用方法:
    @log_tool_execution(logger)
    def my_tool(query: str):
        ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_name = func.__name__

            # 记录工具调用开始
            logger.log_step(
                f"调用工具: {func_name}",
                {
                    "parameters": {
                        "args": args,
                        "kwargs": kwargs
                    }
                }
            )

            try:
                # 执行工具
                result = func(*args, **kwargs)

                # 记录结果
                logger.log_result(result, f"{func_name}结果")

                return result

            except Exception as e:
                # 记录错误
                logger.log_error(e, f"工具 {func_name} 执行失败")
                raise

        return wrapper
    return decorator


# ========================================
# 全局Logger实例
# ========================================

# 创建全局logger实例
agent_logger = AgentLogger("logs/agent_execution.log")

# 确保logs目录存在
os.makedirs("logs", exist_ok=True)


# ========================================
# 便捷函数
# ========================================

def get_logger() -> AgentLogger:
    """获取全局logger实例"""
    return agent_logger

def log_cypher_generation(cypher: str, user_query: str, attempt: int):
    """
    记录Cypher生成过程

    Args:
        cypher: 生成的Cypher语句
        user_query: 用户查询
        attempt: 尝试次数
    """
    get_logger().log_cypher(cypher, {
        "user_query": user_query,
        "attempt": attempt,
        "type": "generation"
    })

def log_cypher_execution(cypher: str, result_count: int, execution_time: float):
    """
    记录Cypher执行结果

    Args:
        cypher: 执行的Cypher语句
        result_count: 结果数量
        execution_time: 执行时间（秒）
    """
    get_logger().log_cypher(cypher, {
        "result_count": result_count,
        "execution_time": f"{execution_time:.3f}s",
        "type": "execution"
    })


if __name__ == "__main__":
    """测试日志功能"""
    logger = get_logger()

    logger.start_execution("测试消息", "test_session_123")

    # 模拟Cypher生成
    test_cypher = """MATCH (a:Author)-[:AUTHORED]->(p:Paper)
WHERE toLower(a.display_name) CONTAINS toLower('Yao Xie')
RETURN a, count(p) as papers"""

    logger.log_cypher(test_cypher, {
        "user_query": "Yao Xie的论文数",
        "attempt": 1
    })

    # 模拟工具调用
    logger.log_tool_call({
        "name": "dynamic_graph_retrieval",
        "parameters": {"query": "Yao Xie", "max_results": 5}
    })

    # 模拟结果
    logger.log_result({"papers": 78, "citations": 790}, "统计结果")

    logger.log_summary()
