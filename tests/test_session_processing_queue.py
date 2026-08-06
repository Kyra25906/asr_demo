import threading
import unittest

from src.asr.schemas import (
    ASRResult,
)
from src.core.session_context import (
    SessionContext,
)
from src.core.session_processing_queue import (
    SessionProcessingQueue,
)
from src.llm.processor import (
    ProcessOutcome,
)
from src.llm.schemas import (
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)


def make_asr_result(
    segment_id: int,
) -> ASRResult:
    """
    创建一条不依赖真实 FunASR 的测试结果。
    """

    text = f"第{segment_id}段口述。"

    return ASRResult(
        text=text,
        raw_text=text,
        audio_path=(
            f"segment_{segment_id}.wav"
        ),
        audio_duration_seconds=1.0,
        recognition_seconds=0.1,
        model="fake-asr",
        language="zh",
    )


def make_outcome(
    *,
    session_id: str,
    segment_id: int,
    raw_text: str,
) -> ProcessOutcome[
    LLMAnalysisResult
]:
    """
    创建一份正常的结构化结果。
    """

    event = ExperimentEvent(
        event_type=(
            ExperimentEventType.OPERATION
        ),
        raw_text=raw_text,
        normalized_text=raw_text,
        source_session_id=session_id,
        source_segment_id=segment_id,
    )

    result = LLMAnalysisResult(
        events=[event],
        should_ask_follow_up=False,
        follow_up_question=None,
        assistant_reply="已记录。",
    )

    return ProcessOutcome(
        value=result,
        degraded=False,
        error=None,
    )


class FakeSegmentProcessor:
    """
    可控制执行过程的假处理器。

    gate:
        如果传入 Event，后台任务会等待
        gate.set() 后才继续。

    started:
        后台任务真正开始执行时设置，
        方便测试确认工作线程已经启动。

    raise_on_segment:
        指定某段主动抛出异常。
    """

    def __init__(
        self,
        *,
        gate: threading.Event | None = None,
        started: threading.Event | None = None,
        raise_on_segment: int | None = None,
    ) -> None:
        self.gate = gate
        self.started = started
        self.raise_on_segment = (
            raise_on_segment
        )

        self.calls: list[int] = []
        self.received_contexts = []

    def process(
        self,
        *,
        asr_result,
        session_id,
        segment_id,
        context,
    ):
        self.calls.append(
            segment_id
        )

        self.received_contexts.append(
            context
        )

        if self.started is not None:
            self.started.set()

        if self.gate is not None:
            released = self.gate.wait(
                timeout=5.0
            )

            if not released:
                raise TimeoutError(
                    "测试等待 gate 超时。"
                )

        if (
            segment_id
            == self.raise_on_segment
        ):
            raise OSError(
                "模拟后台处理失败"
            )

        return make_outcome(
            session_id=session_id,
            segment_id=segment_id,
            raw_text=asr_result.text,
        )


