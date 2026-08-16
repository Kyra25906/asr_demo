import unittest

from src.core.presentation_timing import IdleNoticeTracker


class IdleNoticeTrackerTests(unittest.TestCase):
    def test_repeated_timeouts_in_same_stage_are_silent(self):
        tracker = IdleNoticeTracker()

        first = tracker.message_for_timeout(270)
        repeated = tracker.message_for_timeout(240)

        self.assertIn("继续等待", first)
        self.assertIsNone(repeated)

    def test_each_countdown_milestone_is_announced_once(self):
        tracker = IdleNoticeTracker()

        messages = [
            tracker.message_for_timeout(270),
            tracker.message_for_timeout(60),
            tracker.message_for_timeout(55),
            tracker.message_for_timeout(30),
            tracker.message_for_timeout(20),
        ]

        self.assertEqual(
            [message for message in messages if message is not None],
            [
                "暂时没有检测到口述，实验会话继续等待。",
                "仍未检测到口述，距离自动结束约还有 60 秒。",
                "仍未检测到口述，距离自动结束约还有 30 秒。",
            ],
        )

    def test_first_late_timeout_uses_the_current_urgent_stage(self):
        tracker = IdleNoticeTracker()

        message = tracker.message_for_timeout(25)

        self.assertIn("30 秒", message)

    def test_activity_reset_allows_a_new_waiting_notice(self):
        tracker = IdleNoticeTracker()
        tracker.message_for_timeout(270)

        tracker.reset()
        message = tracker.message_for_timeout(270)

        self.assertIn("继续等待", message)

    def test_expired_session_is_left_for_main_to_end(self):
        tracker = IdleNoticeTracker()

        self.assertIsNone(tracker.message_for_timeout(0))


if __name__ == "__main__":
    unittest.main()
