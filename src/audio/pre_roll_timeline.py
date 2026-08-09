"""为句首预缓冲补充录音会话内的绝对采样位置。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.audio.pre_roll_buffer import PreRollBuffer


@dataclass(frozen=True)
class PreRollSnapshot:
    """某一时刻的预缓冲内容及其半开采样区间 ``[start, end)``。"""

    samples: np.ndarray
    start_sample: int
    end_sample: int

    def __post_init__(self) -> None:
        if self.samples.ndim != 1:
            raise ValueError("samples 必须是一维单声道数组。")
        if self.samples.dtype != np.float32:
            raise TypeError("samples 必须是 float32 数组。")
        if self.start_sample < 0:
            raise ValueError("start_sample 不能小于 0。")
        if self.end_sample < self.start_sample:
            raise ValueError("end_sample 不能早于 start_sample。")
        if self.end_sample - self.start_sample != self.samples.size:
            raise ValueError("采样区间长度必须与 samples 长度一致。")


class PreRollTimelineBuffer:
    """在固定容量缓冲器外记录本次录音已接收的采样总数。"""

    def __init__(self, capacity_samples: int) -> None:
        self._buffer = PreRollBuffer(capacity_samples=capacity_samples)
        self._total_samples = 0

    @classmethod
    def from_seconds(
        cls,
        *,
        duration_seconds: float,
        sample_rate: int,
    ) -> PreRollTimelineBuffer:
        buffer = PreRollBuffer.from_seconds(
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
        )
        return cls(capacity_samples=buffer.capacity_samples)

    @property
    def capacity_samples(self) -> int:
        return self._buffer.capacity_samples

    @property
    def total_samples(self) -> int:
        return self._total_samples

    def append(self, samples: np.ndarray) -> None:
        """追加采样；只有底层校验成功后才推进时间线。"""

        array = np.asarray(samples)
        self._buffer.append(array)
        self._total_samples += array.size

    def snapshot(self) -> PreRollSnapshot:
        """返回当前内容及其在本次录音输入中的绝对采样区间。"""

        samples = self._buffer.snapshot()
        end_sample = self._total_samples
        start_sample = end_sample - samples.size
        return PreRollSnapshot(
            samples=samples,
            start_sample=start_sample,
            end_sample=end_sample,
        )

    def clear(self) -> None:
        """清除音频并把下一次录音的时间线重新从0开始。"""

        self._buffer.clear()
        self._total_samples = 0
