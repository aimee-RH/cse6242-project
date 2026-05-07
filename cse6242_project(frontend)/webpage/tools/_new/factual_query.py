"""
Factual Query Tool

统一的事实查询工具，覆盖多个旧工具的功能。
优先走模板化 Cypher，模板不覆盖的情况才 fallback 到 text2cypher。

Author: Scholar Compass Team
Date: 2025-04-22
"""

import logging
import json
from typing import Optional, Any
from langchain_core.tools import tool

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _get_entity_set_class():
    """延迟导入 EntitySet"""
    from graph.schemas import EntitySet
    return EntitySet


def _get_try_match_template():
    """延迟导入 try_match_template"""
    from tools._new.query_templates import try_match_template
    return try_match_template


@tool
def factual_query(
    resolved_query: str,
    entities_json: str,
    query_shape: Optional[str] = None,
) -> str:
    """
    统一的事实查询工具，覆盖学者、论文、关系等多种事实查询。

    该工具优先走模板化 Cypher（快速、稳定），模板未命中时 fallback 到 text2cypher（灵活）。
    输入的 entities_json 来自路由层已解析的实体，工具不再需要自己做 NER。

    Args:
        resolved_query: 路由层消解后的完整查询
        entities_json: EntitySet 的 JSON 字符串（RoutingDecision.entities.model_dump_json()）
        query_shape: 查询形态 hint（single_lookup/comparison/aggregation/multi_hop）

    Returns:
        格式化后的查询结果字符串（人类可读）

    Examples:
        >>> # Top N papers（命中 author_top_papers 模板）
        >>> factual_query(
        ...     "查询 Yao Xie 的 top 5 高被引论文",
        ...     EntitySet(authors=[ResolvedAuthor(name="Yao Xie", author_id="...")]).model_dump_json()
        ... )

        >>> # Paper count（命中 author_paper_count 模板）
        >>> factual_query(
        ...     "Yao Xie 发过多少篇论文",
        ...     EntitySet(authors=[ResolvedAuthor(name="Yao Xie", author_id="...")]).model_dump_json()
        ... )

        >>> # 复杂查询（fallback 到 text2cypher）
        >>> factual_query(
        ...     "Yao Xie 的合作者里发文最多的三个人",
        ...     entities_json,
        ...     query_shape="multi_hop"
        ... )
    """
    logger.info(f"[factual_query] Query: {resolved_query[:100]}...")
    logger.info(f"[factual_query] Query shape: {query_shape}")

    # Step 1: 反序列化 entities
    try:
        EntitySet = _get_entity_set_class()
        entities = EntitySet.model_validate_json(entities_json)
    except Exception as e:
        logger.error(f"[factual_query] Failed to parse entities_json: {e}")
        # 解析失败，降级到纯 text2cypher
        EntitySet = _get_entity_set_class()
        return _fallback_to_text2cypher(resolved_query, EntitySet(), query_shape)

    # Step 2: 尝试匹配模板
    try_match_template = _get_try_match_template()
    template = try_match_template(resolved_query, entities, query_shape)

    if template is not None:
        # 命中模板
        template_name = template.get("output_hint", "unknown")
        logger.info(f"[factual_query] Template matched: {template_name}")

        # 特殊处理：重名作者对比不需要执行 Cypher
        if template_name == "duplicate_authors":
            return _format_duplicate_authors(template["candidates"])

        # 执行 Cypher
        cypher = template["cypher"]
        params = template["params"]
        output_hint = template["output_hint"]

        try:
            results = _execute_cypher(cypher, params)
            return _format_results(results, output_hint, resolved_query)
        except Exception as e:
            logger.error(f"[factual_query] Template execution failed: {e}")
            # 模板执行失败，fallback 到 text2cypher
            return _fallback_to_text2cypher(resolved_query, entities, query_shape)

    # Step 3: 模板未命中，fallback 到 text2cypher
    logger.info(f"[factual_query] No template match, falling back to text2cypher")
    return _fallback_to_text2cypher(resolved_query, entities, query_shape)


def _execute_cypher(cypher: str, params: dict) -> list:
    """执行 Cypher 查询"""
    logger.debug(f"[factual_query] Executing Cypher: {cypher[:200]}...")
    logger.debug(f"[factual_query] Params: {params}")
    from tools.neo4j_connector import neo4j_connector
    return neo4j_connector.execute_query(cypher, params)


