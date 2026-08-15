"""呈现泵：唯一拥有 stdout 写入权的执行流。

后台业务线程只把 Intent 投递给 PresentationCoordinator，本泵从 Coordinator
取货、交给 Renderer 渲染、再写入输出。Renderer 以协议约定（只要会
`render(intent) -> str` 就算满足），pump 不绑定 TerminalRenderer 具体类。
"""

from __future__ import annotations

import threading
from typing import Callable, Protocol

from src.core.presentation_coordinator import PresentationCoordinator
from src.core.presentation_intent import PresentationIntent


class Renderer(Protocol):
    """pump 依赖的渲染契约；TerminalRenderer 与未来 Web/TTS 渲染器都满足它。"""

    def render(self, intent: PresentationIntent) -> str: ...


class PresentationPump:
    """循环取货 → 渲染 → 输出的消费者线程；唯一写 stdout 的地方。"""

    def __init__(
        self,
        coordinator: PresentationCoordinator,
        renderer: Renderer,
        output: Callable[[str], None] = print,
    ) -> None:
        self._coordinator = coordinator
        self._renderer = renderer
        self._output = output
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """启动泵线程（守护线程，不阻塞主进程退出）。"""

        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="presentation-pump",
        )
        self._thread.start()

    def stop(self, timeout: float | None = None) -> None:
        """请求停止并等待线程退出；已投递但未渲染的消息仍留在队列。"""

        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout)

    def _run(self) -> None:
        while not self._stop.is_set():
            intents = self._coordinator.drain(timeout=0.1)
            if not intents:
                continue
            for intent in intents:
                self._output(self._renderer.render(intent))
