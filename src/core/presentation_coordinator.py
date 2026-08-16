"""呈现协调器：把一批呈现意图按规则整理成"本轮交付 + 延后"。

纯函数 `coordinate` 定义整理规则（FIFO、相邻去重、单问题限制）；
`PresentationCoordinator` 在其外包一层线程安全的投递队列，供后台线程投递、
presentation pump 取货。
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Iterable, Sequence

from src.core.presentation_intent import MessageKind, PresentationIntent


def coordinate(
    intents: Sequence[PresentationIntent],
) -> tuple[tuple[PresentationIntent, ...], tuple[PresentationIntent, ...]]:
    """按 FIFO + 相邻去重 + 单问题限制整理一批意图。

    返回 (deliver, deferred)：
    - deliver：本轮应交付的意图，保持投递顺序、相邻重复已合并、最多一个问题；
    - deferred：因单问题限制被压下的多余问题，由有状态层延后到下一轮。
    """

    merged = _merge_adjacent_duplicates(intents)
    return _split_single_question(merged)


def _merge_adjacent_duplicates(
    intents: Sequence[PresentationIntent],
) -> list[PresentationIntent]:
    """相邻的语义等价意图合并成一条（去重），非相邻的保留。"""

    result: list[PresentationIntent] = []
    for intent in intents:
        if result and _semantically_equal(result[-1], intent):
            continue
        result.append(intent)
    return result


def _split_single_question(
    intents: Sequence[PresentationIntent],
) -> tuple[tuple[PresentationIntent, ...], tuple[PresentationIntent, ...]]:
    """最多放出一个问题（CLARIFICATION），其余问题延后。

    有多个问题时，保留优先级最高（priority 数值最小）的那一个。
    """

    question_indices = [
        index
        for index, intent in enumerate(intents)
        if intent.kind == MessageKind.CLARIFICATION
    ]
    if len(question_indices) <= 1:
        return tuple(intents), ()

    chosen = min(question_indices, key=lambda i: intents[i].priority)

    deliver: list[PresentationIntent] = []
    deferred: list[PresentationIntent] = []
    for index, intent in enumerate(intents):
        if intent.kind == MessageKind.CLARIFICATION and index != chosen:
            deferred.append(intent)
        else:
            deliver.append(intent)
    return tuple(deliver), tuple(deferred)


def _semantically_equal(
    first: PresentationIntent,
    second: PresentationIntent,
) -> bool:
    """kind 相同且 args 相同，视为同一条语义（忽略 intent_id）。"""

    return first.kind == second.kind and first.args == second.args


class PresentationCoordinator:
    """线程安全的呈现消息队列：后台线程投递，pump 取货。

    只负责顺序整理与单问题限制，不做 supersede、持久化或规则引擎。
    """

    def __init__(self) -> None:
        self._pending: deque[PresentationIntent] = deque()
        self._condition = threading.Condition()
        self._unfinished_count = 0

    def submit(self, intents: Iterable[PresentationIntent]) -> None:
        """投递一批 Intent（多线程可并发调用）。"""

        batch = tuple(intents)
        with self._condition:
            self._pending.extend(batch)
            self._unfinished_count += len(batch)
            self._condition.notify_all()

    def drain(
        self,
        timeout: float | None = None,
    ) -> tuple[PresentationIntent, ...]:
        """阻塞取货，返回本轮交付组；超时返回空组。

        被单问题限制压下的多余问题放回队首，下一轮优先放行。
        """

        with self._condition:
            while not self._pending:
                self._condition.wait(timeout)
                if not self._pending:
                    return ()

            batch = tuple(self._pending)
            self._pending.clear()

            deliver, deferred = coordinate(batch)
            dropped_count = len(batch) - len(deliver) - len(deferred)
            self._unfinished_count -= dropped_count
            if deferred:
                self._pending.extendleft(reversed(deferred))
            if self._unfinished_count == 0:
                self._condition.notify_all()
            return deliver

    def mark_completed(self) -> None:
        """标记一条已取走意图的交付尝试完成。"""

        with self._condition:
            if self._unfinished_count <= 0:
                raise RuntimeError("没有可标记完成的呈现意图。")
            self._unfinished_count -= 1
            if self._unfinished_count == 0:
                self._condition.notify_all()

    def join(self, timeout: float | None = None) -> bool:
        """等待已投递意图全部完成或被语义去重。"""

        deadline = None if timeout is None else time.monotonic() + timeout
        with self._condition:
            while self._unfinished_count > 0:
                if deadline is None:
                    self._condition.wait()
                    continue
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._condition.wait(remaining)
            return True

    @property
    def pending_count(self) -> int:
        """当前待交付的消息数（测试/诊断用）。"""

        with self._condition:
            return len(self._pending)

    @property
    def unfinished_count(self) -> int:
        """尚未完成的意图数：包含 pending、deferred 和 in-flight。"""

        with self._condition:
            return self._unfinished_count
