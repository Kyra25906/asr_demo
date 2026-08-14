"""无编号回答的确定性兜底。

纯函数层：不依赖 LLM、不做任何 I/O，只根据
"待确认问题数量 + 文本是否提供问题缺失字段"做确定性判断。
用途：统一链把短事实句判为弃权(abstention)时，兜底决定它是否
其实是对"唯一待确认问题"的回答；任何不满足条件的输入
（多问题/无问题/字段不匹配/实验记录）一律返回非回答，
绝不把实验记录路由成回答。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from src.core.pending_clarification import PendingClarification

# 演示实验的核心实体字段的确定性提取模式。
# 只覆盖本项目 demo 会用到的字段；不试图做通用 NLP。
_FIELD_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("temperature", re.compile(r"\d+(?:\.\d+)?\s*(?:摄氏度|℃|°C|度)")),
    ("duration", re.compile(r"\d+(?:\.\d+)?\s*(?:分钟|小时|秒|min|h)")),
    ("amount_value", re.compile(r"\d+(?:\.\d+)?\s*(?:毫升|微升|升|μl|ul|ml|l)")),
    ("amount_unit", re.compile(r"(?:毫升|微升|升|μl|ul|ml|l)")),
    ("concentration", re.compile(r"\d+(?:\.\d+)?\s*(?:mol/l|mmol/l|摩尔每升)")),
)

# "短句"的操作化边界：超过该长度视为复合句（可能是实验操作），不兜底。
_MAX_ANSWER_TEXT_LENGTH = 20


@dataclass(frozen=True)
class UnnumberedAnswerDecision:
    """兜底判断结果；字段为空时表示不作为回答。"""

    is_answer: bool
    fields: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.is_answer and self.fields:
            raise ValueError("非回答判定不能携带字段。")


def extract_entity_fields(text: str) -> tuple[str, ...]:
    """从文本中确定性提取命中的实体字段名（只判存在，不做值归一化）。"""

    if not isinstance(text, str) or not text.strip():
        return ()

    found: list[str] = []
    for field_name, pattern in _FIELD_PATTERNS:
        if pattern.search(text) and field_name not in found:
            found.append(field_name)
    return tuple(found)


def decide_unnumbered_answer(
    *,
    pending_questions: Sequence["PendingClarification"],
    text: str,
) -> UnnumberedAnswerDecision:
    """判定一段无编号文本是否是对唯一待确认问题的回答。

    规则（全部满足才算回答）：
    1. 恰好一个待确认问题（多个或零个都不猜）；
    2. 文本是短句（长度上限），避免冗长陈述；
    3. 文本提供了该问题缺失字段中的至少一个；
    4. 文本提供的所有字段都属于该问题缺失字段
       （夹带无关字段 = 新实验事实，如"加入5毫升缓冲液，加热到60摄氏度"）。

    不满足任何一条 → 非回答（保持原分类）。这保证了
    "加入5毫升缓冲液"这类实验记录（字段不匹配）绝不会被当作回答。
    """

    if len(pending_questions) != 1:
        return UnnumberedAnswerDecision(is_answer=False)

    if not isinstance(text, str) or not text.strip():
        return UnnumberedAnswerDecision(is_answer=False)
    if len(text) > _MAX_ANSWER_TEXT_LENGTH:
        return UnnumberedAnswerDecision(is_answer=False)

    extracted = extract_entity_fields(text)
    if not extracted:
        return UnnumberedAnswerDecision(is_answer=False)

    question = pending_questions[0]
    missing = set(question.missing_fields)
    # 答案只能提供问题缺的字段：夹带无关字段（体积/浓度等）视为实验陈述。
    if not set(extracted).issubset(missing):
        return UnnumberedAnswerDecision(is_answer=False)
    matched = tuple(
        field_name
        for field_name in question.missing_fields
        if field_name in extracted
    )
    if not matched:
        return UnnumberedAnswerDecision(is_answer=False)

    return UnnumberedAnswerDecision(is_answer=True, fields=matched)
