"""
Routing Layer Schema Definitions

This module defines the data contracts for the pre-routing layer that sits
at the entry of LangGraph. It consolidates query rewriting, task classification,
and entity resolution into a single LLM call.

Author: Scholar Compass Team
Date: 2025-04-20
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any


class TimeRange(BaseModel):
    """解析后的时间范围

    用于将模糊时间表达（"最近"、"近几年"）转换为具体年份范围。
    当前年份假设为 2026。
    """
    start_year: int = Field(..., description="起始年份")
    end_year: int = Field(..., description="结束年份")

    # 原始表达（用于调试）
    original_expression: Optional[str] = Field(
        None, description="原始时间表达，如'最近三年'、'2020-2022'"
    )


class AuthorCandidate(BaseModel):
    """重名作者的候选项（用于 CLARIFICATION_NEEDED 时反问用户）

    当识别到多个同名作者时，每个候选的信息。
    """
    author_id: str = Field(..., description="OpenAlex ID（完整 URL 格式）")
    name: str = Field(..., description="作者姓名")
    paper_count: int = Field(default=0, description="论文总数")
    total_citations: int = Field(default=0, description="累计被引次数")
    max_citations: int = Field(default=0, description="单篇最高被引次数")
    sample_titles: List[str] = Field(
        default_factory=list,
        description="代表作标题列表（前 3 篇，按引用数排序）"
    )
    # 未来数据补全后使用
    affiliation: Optional[str] = Field(None, description="所属机构（如有）")
    research_areas: List[str] = Field(
        default_factory=list,
        description="研究领域关键词（用于区分重名）"
    )
    # 旧字段保留（向后兼容）
    similarity_score: Optional[float] = Field(
        None,
        description="与当前查询上下文的语义相似度 0-1"
    )


class ResolvedAuthor(BaseModel):
    """已解析的作者

    可能包含唯一匹配，也可能包含多个候选（重名情况）。
    """
    name: str = Field(..., description="作者名称")

    # 如果唯一匹配，填充此字段
    author_id: Optional[str] = Field(
        default=None, description="已解析的 OpenAlex ID（唯一匹配时）"
    )

    # 解析置信度和候选列表
    confidence: float = Field(
        ..., description="解析置信度 0-1，<0.7 视为不确定需要澄清"
    )

    # 如果重名，列出候选
    candidates: List[AuthorCandidate] = Field(
        default_factory=list,
        description="重名时的候选列表，每项包含 name, author_id, research_field"
    )

    # 原始表达（用于调试）
    original_expression: Optional[str] = Field(
        None, description="原始表达，如'他'、'这位老师'、'张教授'"
    )


class EntitySet(BaseModel):
    """实体识别结果

    包含从查询中识别出的所有实体及其解析状态。
    """
    # 作者相关
    authors: List[ResolvedAuthor] = Field(
        default_factory=list,
        description="已识别的作者（包含唯一匹配和重名情况）"
    )
    unresolved_authors: List[str] = Field(
        default_factory=list,
        description="无法解析的作者名（数据库中未找到）"
    )

    # 研究主题
    topics: List[str] = Field(
        default_factory=list,
        description="研究主题/领域关键词"
    )

    # 时间范围
    time_range: Optional[TimeRange] = Field(
        None, description="解析后的时间范围"
    )

    # 论文引用
    paper_ids: List[str] = Field(
        default_factory=list,
        description="上下文提到的具体论文 ID"
    )

    # 其他实体
    venues: List[str] = Field(
        default_factory=list,
        description="会议/期刊名称"
    )


class RoutingDecision(BaseModel):
    """前置路由层输出决策

    这是路由层节点的输出，包含指代消解、任务分类、实体识别的结果。
    后续节点根据此决策进行路由和执行。

    字段数量控制在 9 个，确保 LLM 输出准确率。
    """

    # ========== 核心输出（5 个）==========
    resolved_query: str = Field(
        ...,
        description="消解后的完整 query（指代替换为明确实体）"
    )

    task_type: Literal[
        "FACTUAL_QUERY",        # 事实查询：模板 Cypher 可解决
        "SEMANTIC_SEARCH",      # 语义检索：需要向量或模糊匹配
        "ANALYSIS",             # 分析推理：研究轨迹、契合度等
        "COMPLEX",              # 复合任务：需要 ReAct 多步
        "CLARIFICATION_NEEDED", # 信息不足，需要反问
    ] = Field(
        ...,
        description="任务分类（按处理路径分，用于路由决策）"
    )

    entities: EntitySet = Field(
        default_factory=EntitySet,
        description="实体识别结果"
    )

    suggested_tools: List[str] = Field(
        default_factory=list,
        description="建议使用的下游工具名（允许多个）"
    )

    reasoning: str = Field(
        ...,
        description="分类依据（便于调试和评估）"
    )

    # ========== 可选输出（2 个）==========
    clarification_question: Optional[str] = Field(
        None,
        description=(
            "如果 task_type 是 CLARIFICATION_NEEDED，"
            "这里放反问内容（自然语言形式）"
        )
    )

    ambiguity_reason: Optional[Literal[
        "multiple_author_candidates",  # 重名，需用户选择
        "missing_context",              # 代词无前文
        "vague_topic",                  # 话题过泛
        "missing_info",                 # 缺少关键信息
    ]] = Field(
        None,
        description=(
            "机器可读的歧义原因，"
            "只在 task_type == CLARIFICATION_NEEDED 时填充"
        )
    )

    # ========== 元数据（2 个）==========
    routing_confidence: Literal["high", "medium", "low"] = Field(
        "medium",
        description="路由分类置信度（复用 task_classifier 的字段设计）"
    )

    has_coreference: bool = Field(
        default=False,
        description="是否进行了指代消解（复用 query_rewriter 字段）"
    )

    # ========== 旧分类体系（保留给下游工具作为 hint）==========
    query_shape: Optional[Literal[
        "single_lookup",    # 单实体查询
        "comparison",       # 对比分析
        "aggregation",      # 聚合统计
        "multi_hop",        # 多跳推理
    ]] = Field(
        None,
        description=(
            "旧分类体系（按 Cypher 查询形态分），"
            "仅在 task_type == FACTUAL_QUERY 时有意义，"
            "用于 factual_query 工具选择模板"
        )
    )


class PendingClarification(BaseModel):
    """上一轮挂起的候选，等待用户选择

    当路由层检测到重名作者时，会触发 CLARIFICATION_NEEDED。
    这个结构保存当前的候选列表，下一轮如果用户回复编号（如"1"），
    可以直接从 candidates 中取出对应的 author_id。
    """
    entity_name: str = Field(..., description="被澄清的实体名，如 'Yao Xie'")
    candidates: List[AuthorCandidate] = Field(..., description="候选列表")
    created_at: Optional[str] = Field(None, description="ISO timestamp，可选")
