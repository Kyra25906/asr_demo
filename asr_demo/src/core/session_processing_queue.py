from collections import deque
from concurrent.futures import (
    Future,
    ThreadPoolExecutor,
)
from dataclasses import dataclass

from src.asr.schemas import (
    ASRResult,
)
from src.core.segment_processor import (
    SegmentProcessor,
)
from src.core.session_context import (
    SessionContext,
)
from src.llm.processor import (
    ProcessOutcome,
)
from src.llm.schemas import (
    LLMAnalysisResult,
)


@dataclass(frozen=True)
class CompletedSegment:
    """
    一个后台任务的最终结果。

    outcome 非空表示处理成功，
    error 非空表示后台任务抛出异常。
    """

    segment_id: int
    asr_result: ASRResult
    outcome: (
        ProcessOutcome[
            LLMAnalysisResult
        ]
        | None
    )
    error: str | None = None
    target_clarification_id: str | None = None
    confirms_target_suggestion: bool = False


@dataclass(frozen=True)
class PendingSegment:
    """
    一个已经提交但尚未消费结果的任务。
    """

    segment_id: int
    asr_result: ASRResult
    future: Future
    target_clarification_id: str | None = None
    confirms_target_suggestion: bool = False


class SessionProcessingQueue:
    """
    当前实验会话的后台处理队列。

    使用单工作线程保证：
    - ASR 记录按顺序保存；
    - LLM 请求按顺序执行；
    - 实验事件按顺序保存；
    - SessionContext 只由一个线程修改。
    """

    def __init__(
        self,
        *,
        segment_processor: SegmentProcessor,
        context: SessionContext,
        max_pending_tasks: int = 4,
    ) -> None:
        if max_pending_tasks <= 0:
            raise ValueError(
                "max_pending_tasks "
                "必须大于 0。"
            )

        self.segment_processor = (
            segment_processor
        )
        self.context = context
        self.max_pending_tasks = (
            max_pending_tasks
        )

        self._executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix=(
                    "experiment-llm"
                ),
            )
        )

        self._pending: deque[
            PendingSegment
        ] = deque()

        self._closed = False

    def submit(
        self,
        *,
        asr_result: ASRResult,
        session_id: str,
        segment_id: int,
        target_clarification_id: str | None = None,
        confirms_target_suggestion: bool = False,
    ) -> list[CompletedSegment]:
        """
        提交一段后台处理任务。

        返回提交前已经完成的结果。

        如果积压任务达到上限，
        会等待最旧任务完成后再提交，
        形成背压，避免队列无限增长。
        """

        if self._closed:
            raise RuntimeError(
                "后台处理队列已经关闭。"
            )

        completed = (
            self.collect_ready()
        )

        if (
            len(self._pending)
            >= self.max_pending_tasks
        ):
            completed.append(
                self._collect_oldest(
                    wait=True
                )
            )

        future = self._executor.submit(
            self.segment_processor.process,
            asr_result=asr_result,
            session_id=session_id,
            segment_id=segment_id,
            context=self.context,
        )

        self._pending.append(
            PendingSegment(
                segment_id=segment_id,
                asr_result=asr_result,
                future=future,
                target_clarification_id=target_clarification_id,
                confirms_target_suggestion=confirms_target_suggestion,
            )
        )

        return completed

    def collect_ready(
        self,
    ) -> list[CompletedSegment]:
        """
        非阻塞地取出已经完成的任务。

        因为只有一个工作线程，
        任务一定按提交顺序完成。
        只需从队首开始检查。
        """

        completed = []

        while (
            self._pending
            and self._pending[
                0
            ].future.done()
        ):
            completed.append(
                self._collect_oldest(
                    wait=False
                )
            )

        return completed

    def finish(
        self,
    ) -> list[CompletedSegment]:
        """
        等待所有任务完成并关闭线程池。

        会话结束、空闲超时或程序退出时
        都必须调用。
        """

        if self._closed:
            return []

        completed = (
            self.collect_ready()
        )

        while self._pending:
            completed.append(
                self._collect_oldest(
                    wait=True
                )
            )

        self._executor.shutdown(
            wait=True
        )

        self._closed = True

        return completed

    def pending_count(
        self,
    ) -> int:
        """
        返回尚未消费结果的任务数量。
        """

        return len(self._pending)

    def _collect_oldest(
        self,
        *,
        wait: bool,
    ) -> CompletedSegment:
        """
        取出队首任务。

        wait=True 时允许阻塞；
        wait=False 时要求任务已经完成。
        """

        pending = self._pending[0]

        if (
            not wait
            and not pending.future.done()
        ):
            raise RuntimeError(
                "任务尚未完成，"
                "不能进行非阻塞收集。"
            )

        self._pending.popleft()

        try:
            outcome = (
                pending.future.result()
            )

            return CompletedSegment(
                segment_id=(
                    pending.segment_id
                ),
                asr_result=(
                    pending.asr_result
                ),
                outcome=outcome,
                error=None,
                target_clarification_id=(
                    pending.target_clarification_id
                ),
                confirms_target_suggestion=(
                    pending.confirms_target_suggestion
                ),
            )

        except Exception as error:
            return CompletedSegment(
                segment_id=(
                    pending.segment_id
                ),
                asr_result=(
                    pending.asr_result
                ),
                outcome=None,
                error=(
                    f"{type(error).__name__}: "
                    f"{error}"
                ),
                target_clarification_id=(
                    pending.target_clarification_id
                ),
                confirms_target_suggestion=(
                    pending.confirms_target_suggestion
                ),
            )

    def __enter__(
        self,
    ) -> "SessionProcessingQueue":
        return self

    def __exit__(
        self,
        exception_type,
        exception,
        traceback,
    ) -> None:
        self.finish()
