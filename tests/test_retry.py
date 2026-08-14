import unittest

from src.core.retry import next_backoff_delay


class NextBackoffDelayTests(unittest.TestCase):
    def test_default_backoff_doubles_then_caps(self):
        delays = [
            next_backoff_delay(attempt)
            for attempt in range(1, 7)
        ]

        self.assertEqual(delays, [1.0, 2.0, 4.0, 8.0, 10.0, 10.0])

    def test_custom_base_and_cap(self):
        delays = [
            next_backoff_delay(attempt, base_seconds=0.5, cap_seconds=3.0)
            for attempt in range(1, 6)
        ]

        self.assertEqual(delays, [0.5, 1.0, 2.0, 3.0, 3.0])

    def test_attempt_must_start_at_one(self):
        with self.assertRaisesRegex(ValueError, "attempt"):
            next_backoff_delay(0)

    def test_base_must_be_positive(self):
        with self.assertRaisesRegex(ValueError, "base_seconds"):
            next_backoff_delay(1, base_seconds=0)

    def test_cap_must_not_be_below_base(self):
        with self.assertRaisesRegex(ValueError, "cap_seconds"):
            next_backoff_delay(1, base_seconds=5.0, cap_seconds=2.0)


if __name__ == "__main__":
    unittest.main()