class SessionProcessingQueueTests(
    unittest.TestCase
):
    def test_submit_returns_before_task_finishes(
        self,
    ):
        """
        submit 不应等待后台任务完成。

        后台任务被 gate 阻塞时，
        submit 仍应立即返回。
        """

        gate = threading.Event()
        started = threading.Event()

        fake_processor = (
            FakeSegmentProcessor(
                gate=gate,
                started=started,
            )
        )

        queue = SessionProcessingQueue(
            segment_processor=(
                fake_processor
            ),
            context=SessionContext(
                max_events=8
            ),
            max_pending_tasks=4,
        )

        try:
            completed = queue.submit(
                asr_result=(
                    make_asr_result(1)
                ),
                session_id="session_001",
                segment_id=1,
            )

            # submit 已经返回，
            # 但任务仍被 gate 阻塞。
            self.assertEqual(
                completed,
                [],
            )

            self.assertTrue(
                started.wait(
                    timeout=1.0
                )
            )

            self.assertFalse(
                gate.is_set()
            )

            self.assertEqual(
                queue.pending_count(),
                1,
            )

        finally:
            # 无论测试是否成功，
            # 都必须释放工作线程。
            gate.set()
            queue.finish()

    def test_collect_ready_does_not_wait_for_running_task(
        self,
    ):
        """
        collect_ready 是非阻塞方法。

        任务未完成时应立即返回空列表。
        """

        gate = threading.Event()
        started = threading.Event()

        queue = SessionProcessingQueue(
            segment_processor=(
                FakeSegmentProcessor(
                    gate=gate,
                    started=started,
                )
            ),
            context=SessionContext(
                max_events=8
            ),
        )

        try:
            queue.submit(
                asr_result=(
                    make_asr_result(1)
                ),
                session_id="session_001",
                segment_id=1,
            )

            self.assertTrue(
                started.wait(
                    timeout=1.0
                )
            )

            completed = (
                queue.collect_ready()
            )

            self.assertEqual(
                completed,
                [],
            )

            self.assertEqual(
                queue.pending_count(),
                1,
            )

        finally:
            gate.set()
            queue.finish()

    def test_tasks_run_in_submission_order(
        self,
    ):
        """
        即使快速提交多段任务，
        单工作线程仍应按 1、2、3 执行。
        """

        fake_processor = (
            FakeSegmentProcessor()
        )

        queue = SessionProcessingQueue(
            segment_processor=(
                fake_processor
            ),
            context=SessionContext(
                max_events=8
            ),
            max_pending_tasks=4,
        )

        completed = []

        for segment_id in (
            1,
            2,
            3,
        ):
            completed.extend(
                queue.submit(
                    asr_result=(
                        make_asr_result(
                            segment_id
                        )
                    ),
                    session_id=(
                        "session_001"
                    ),
                    segment_id=(
                        segment_id
                    ),
                )
            )

        completed.extend(
            queue.finish()
        )

        self.assertEqual(
            fake_processor.calls,
            [1, 2, 3],
        )

        self.assertEqual(
            [
                item.segment_id
                for item in completed
            ],
            [1, 2, 3],
        )

        self.assertTrue(
            all(
                item.error is None
                for item in completed
            )
        )

        self.assertTrue(
            all(
                item.outcome is not None
                for item in completed
            )
        )

    def test_background_exception_becomes_completed_error(
        self,
    ):
        """
        后台异常不能直接冲垮主线程。

        它应被转换成 CompletedSegment.error。
        """

        fake_processor = (
            FakeSegmentProcessor(
                raise_on_segment=2
            )
        )

        queue = SessionProcessingQueue(
            segment_processor=(
                fake_processor
            ),
            context=SessionContext(
                max_events=8
            ),
        )

        completed = []

        for segment_id in (
            1,
            2,
            3,
        ):
            completed.extend(
                queue.submit(
                    asr_result=(
                        make_asr_result(
                            segment_id
                        )
                    ),
                    session_id=(
                        "session_002"
                    ),
                    segment_id=(
                        segment_id
                    ),
                )
            )

        completed.extend(
            queue.finish()
        )

        self.assertEqual(
            [
                item.segment_id
                for item in completed
            ],
            [1, 2, 3],
        )

        first = completed[0]
        second = completed[1]
        third = completed[2]

        self.assertIsNone(
            first.error
        )
        self.assertIsNotNone(
            first.outcome
        )

        self.assertIsNone(
            second.outcome
        )
        self.assertIsNotNone(
            second.error
        )
        self.assertIn(
            "OSError",
            second.error,
        )
        self.assertIn(
            "模拟后台处理失败",
            second.error,
        )

        self.assertIsNone(
            third.error
        )
        self.assertIsNotNone(
            third.outcome
        )

    def test_finish_waits_for_all_tasks(
        self,
    ):
        """
        submit 可能顺便返回已经完成的旧任务。

        因此需要收集：
        - 每次 submit 返回的结果；
        - finish 返回的剩余结果。
        """

        queue = SessionProcessingQueue(
            segment_processor=(
                FakeSegmentProcessor()
            ),
            context=SessionContext(
                max_events=8
            ),
        )

        all_completed = []

        for segment_id in range(
            1,
            5,
        ):
            completed_during_submit = (
                queue.submit(
                    asr_result=(
                        make_asr_result(
                            segment_id
                        )
                    ),
                    session_id=(
                        "session_003"
                    ),
                    segment_id=(
                        segment_id
                    ),
                )
            )

            all_completed.extend(
                completed_during_submit
            )

        remaining = queue.finish()

        all_completed.extend(
            remaining
        )

        self.assertEqual(
            [
                item.segment_id
                for item in all_completed
            ],
            [1, 2, 3, 4],
        )

        self.assertEqual(
            queue.pending_count(),
            0,
        )
    def test_submit_after_finish_is_rejected(
        self,
    ):
        """
        已关闭的队列不能继续接收任务。
        """

        queue = SessionProcessingQueue(
            segment_processor=(
                FakeSegmentProcessor()
            ),
            context=SessionContext(
                max_events=8
            ),
        )

        queue.finish()

        with self.assertRaises(
            RuntimeError
        ):
            queue.submit(
                asr_result=(
                    make_asr_result(1)
                ),
                session_id=(
                    "session_004"
                ),
                segment_id=1,
            )

    def test_backpressure_waits_when_queue_is_full(
        self,
    ):
        """
        max_pending_tasks=1 时：

        第一段未完成前提交第二段，
        第二次 submit 应等待第一段完成。
        """

        gate = threading.Event()
        started = threading.Event()

        queue = SessionProcessingQueue(
            segment_processor=(
                FakeSegmentProcessor(
                    gate=gate,
                    started=started,
                )
            ),
            context=SessionContext(
                max_events=8
            ),
            max_pending_tasks=1,
        )

        queue.submit(
            asr_result=(
                make_asr_result(1)
            ),
            session_id="session_005",
            segment_id=1,
        )

        self.assertTrue(
            started.wait(
                timeout=1.0
            )
        )

        second_submit_finished = (
            threading.Event()
        )

        second_submit_results = []
        second_submit_errors = []

        def submit_second():
            try:
                results = queue.submit(
                    asr_result=(
                        make_asr_result(2)
                    ),
                    session_id=(
                        "session_005"
                    ),
                    segment_id=2,
                )

                second_submit_results.extend(
                    results
                )

            except Exception as error:
                second_submit_errors.append(
                    error
                )

            finally:
                second_submit_finished.set()

        submit_thread = threading.Thread(
            target=submit_second,
            name="test-submit-second",
        )

        submit_thread.start()

        try:
            # 第一段尚未释放，
            # 第二次提交不应完成。
            self.assertFalse(
                second_submit_finished.wait(
                    timeout=0.2
                )
            )

            # 释放第一段。
            gate.set()

            self.assertTrue(
                second_submit_finished.wait(
                    timeout=2.0
                )
            )

            submit_thread.join(
                timeout=1.0
            )

            self.assertFalse(
                submit_thread.is_alive()
            )

            self.assertEqual(
                second_submit_errors,
                [],
            )

            # 第二次 submit 为了腾出容量，
            # 收集了第一段的完成结果。
            self.assertEqual(
                [
                    item.segment_id
                    for item
                    in second_submit_results
                ],
                [1],
            )

        finally:
            gate.set()

            if submit_thread.is_alive():
                submit_thread.join(
                    timeout=1.0
                )

            queue.finish()


if __name__ == "__main__":
    unittest.main()