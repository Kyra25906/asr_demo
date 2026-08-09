import unittest

import numpy as np

from src.audio.pre_roll_buffer import PreRollBuffer


class PreRollBufferTests(unittest.TestCase):
    def test_keeps_samples_in_original_order_before_capacity(self):
        buffer = PreRollBuffer(capacity_samples=5)

        buffer.append(np.array([1.0, 2.0], dtype=np.float32))
        buffer.append(np.array([3.0], dtype=np.float32))

        np.testing.assert_array_equal(
            buffer.snapshot(),
            np.array([1.0, 2.0, 3.0], dtype=np.float32),
        )
        self.assertEqual(buffer.size_samples, 3)

    def test_discards_only_oldest_samples_after_overflow(self):
        buffer = PreRollBuffer(capacity_samples=5)

        buffer.append(np.array([1, 2], dtype=np.float32))
        buffer.append(np.array([3, 4], dtype=np.float32))
        buffer.append(np.array([5, 6], dtype=np.float32))

        np.testing.assert_array_equal(
            buffer.snapshot(),
            np.array([2, 3, 4, 5, 6], dtype=np.float32),
        )
        self.assertEqual(buffer.size_samples, 5)

    def test_large_chunk_keeps_only_its_tail(self):
        buffer = PreRollBuffer(capacity_samples=3)

        buffer.append(np.array([1, 2, 3, 4, 5], dtype=np.float32))

        np.testing.assert_array_equal(
            buffer.snapshot(),
            np.array([3, 4, 5], dtype=np.float32),
        )

    def test_snapshot_is_a_copy_not_internal_storage(self):
        buffer = PreRollBuffer(capacity_samples=3)
        buffer.append(np.array([1, 2, 3], dtype=np.float32))

        snapshot = buffer.snapshot()
        snapshot[0] = 99

        np.testing.assert_array_equal(
            buffer.snapshot(),
            np.array([1, 2, 3], dtype=np.float32),
        )

    def test_append_copies_input_array(self):
        buffer = PreRollBuffer(capacity_samples=3)
        source = np.array([1, 2, 3], dtype=np.float32)

        buffer.append(source)
        source[0] = 99

        np.testing.assert_array_equal(
            buffer.snapshot(),
            np.array([1, 2, 3], dtype=np.float32),
        )

    def test_clear_removes_all_samples(self):
        buffer = PreRollBuffer(capacity_samples=3)
        buffer.append(np.array([1, 2], dtype=np.float32))

        buffer.clear()

        self.assertEqual(buffer.size_samples, 0)
        self.assertEqual(buffer.snapshot().dtype, np.float32)
        self.assertEqual(buffer.snapshot().size, 0)

    def test_from_seconds_converts_duration_to_sample_capacity(self):
        buffer = PreRollBuffer.from_seconds(
            duration_seconds=0.5,
            sample_rate=16_000,
        )

        self.assertEqual(buffer.capacity_samples, 8_000)

    def test_empty_chunk_is_a_safe_no_op(self):
        buffer = PreRollBuffer(capacity_samples=3)
        buffer.append(np.array([], dtype=np.float32))

        self.assertEqual(buffer.size_samples, 0)

    def test_rejects_non_positive_capacity_or_duration(self):
        for capacity in (0, -1):
            with self.subTest(capacity=capacity):
                with self.assertRaises(ValueError):
                    PreRollBuffer(capacity_samples=capacity)

        with self.assertRaises(ValueError):
            PreRollBuffer.from_seconds(
                duration_seconds=0,
                sample_rate=16_000,
            )
        with self.assertRaises(ValueError):
            PreRollBuffer.from_seconds(
                duration_seconds=0.5,
                sample_rate=0,
            )

    def test_rejects_multichannel_or_non_finite_samples(self):
        buffer = PreRollBuffer(capacity_samples=4)

        with self.assertRaisesRegex(ValueError, "一维"):
            buffer.append(np.zeros((2, 2), dtype=np.float32))

        with self.assertRaisesRegex(ValueError, "有限"):
            buffer.append(np.array([0.0, np.nan], dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
