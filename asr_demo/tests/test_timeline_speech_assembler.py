import unittest

import numpy as np

from src.audio.pre_roll_timeline import PreRollSnapshot
from src.audio.timeline_speech_assembler import TimelineSpeechAssembler


def snapshot(samples, start):
    array = np.array(samples, dtype=np.float32)
    return PreRollSnapshot(
        samples=array,
        start_sample=start,
        end_sample=start + array.size,
    )


class TimelineSpeechAssemblerTests(unittest.TestCase):
    def setUp(self):
        self.assembler = TimelineSpeechAssembler()

    def test_calculates_overlap_from_absolute_sample_positions(self):
        result = self.assembler.assemble(
            pre_roll=snapshot([1, 2, 3, 4], start=10),
            speech_segment=np.array([3, 4, 5, 6]),
            speech_start_sample=12,
        )

        np.testing.assert_array_equal(result, [1, 2, 3, 4, 5, 6])

    def test_accepts_touching_segments_without_overlap(self):
        result = self.assembler.assemble(
            pre_roll=snapshot([1, 2], start=10),
            speech_segment=np.array([3, 4]),
            speech_start_sample=12,
        )

        np.testing.assert_array_equal(result, [1, 2, 3, 4])

    def test_returns_speech_when_it_already_contains_pre_roll(self):
        result = self.assembler.assemble(
            pre_roll=snapshot([2, 3], start=11),
            speech_segment=np.array([1, 2, 3, 4]),
            speech_start_sample=10,
        )

        np.testing.assert_array_equal(result, [1, 2, 3, 4])

    def test_appends_pre_roll_tail_when_speech_ends_inside_snapshot(self):
        result = self.assembler.assemble(
            pre_roll=snapshot([3, 4, 5], start=12),
            speech_segment=np.array([1, 2, 3, 4]),
            speech_start_sample=10,
        )

        np.testing.assert_array_equal(result, [1, 2, 3, 4, 5])

    def test_rejects_unknown_gap(self):
        with self.assertRaisesRegex(ValueError, "未知采样缺口"):
            self.assembler.assemble(
                pre_roll=snapshot([1, 2], start=10),
                speech_segment=np.array([4, 5]),
                speech_start_sample=13,
            )

    def test_rejects_inconsistent_overlap(self):
        with self.assertRaisesRegex(ValueError, "重叠采样不一致"):
            self.assembler.assemble(
                pre_roll=snapshot([1, 2, 3], start=10),
                speech_segment=np.array([9, 4]),
                speech_start_sample=12,
            )

    def test_rejects_invalid_start_or_empty_speech(self):
        with self.assertRaises(ValueError):
            self.assembler.assemble(
                pre_roll=snapshot([1], start=0),
                speech_segment=np.array([1]),
                speech_start_sample=-1,
            )
        with self.assertRaisesRegex(ValueError, "不能为空"):
            self.assembler.assemble(
                pre_roll=snapshot([], start=0),
                speech_segment=np.array([]),
                speech_start_sample=0,
            )


if __name__ == "__main__":
    unittest.main()
