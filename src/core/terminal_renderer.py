"""终端渲染器：把呈现意图渲染成终端文本。"""

from src.core.presentation_copy import copy_for_intent
from src.core.presentation_intent import PresentationIntent


class TerminalRenderer:
    """把 PresentationIntent 渲染成终端文本；封装 ui_mode，是唯一转换点。

    调用方（未来的 presentation pump）只依赖本类，不直接依赖文案目录，
    也不需要知道 ui_mode。未来 Web renderer 与 TTS 消费同一契约。
    """

    def __init__(self, ui_mode: str) -> None:
        if ui_mode not in {"user", "admin"}:
            raise ValueError("ui_mode 必须是 user 或 admin。")
        self._ui_mode = ui_mode

    @property
    def ui_mode(self) -> str:
        """本渲染器的受众模式（user 或 admin）。"""

        return self._ui_mode

    def render(self, intent: PresentationIntent) -> str:
        """渲染一条意图为终端文本（可能多行，如查看列表）。"""

        return copy_for_intent(intent, ui_mode=self._ui_mode)
