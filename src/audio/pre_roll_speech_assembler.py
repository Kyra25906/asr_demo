"""安全地组装触发前缓冲音频和VAD语音段。"""

from __future__ import annotations

import numpy as np


class PreRollSpeechAssembler:
    """按已知重叠量拼接两段单声道音频，不自行猜测边界。"""

    def assemble(
        self,
        *,
        pre_roll: np.ndarray,
        speech_segment: np.ndarray,
        overlap_samples: int = 0,
    ) -> np.ndarray:
        """返回“预缓冲 + 去除已知重叠后的语音段”。

        ``overlap_samples`` 表示 ``pre_roll`` 尾部和
        ``speech_segment`` 头部重复的采样点数。指定重叠时，两处采样
        必须完全相同；否则拒绝拼接，避免静默删除真实语音。
        """

        pre_roll_array = self._copy_mono_samples(
            pre_roll,
            field_name="pre_roll",
        )
        speech_array = self._copy_mono_samples(
            speech_segment,
            field_name="speech_segment",
        )

        if speech_array.size == 0:
            raise ValueError("speech_segment 不能为空。")
        self._validate_overlap(
            overlap_samples=overlap_samples,
            pre_roll_size=pre_roll_array.size,
            speech_size=speech_array.size,
        )

        if overlap_samples:
            pre_roll_overlap = pre_roll_array[-overlap_samples:]
            speech_overlap = speech_array[:overlap_samples]
            if not np.array_equal(pre_roll_overlap, speech_overlap):
                raise ValueError(
                    "声明的重叠采样不一致，无法安全去重。"
                )

        speech_tail = speech_array[overlap_samples:]
        if pre_roll_array.size == 0:
            return speech_tail.copy()
        if speech_tail.size == 0:
            return pre_roll_array.copy()
        return np.concatenate((pre_roll_array, speech_tail)).astype(
            np.float32,
            copy=False,
        )

    @staticmethod
    def _copy_mono_samples(
        samples: np.ndarray,
        *,
        field_name: str,
    ) -> np.ndarray:
        array = np.asarray(samples)
        if array.ndim != 1:
            raise ValueError(f"{field_name} 必须是一维单声道数组。")
        if not np.issubdtype(array.dtype, np.number):
            raise TypeError(f"{field_name} 必须是数值数组。")

        copied = np.array(array, dtype=np.float32, copy=True)
        if not np.all(np.isfinite(copied)):
            raise ValueError(f"{field_name} 必须全部是有限数值。")
        return copied

    @staticmethod
    def _validate_overlap(
        *,
        overlap_samples: int,
        pre_roll_size: int,
        speech_size: int,
    ) -> None:
        if isinstance(overlap_samples, bool) or not isinstance(
            overlap_samples,
            int,
        ):
            raise TypeError("overlap_samples 必须是整数。")
        if overlap_samples < 0:
            raise ValueError("overlap_samples 不能小于 0。")
        if overlap_samples > min(pre_roll_size, speech_size):
            raise ValueError(
                "overlap_samples 不能超过任一输入音频的长度。"
            )
