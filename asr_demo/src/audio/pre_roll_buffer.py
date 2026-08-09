"""保留语音触发前最近一段单声道音频采样。"""

from __future__ import annotations

from collections import deque

import numpy as np


class PreRollBuffer:
    """固定容量、先进先出的单声道float32采样缓冲器。"""

    def __init__(self, capacity_samples: int) -> None:
        if isinstance(capacity_samples, bool) or not isinstance(
            capacity_samples,
            int,
        ):
            raise TypeError("capacity_samples 必须是整数。")
        if capacity_samples <= 0:
            raise ValueError("capacity_samples 必须大于 0。")

        self._capacity_samples = capacity_samples
        self._chunks: deque[np.ndarray] = deque()
        self._size_samples = 0

    @classmethod
    def from_seconds(
        cls,
        *,
        duration_seconds: float,
        sample_rate: int,
    ) -> PreRollBuffer:
        """根据时长和采样率建立缓冲器。"""

        if duration_seconds <= 0:
            raise ValueError("duration_seconds 必须大于 0。")
        if isinstance(sample_rate, bool) or not isinstance(sample_rate, int):
            raise TypeError("sample_rate 必须是整数。")
        if sample_rate <= 0:
            raise ValueError("sample_rate 必须大于 0。")

        capacity_samples = round(duration_seconds * sample_rate)
        if capacity_samples <= 0:
            raise ValueError("预录音时长不足一个采样点。")
        return cls(capacity_samples=capacity_samples)

    @property
    def capacity_samples(self) -> int:
        return self._capacity_samples

    @property
    def size_samples(self) -> int:
        return self._size_samples

    def append(self, samples: np.ndarray) -> None:
        """复制一段采样，并在溢出时丢弃最旧部分。"""

        array = np.asarray(samples)
        if array.ndim != 1:
            raise ValueError("预录音采样必须是一维单声道数组。")
        if not np.issubdtype(array.dtype, np.number):
            raise TypeError("预录音采样必须是数值数组。")
        if array.size == 0:
            return

        chunk = np.array(array, dtype=np.float32, copy=True)
        if not np.all(np.isfinite(chunk)):
            raise ValueError("预录音采样必须全部是有限数值。")

        if chunk.size >= self._capacity_samples:
            self._chunks.clear()
            self._chunks.append(
                chunk[-self._capacity_samples :].copy()
            )
            self._size_samples = self._capacity_samples
            return

        self._chunks.append(chunk)
        self._size_samples += chunk.size
        self._discard_oldest_overflow()

    def snapshot(self) -> np.ndarray:
        """返回按时间顺序排列的独立采样副本。"""

        if not self._chunks:
            return np.empty(0, dtype=np.float32)
        return np.concatenate(tuple(self._chunks)).astype(
            np.float32,
            copy=True,
        )

    def clear(self) -> None:
        self._chunks.clear()
        self._size_samples = 0

    def _discard_oldest_overflow(self) -> None:
        overflow = self._size_samples - self._capacity_samples
        while overflow > 0:
            oldest = self._chunks[0]
            if oldest.size <= overflow:
                self._chunks.popleft()
                self._size_samples -= oldest.size
                overflow -= oldest.size
                continue

            self._chunks[0] = oldest[overflow:].copy()
            self._size_samples -= overflow
            overflow = 0
