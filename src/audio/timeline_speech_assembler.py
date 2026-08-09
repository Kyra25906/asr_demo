"""根据绝对采样位置组装预缓冲快照和VAD语音段。"""

from __future__ import annotations

import numpy as np

from src.audio.pre_roll_speech_assembler import PreRollSpeechAssembler
from src.audio.pre_roll_timeline import PreRollSnapshot


class TimelineSpeechAssembler:
    """把采样时间线转换成可验证的音频重叠量。"""

    def __init__(self) -> None:
        self._assembler = PreRollSpeechAssembler()

    def assemble(
        self,
        *,
        pre_roll: PreRollSnapshot,
        speech_segment: np.ndarray,
        speech_start_sample: int,
    ) -> np.ndarray:
        if isinstance(speech_start_sample, bool) or not isinstance(
            speech_start_sample,
            int,
        ):
            raise TypeError("speech_start_sample 必须是整数。")
        if speech_start_sample < 0:
            raise ValueError("speech_start_sample 不能小于 0。")

        speech = self._copy_speech(speech_segment)
        speech_end_sample = speech_start_sample + speech.size

        if pre_roll.samples.size == 0:
            return speech

        if speech_start_sample > pre_roll.end_sample:
            raise ValueError("预缓冲和语音段之间存在未知采样缺口。")
        if speech_end_sample < pre_roll.start_sample:
            raise ValueError("语音段结束位置早于预缓冲开始位置。")

        if pre_roll.start_sample <= speech_start_sample:
            overlap_samples = pre_roll.end_sample - speech_start_sample
            return self._assembler.assemble(
                pre_roll=pre_roll.samples,
                speech_segment=speech,
                overlap_samples=overlap_samples,
            )

        pre_roll_offset = pre_roll.start_sample - speech_start_sample
        if speech_end_sample < pre_roll.end_sample:
            overlap_samples = speech_end_sample - pre_roll.start_sample
            speech_overlap = speech[-overlap_samples:]
            pre_roll_overlap = pre_roll.samples[:overlap_samples]
            if not np.array_equal(speech_overlap, pre_roll_overlap):
                raise ValueError("时间线重叠采样不一致，无法安全组装。")
            return np.concatenate(
                (speech, pre_roll.samples[overlap_samples:])
            ).astype(np.float32, copy=False)

        contained = speech[
            pre_roll_offset : pre_roll_offset + pre_roll.samples.size
        ]
        if not np.array_equal(contained, pre_roll.samples):
            raise ValueError("时间线重叠采样不一致，无法安全组装。")
        return speech.copy()

    @staticmethod
    def _copy_speech(samples: np.ndarray) -> np.ndarray:
        array = np.asarray(samples)
        if array.ndim != 1:
            raise ValueError("speech_segment 必须是一维单声道数组。")
        if not np.issubdtype(array.dtype, np.number):
            raise TypeError("speech_segment 必须是数值数组。")
        copied = np.array(array, dtype=np.float32, copy=True)
        if copied.size == 0:
            raise ValueError("speech_segment 不能为空。")
        if not np.all(np.isfinite(copied)):
            raise ValueError("speech_segment 必须全部是有限数值。")
        return copied
