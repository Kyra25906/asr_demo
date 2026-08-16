"""会话等待状态的呈现节流规则。"""

from enum import IntEnum


class _IdleNoticeStage(IntEnum):
    WAITING = 0
    ONE_MINUTE = 1
    THIRTY_SECONDS = 2


class IdleNoticeTracker:
    """只在无口述等待阶段发生变化时返回一条用户提示。"""

    def __init__(self) -> None:
        self._last_stage: _IdleNoticeStage | None = None

    def reset(self) -> None:
        """检测到新口述后回到活跃态；下次等待可重新提示。"""

        self._last_stage = None

    def message_for_timeout(self, remaining_seconds: float) -> str | None:
        """返回新阶段文案；同一或更早阶段重复到达时返回 None。"""

        if remaining_seconds <= 0:
            return None

        stage = self._stage_for(remaining_seconds)
        if self._last_stage is not None and stage <= self._last_stage:
            return None

        self._last_stage = stage
        if stage == _IdleNoticeStage.WAITING:
            return "暂时没有检测到口述，实验会话继续等待。"
        if stage == _IdleNoticeStage.ONE_MINUTE:
            return "仍未检测到口述，距离自动结束约还有 60 秒。"
        return "仍未检测到口述，距离自动结束约还有 30 秒。"

    @staticmethod
    def _stage_for(remaining_seconds: float) -> _IdleNoticeStage:
        if remaining_seconds > 60:
            return _IdleNoticeStage.WAITING
        if remaining_seconds > 30:
            return _IdleNoticeStage.ONE_MINUTE
        return _IdleNoticeStage.THIRTY_SECONDS