def _format_results(results: list, output_hint: str, original_query: str) -> str:
    """
    格式化查询结果。

    Args:
        results: Cypher 查询结果
        output_hint: 输出类型提示
        original_query: 原始查询（用于上下文）
    """
    if not results:
        return "未找到相关信息。"

    if output_hint == "top_papers":
        return _format_top_papers(results)
    elif output_hint == "paper_count":
        return _format_paper_count(results)
    elif output_hint == "recent_papers":
        return _format_recent_papers(results)
    elif output_hint == "paper_details":
        return _format_paper_details(results)
    else:
        return _format_generic_results(results)


def _format_top_papers(results: list) -> str:
    """格式化 Top N 论文结果"""
    output = f"✅ 查询成功，共找到 {len(results)} 篇论文：\n\n"

    for i, row in enumerate(results, 1):
        title = row.get("title", "无标题")
        citations = row.get("citations", 0)
        year = row.get("year", "未知")
        output += f"{i}. 《{title}》\n"
        output += f"   - 被引次数: {citations}\n"
        output += f"   - 发表年份: {year}\n"
        output += "\n"

    return output


def _format_paper_count(results: list) -> str:
    """格式化论文数统计结果"""
    if not results:
        return "未找到论文信息。"

    row = results[0]
    paper_count = row.get("paper_count", 0)
    total_citations = row.get("total_citations", 0)
    max_citations = row.get("max_citations", 0)
    avg_fwci = row.get("avg_fwci", 0)

    output = "✅ 论文统计信息：\n\n"
    output += f"- 论文总数: {paper_count} 篇\n"
    output += f"- 累计被引: {total_citations} 次\n"
    output += f"- 单篇最高被引: {max_citations} 次\n"
    if avg_fwci:
        output += f"- 平均 FWCI: {avg_fwci:.2f}\n"

    return output


def _format_recent_papers(results: list) -> str:
    """格式化近期论文结果"""
    output = f"✅ 查询成功，共找到 {len(results)} 篇论文：\n\n"

    for i, row in enumerate(results, 1):
        title = row.get("title", "无标题")
        citations = row.get("citations", 0)
        year = row.get("year", "未知")
        output += f"{i}. 《{title}》({year}) - 被引 {citations} 次\n"

    return output


def _format_paper_details(results: list) -> str:
    """格式化论文详情结果"""
    if not results:
        return "未找到论文信息。"

    row = results[0]
    title = row.get("title", "无标题")
    citations = row.get("citations", 0)
    year = row.get("year", "未知")
    fwci = row.get("fwci", 0)
    authors = row.get("authors", [])

    output = "✅ 论文详情：\n\n"
    output += f"- 标题: 《{title}》\n"
    output += f"- 被引次数: {citations}\n"
    output += f"- 发表年份: {year}\n"
    if fwci:
        output += f"- FWCI: {fwci:.2f}\n"
    if authors:
        output += f"- 作者: {', '.join(authors)}\n"

    return output


def _format_duplicate_authors(candidates: list) -> str:
    """
    格式化重名作者对比结果（直接从 candidates 构造，不执行 Cypher）。
    """
    output = f"数据库中有 {len(candidates)} 位同名学者：\n\n"

    for i, c in enumerate(candidates, 1):
        output += f"{i}. 论文数: {c.paper_count}，累计被引: {c.total_citations} 次\n"
        if c.sample_titles:
            top_paper = c.sample_titles[0]
            output += f"   代表作:《{top_paper}》\n"
        output += "\n"

    return output


def _format_generic_results(results: list) -> str:
    """通用结果格式化"""
    output = f"✅ 查询成功，共 {len(results)} 条记录：\n\n"

    for i, row in enumerate(results[:10], 1):
        items = [f"{k}: {v}" for k, v in row.items() if v is not None]
        output += f"{i}. {', '.join(items)}\n"

    if len(results) > 10:
        output += f"\n... 还有 {len(results) - 10} 条记录未显示"

    return output


def _fallback_to_text2cypher(
    query: str,
    entities: Any,
    query_shape: Optional[str] = None,
) -> str:
    """
    Fallback 到 text2cypher（新的接口，接收 entities）。

    Args:
        query: 用户查询
        entities: 路由层解析的实体
        query_shape: 查询形态 hint
    """
    from tools.text2cypher import generate_cypher_with_entities
    from tools.neo4j_connector import neo4j_connector

    try:
        # 调用新的 text2cypher 入口（返回 cypher, params 元组）
        cypher, params = generate_cypher_with_entities(query, entities)

        # 执行生成的 Cypher（带参数）
        results = neo4j_connector.execute_query(cypher, params)

        # 格式化结果
        return _format_generic_results(results)

    except Exception as e:
        logger.error(f"[factual_query] text2cypher fallback failed: {e}")
        return f"查询失败：{str(e)}"
