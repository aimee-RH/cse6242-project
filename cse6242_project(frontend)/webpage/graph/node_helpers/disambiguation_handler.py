"""
Disambiguation Response Handler

处理用户对澄清问题的响应（如选择编号"1"、"第二个"等），
并维护 session 内的实体持久化。

Author: Scholar Compass Team
Date: 2025-04-22
"""

import re
import logging
from typing import Optional, TYPE_CHECKING

logger = logging.getLogger(__name__)

# 延迟导入避免循环引用
if TYPE_CHECKING:
    from graph.schemas import PendingClarification, AuthorCandidate, ResolvedAuthor


# 数字选择的正则模式（支持中英文）
NUMBER_PATTERNS = [
    r"^\s*(\d+)\s*$",                                    # "1", "2"
    r"^\s*第\s*([一二三四五六七八九十\d]+)\s*[个位]?\s*$",  # "第一个", "第2位"
    r"^\s*(first|second|third|1st|2nd|3rd)\s*$",         # 英文序数
    r"^\s*选\s*(\d+)\s*$",                                # "选1"
    r"^\s*([一二三四五六七八九十])\s*$",                     # "一", "二"
]

CN_NUM_MAP = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10
}
EN_NUM_MAP = {
    "first": 1, "second": 2, "third": 3,
    "1st": 1, "2nd": 2, "3rd": 3
}


def detect_disambiguation_response(
    user_query: str,
    pending: Optional["PendingClarification"]
) -> Optional[int]:
    """
    检测用户输入是否是对上一轮 clarification 的编号选择。

    Args:
        user_query: 用户当前输入
        pending: 上一轮挂起的候选

    Returns:
        - int: 用户选择的候选编号（1-based）
        - None: 不是消歧响应，或没有待澄清项，或编号越界
    """
    if pending is None or not pending.candidates:
        return None

    query = user_query.strip().lower()
    max_num = len(pending.candidates)

    for pattern in NUMBER_PATTERNS:
        match = re.match(pattern, query, re.IGNORECASE)
        if not match:
            continue

        token = match.group(1)

        # 解析数字
        if token.isdigit():
            num = int(token)
        elif token in CN_NUM_MAP:
            num = CN_NUM_MAP[token]
        elif token in EN_NUM_MAP:
            num = EN_NUM_MAP[token]
        else:
            continue

        if 1 <= num <= max_num:
            logger.info(f"[disambiguation] Detected selection: #{num} of {max_num}")
            return num
        else:
            # 编号越界
            logger.info(f"[disambiguation] Selection out of range: {num} > {max_num}")
            return None

    return None


def resolve_from_disambiguation(
    selected_num: int,
    pending: "PendingClarification"
) -> "ResolvedAuthor":
    """
    根据用户选择的编号，构造 ResolvedAuthor。

    Args:
        selected_num: 用户选择的编号（1-based）
        pending: 待澄清的候选列表

    Returns:
        ResolvedAuthor: 已消歧的作者信息
    """
    from graph.schemas import ResolvedAuthor

    candidate = pending.candidates[selected_num - 1]

    return ResolvedAuthor(
        name=candidate.name,
        author_id=candidate.author_id,
        confidence=1.0,  # 用户明确选择，置信度 100%
        candidates=[],   # 已消歧，清空候选
        original_expression=f"用户选择候选 #{selected_num}",
    )


def find_paper_count_in_candidate(pending: "PendingClarification", idx: int) -> int:
    """从 pending 中取第 idx 个候选的 paper_count"""
    if 0 <= idx < len(pending.candidates):
        return pending.candidates[idx].paper_count
    return 0
