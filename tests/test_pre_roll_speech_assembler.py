import unittest

import numpy as np

from src.audio.pre_roll_speech_assembler import PreRollSpeechAssembler


class PreRollSpeechAssemblerTests(unittest.TestCase):
    def setUp(self):
        self.assembler = PreRollSpeechAssembler()

    def test_assembles_disjoint_audio_in_time_order(self):
        result = self.assembler.assemble(
            pre_roll=np.array([1, 2], dtype=np.float32),
            speech_segment=np.array([3, 4], dtype=np.float32),
        )

        np.testing.assert_array_equal(
            result,
            np.array([1, 2, 3, 4], dtype=np.float32),
        )

    def test_removes_declared_overlap_exactly_once(self):
        result = self.assembler.assemble(
            pre_roll=np.array([1, 2, 3, 4], dtype=np.float32),
            speech_segment=np.array([3, 4, 5, 6], dtype=np.float32),
            overlap_samples=2,
        )

        np.testing.assert_array_equal(
            result,
            np.array([1, 2, 3, 4, 5, 6], dtype=np.float32),
        )

    def test_all_speech_samples_may_already_exist_in_pre_roll(self):
        result = self.assembler.assemble(
            pre_roll=np.array([1, 2, 3], dtype=np.float32),
            speech_segment=np.array([2, 3], dtype=np.float32),
            overlap_samples=2,
        )

        np.testing.assert_array_equal(
            result,
            np.array([1, 2, 3], dtype=np.float32),
        )

    def test_rejects_mismatched_declared_overlap(self):
        with self.assertRaisesRegex(ValueError, "重叠采样不一致"):
            self.assembler.assemble(
                pre_roll=np.array([1, 2], dtype=np.float32),
                speech_segment=np.array([9, 3], dtype=np.float32),
                overlap_samples=1,
            )

    def test_rejects_negative_or_oversized_overlap(self):
        for overlap in (-1, 3):
            with self.subTest(overlap=overlap):
                with self.assertRaises(ValueError):
                    self.assembler.assemble(
                        pre_roll=np.array([1, 2], dtype=np.float32),
                        speech_segment=np.array([1, 2], dtype=np.float32),
                        overlap_samples=overlap,
                    )

    def test_rejects_non_integer_overlap_including_bool(self):
        for overlap in (1.5, True):
            with self.subTest(overlap=overlap):
                with self.assertRaises(TypeError):
                    self.assembler.assemble(
                        pre_roll=np.array([1], dtype=np.float32),
                        speech_segment=np.array([1], dtype=np.float32),
                        overlap_samples=overlap,
                    )

    def test_empty_pre_roll_returns_independent_speech_copy(self):
        speech = np.array([1, 2], dtype=np.float32)

        result = self.assembler.assemble(
            pre_roll=np.array([], dtype=np.float32),
            speech_segment=speech,
        )
        result[0] = 99

        np.testing.assert_array_equal(
            speech,
            np.array([1, 2], dtype=np.float32),
        )

    def test_rejects_empty_speech_segment(self):
        with self.assertRaisesRegex(ValueError, "不能为空"):
            self.assembler.assemble(
                pre_roll=np.array([1], dtype=np.float32),
                speech_segment=np.array([], dtype=np.float32),
            )

    def test_result_and_inputs_do_not_share_mutable_storage(self):
        pre_roll = np.array([1, 2], dtype=np.float32)
        speech = np.array([3, 4], dtype=np.float32)

        result = self.assembler.assemble(
            pre_roll=pre_roll,
            speech_segment=speech,
        )
        pre_roll[0] = 88
        speech[0] = 77

        np.testing.assert_array_equal(
            result,
            np.array([1, 2, 3, 4], dtype=np.float32),
        )

    def test_rejects_multichannel_or_non_finite_audio(self):
        with self.assertRaisesRegex(ValueError, "一维"):
            self.assembler.assemble(
                pre_roll=np.zeros((2, 2), dtype=np.float32),
                speech_segment=np.array([1], dtype=np.float32),
            )
        with self.assertRaisesRegex(ValueError, "有限"):
            self.assembler.assemble(
                pre_roll=np.array([1], dtype=np.float32),
                speech_segment=np.array([np.inf], dtype=np.float32),
            )

    def test_consecutive_recordings_do_not_share_state(self):
        first = self.assembler.assemble(
            pre_roll=np.array([1], dtype=np.float32),
            speech_segment=np.array([2], dtype=np.float32),
        )
        second = self.assembler.assemble(
            pre_roll=np.array([10], dtype=np.float32),
            speech_segment=np.array([11], dtype=np.float32),
        )

        np.testing.assert_array_equal(first, np.array([1, 2]))
        np.testing.assert_array_equal(second, np.array([10, 11]))


if __name__ == "__main__":
    unittest.main()
