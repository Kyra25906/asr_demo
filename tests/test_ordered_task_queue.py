"""OrderedTaskQueue 的机制测试。

只用整数/字符串等无业务含义的类型验证通用机制，不引入任何
ASR/LLM/segment 领域类型——以此证明队列不认识业务、可跨领域复用。

测试重点（对应机制三件套）：
1. 单工作线程 + FIFO：任务严格按提交顺序执行、按顺序返回；
2. 背压：积压达到上限时，提交会等待最旧任务完成；
3. 错误隔离：某个任务抛出异常，不影响后续任务，异常被记录为 error。
"""

import threading
import time
import unittest

from src.core.ordered_task_queue import (
    CompletedTask,
    OrderedTaskQueue,
)


class OrderedTaskQueueTest(unittest.TestCase):
    """用纯整数/字符串验证队列机制。"""

    def test_submit_and_finish_returns_results_in_fifo_order(self):
        # Arrange：worker 记录被调用的顺序，返回 item * 10
        calls = []
        lock = threading.Lock()

        def worker(item: int) -> int:
            with lock:
                calls.append(item)
            return item * 10

        queue = OrderedTaskQueue(worker=worker, max_pending_tasks=4)

        # Act：提交三段；累积 submit 返回的已完成结果，最后 finish 排空
        completed = []
        completed += queue.submit(item=1)
        completed += queue.submit(item=2)
        completed += queue.submit(item=3)
        completed += queue.finish()

        # Assert：输入顺序、执行顺序、结果顺序全部一致
        self.assertEqual([c.item for c in completed], [1, 2, 3])
        self.assertEqual([c.result for c in completed], [10, 20, 30])
        self.assertEqual(calls, [1, 2, 3])
        self.assertTrue(all(c.error is None for c in completed))

    def test_backpressure_blocks_submit_when_queue_full(self):
        # Arrange：worker 对 item=1 阻塞，等待放行信号
        first_started = threading.Event()
        allow_first = threading.Event()

        def worker(item: int) -> int:
            if item == 1:
                first_started.set()
                allow_first.wait(timeout=5)
            return item

        queue = OrderedTaskQueue(worker=worker, max_pending_tasks=1)

        # Act：提交 item=1 并确认它已在后台开始执行
        queue.submit(item=1)
        self.assertTrue(first_started.wait(timeout=5))

        # 此时积压=1 已达上限，item=2 的提交应阻塞，直到 item=1 完成。
        submitted = threading.Event()

        def submit_two() -> None:
            queue.submit(item=2)
            submitted.set()

        thread = threading.Thread(target=submit_two)
        thread.start()

        # Assert：放行前 submit(2) 未返回；放行后返回
        time.sleep(0.05)
        self.assertFalse(submitted.is_set(), "背压失效：队列满时提交未阻塞")
        allow_first.set()
        thread.join(timeout=5)
        self.assertTrue(submitted.is_set(), "背压解除后提交未返回")

        queue.finish()

    def test_collect_ready_is_non_blocking(self):
        # Arrange：worker 对 item=1 阻塞
        first_started = threading.Event()
        allow_first = threading.Event()

        def worker(item: int) -> int:
            if item == 1:
                first_started.set()
                allow_first.wait(timeout=5)
            return item

        queue = OrderedTaskQueue(worker=worker, max_pending_tasks=4)

        # Act：提交 item=1，未完成时 collect_ready 应立即返回空列表
        queue.submit(item=1)
        self.assertTrue(first_started.wait(timeout=5))

        start = time.monotonic()
        ready = queue.collect_ready()
        elapsed = time.monotonic() - start

        # Assert：未完成时返回空，且不阻塞等待
        self.assertEqual(ready, [])
        self.assertLess(elapsed, 0.05)

        # 放行后 collect_ready 能取到结果
        allow_first.set()
        deadline = time.monotonic() + 5
        while not queue.pending_count() == 0:
            time.sleep(0.01)
            if time.monotonic() > deadline:
                break
        ready = queue.collect_ready()
        self.assertEqual([c.item for c in ready], [1])
        self.assertEqual([c.result for c in ready], [1])
        queue.finish()

    def test_worker_error_is_captured_and_queue_continues(self):
        # Arrange：item=2 让 worker 抛异常，其余正常
        def worker(item: int) -> int:
            if item == 2:
                raise ValueError("boom")
            return item * 2

        queue = OrderedTaskQueue(worker=worker, max_pending_tasks=4)

        # Act
        completed = []
        completed += queue.submit(item=1)
        completed += queue.submit(item=2)
        completed += queue.submit(item=3)
        completed += queue.finish()

        # Assert：异常被记录为 error，后续 item=3 仍被处理
        self.assertEqual([c.item for c in completed], [1, 2, 3])
        self.assertEqual([c.result for c in completed], [2, None, 6])
        self.assertEqual(
            [c.error for c in completed],
            [None, "ValueError: boom", None],
        )

    def test_submit_after_finish_raises(self):
        queue = OrderedTaskQueue(worker=lambda item: item, max_pending_tasks=4)
        queue.finish()

        with self.assertRaises(RuntimeError):
            queue.submit(item=1)

    def test_max_pending_tasks_must_be_positive(self):
        with self.assertRaises(ValueError):
            OrderedTaskQueue(worker=lambda item: item, max_pending_tasks=0)

    def test_worker_must_not_be_none(self):
        with self.assertRaises(ValueError):
            OrderedTaskQueue(worker=None, max_pending_tasks=4)

    def test_completed_task_rejects_result_and_error_together(self):
        # Arrange & Act & Assert：合同不允许"既成功又失败"
        with self.assertRaises(ValueError):
            CompletedTask(item=1, result=2, error="oops")


if __name__ == "__main__":
    unittest.main()
