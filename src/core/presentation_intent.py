"""呈现意图合同：描述系统想表达什么，不包含最终展示文案。"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from src.core.presentation_message import (
    MessageKind,
    MessagePriority,
    ScreenTarget,
)


@dataclass(frozen=True)
class PresentationIntent:
    """交给呈现层的不可变语义意图。"""

    intent_id: str
    kind: MessageKind
    args: Mapping[str, object]
    priority: MessagePriority
    screen_target: ScreenTarget
    source_segment_id: int | None = None
    clarification_id: str | None = None

    def __post_init__(self) -> None:
        if not self.intent_id.strip():
            raise ValueError("intent_id 不能为空。")
        if self.kind == MessageKind.DEBUG:
            raise ValueError("DEBUG 信息必须走 logging，不能成为呈现意图。")
        if self.source_segment_id is not None and self.source_segment_id <= 0:
            raise ValueError("source_segment_id 必须大于 0。")

        copied_args = dict(self.args)
        if any(not isinstance(key, str) or not key.strip() for key in copied_args):
            raise ValueError("args 的键必须是非空字符串。")

        object.__setattr__(
            self,
            "args",
            MappingProxyType(copied_args),
        )
