"""指数退避计算：外部资源（如唤醒词检测）连续失败时的等待策略。

把退避逻辑抽成纯函数，方便脱离主流程做单元测试，
也避免在 main.py 里内联一段不可测的时间策略。
"""


def next_backoff_delay(
    attempt: int,
    base_seconds: float = 1.0,
    cap_seconds: float = 10.0,
) -> float:
    """返回第 attempt 次连续失败后应等待的秒数。

    参数：
        attempt: 连续失败次数，从 1 开始（第一次失败后等待 base）。
        base_seconds: 首次等待基数，必须大于 0。
        cap_seconds: 等待上限，必须不小于 base。

    规则：
        delay = min(base * 2 ** (attempt - 1), cap)

    失败次数回退或成功后会由调用方把 attempt 重置为 0，
    因此本函数只负责按当前次数算延迟，不维护任何状态。
    """

    if attempt < 1:
        raise ValueError("attempt 必须从 1 开始。")
    if base_seconds <= 0:
        raise ValueError("base_seconds 必须大于 0。")
    if cap_seconds < base_seconds:
        raise ValueError("cap_seconds 不能小于 base_seconds。")

    delay = base_seconds * (2 ** (attempt - 1))
    return min(delay, cap_seconds)
