import unittest

import numpy as np

from src.audio.pre_roll_timeline import PreRollTimelineBuffer


class PreRollTimelineBufferTests(unittest.TestCase):
    def test_snapshot_reports_half_open_sample_range(self):
        buffer = PreRollTimelineBuffer(capacity_samples=5)
        buffer.append(np.array([1, 2, 3], dtype=np.float32))

        snapshot = buffer.snapshot()

        self.assertEqual(snapshot.start_sample, 0)
        self.assertEqual(snapshot.end_sample, 3)
        np.testing.assert_array_equal(snapshot.samples, [1, 2, 3])

    def test_overflow_advances_start_but_keeps_absolute_end(self):
        buffer = PreRollTimelineBuffer(capacity_samples=4)
        buffer.append(np.array([1, 2, 3], dtype=np.float32))
        buffer.append(np.array([4, 5, 6], dtype=np.float32))

        snapshot = buffer.snapshot()

        self.assertEqual(snapshot.start_sample, 2)
        self.assertEqual(snapshot.end_sample, 6)
        np.testing.assert_array_equal(snapshot.samples, [3, 4, 5, 6])

    def test_empty_snapshot_stays_at_current_timeline_position(self):
        buffer = PreRollTimelineBuffer(capacity_samples=2)

        snapshot = buffer.snapshot()

        self.assertEqual(snapshot.start_sample, 0)
        self.assertEqual(snapshot.end_sample, 0)
        self.assertEqual(snapshot.samples.size, 0)

    def test_empty_append_does_not_advance_timeline(self):
        buffer = PreRollTimelineBuffer(capacity_samples=2)
        buffer.append(np.array([], dtype=np.float32))

        self.assertEqual(buffer.total_samples, 0)

    def test_invalid_append_does_not_advance_timeline(self):
        buffer = PreRollTimelineBuffer(capacity_samples=4)

        with self.assertRaises(ValueError):
            buffer.append(np.array([1.0, np.nan], dtype=np.float32))

        self.assertEqual(buffer.total_samples, 0)
        self.assertEqual(buffer.snapshot().samples.size, 0)

    def test_clear_resets_audio_and_timeline_for_next_recording(self):
        buffer = PreRollTimelineBuffer(capacity_samples=3)
        buffer.append(np.array([1, 2], dtype=np.float32))

        buffer.clear()
        buffer.append(np.array([9], dtype=np.float32))
        snapshot = buffer.snapshot()

        self.assertEqual(snapshot.start_sample, 0)
        self.assertEqual(snapshot.end_sample, 1)
        np.testing.assert_array_equal(snapshot.samples, [9])

    def test_from_seconds_uses_sample_capacity(self):
        buffer = PreRollTimelineBuffer.from_seconds(
            duration_seconds=0.5,
            sample_rate=16_000,
        )

        self.assertEqual(buffer.capacity_samples, 8_000)


if __name__ == "__main__":
    unittest.main()
