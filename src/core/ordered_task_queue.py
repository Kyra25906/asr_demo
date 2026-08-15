"""按顺序、单线程、带背压的通用后台任务队列。

机制层：不认识任何业务类型，只负责把传入的 worker 函数在
一条后台工作线程上、按提交顺序、最多积压 N 个地执行。

- 单工作线程保证任务严格按提交顺序执行（FIFO）；
- 背压保证积压达到 max_pending_tasks 时，提交方等待最旧任务完成，
  队列不会无限增长；
- 单个任务的异常被捕获记录为 CompletedTask.error，不影响后续任务。

为什么不需要加锁：_pending 双端队列只由调用方（主线程）在
submit / collect_ready / finish 里修改；工作线程只执行 worker 并写入
Future。Future 本身是线程安全的，因此单属主队列无需锁。
"""

from __future__ import annotations

from collections import deque
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
)
from dataclasses import dataclass
from typing import (
    Callable,
    Generic,
    TypeVar,
)

In = TypeVar("In")
Out = TypeVar("Out")


@dataclass(frozen=True)
class CompletedTask(Generic[In, Out]):
    """一个后台任务的最终结果。

    result 非空表示成功，error 非空表示 worker 抛出异常；
    两者不能同时存在。item 始终原样返回，供调用方在失败时定位。
    """

    item: In
    result: Out | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.result is not None and self.error is not None:
            raise ValueError("成功结果与错误不能同时存在。")


@dataclass(frozen=True)
class _PendingTask(Generic[In, Out]):
    """一个已提交但结果尚未被消费的任务。"""

    item: In
    future: Future[Out]


class OrderedTaskQueue(Generic[In, Out]):
    """单工作线程 + FIFO + 背压的后台任务队列。"""

    def __init__(
        self,
        *,
        worker: Callable[[In], Out],
        max_pending_tasks: int = 4,
    ) -> None:
        if worker is None:
            raise ValueError("worker 不能为空。")
        if max_pending_tasks <= 0:
            raise ValueError("max_pending_tasks 必须大于 0。")

        self._worker = worker
        self._max_pending_tasks = max_pending_tasks
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="ordered-task",
        )
        self._pending: deque[_PendingTask[In, Out]] = deque()
        self._closed = False

    def submit(
        self,
        *,
        item: In,
    ) -> list[CompletedTask[In, Out]]:
        """提交一个任务，返回提交前已经完成的结果。

        若积压达到上限，会等待最旧任务完成后再提交（背压）。
        """

        if self._closed:
            raise RuntimeError("队列已经关闭。")

        completed = self.collect_ready()

        if len(self._pending) >= self._max_pending_tasks:
            completed.append(self._collect_oldest(wait=True))

        future = self._executor.submit(self._worker, item)
        self._pending.append(_PendingTask(item=item, future=future))

        return completed

    def collect_ready(
        self,
    ) -> list[CompletedTask[In, Out]]:
        """非阻塞地取出已经完成的任务。

        因为只有一个工作线程，任务一定按提交顺序完成，
        所以只需从队首开始检查。
        """

        completed: list[CompletedTask[In, Out]] = []

        while (
            self._pending
            and self._pending[0].future.done()
        ):
            completed.append(self._collect_oldest(wait=False))

        return completed

    def finish(
        self,
    ) -> list[CompletedTask[In, Out]]:
        """等待所有任务完成并关闭线程池。

        会话结束、空闲超时或程序退出时都必须调用。
        """

        if self._closed:
            return []

        completed = self.collect_ready()

        while self._pending:
            completed.append(self._collect_oldest(wait=True))

        self._executor.shutdown(wait=True)
        self._closed = True

        return completed

    def pending_count(
        self,
    ) -> int:
        """返回尚未消费结果的任务数量。"""

        return len(self._pending)

    def _collect_oldest(
        self,
        *,
        wait: bool,
    ) -> CompletedTask[In, Out]:
        """取出队首任务。

        wait=True 时允许阻塞；wait=False 时要求任务已经完成。
        """

        pending = self._pending[0]

        if (
            not wait
            and not pending.future.done()
        ):
            raise RuntimeError("任务尚未完成，不能非阻塞收集。")

        self._pending.popleft()

        try:
            result = pending.future.result()
        except Exception as error:
            return CompletedTask(
                item=pending.item,
                result=None,
                error=f"{type(error).__name__}: {error}",
            )

        return CompletedTask(
            item=pending.item,
            result=result,
            error=None,
        )

    def __enter__(self) -> "OrderedTaskQueue[In, Out]":
        return self

    def __exit__(
        self,
        exception_type,
        exception,
        traceback,
    ) -> None:
        self.finish()
