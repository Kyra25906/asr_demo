"""程序级呈现集成测试。

证明启动、就绪、唤醒和 Ctrl+C 退出反馈全部经同一个程序级
Coordinator/Pump 交付，且会话获得的也是这条共享链路。
"""

import unittest
from unittest.mock import Mock, patch

from src.main import main


class _WakeThenExit:
    def __init__(self, **kwargs):
        self.calls = 0

    def wait_for_wake_word(self):
        self.calls += 1
        if self.calls == 1:
            return "小科小科"
        raise KeyboardInterrupt


class MainProgramFeedbackTests(unittest.TestCase):
    @patch("src.main.configure_logging")
    @patch("src.main.VadAudioRecorder", return_value=Mock())
    @patch("src.main.ASRResultStore", return_value=Mock())
    @patch("src.main.ConfirmationStore", return_value=Mock())
    @patch("src.main.ExperimentEventStore", return_value=Mock())
    @patch("src.main.create_unified_observer", return_value=Mock())
    @patch("src.main.create_asr_backend", return_value=Mock())
    @patch("src.main.WakeWordDetector", side_effect=_WakeThenExit)
    @patch("src.main.play_wake_tone")
    @patch("src.main.run_experiment_session")
    def test_program_feedback_is_visible_once_and_session_reuses_pump(
        self,
        run_session,
        play_tone,
        detector_factory,
        create_backend,
        create_observer,
        event_store,
        confirmation_store,
        asr_store,
        recorder,
        configure_logging,
    ):
        with patch("builtins.print") as output:
            main()

        rendered = "\n".join(call.args[0] for call in output.call_args_list)
        self.assertEqual(rendered.count("正在启动，请稍候"), 1)
        self.assertEqual(rendered.count("已就绪，正在等待唤醒"), 1)
        self.assertEqual(rendered.count("唤醒成功：小科小科"), 1)
        self.assertEqual(rendered.count("已返回待机"), 1)
        self.assertIn("再次说“小科小科”开始新会话", rendered)
        self.assertEqual(rendered.count("已退出实验语音智能体"), 1)

        play_tone.assert_called_once_with()
        run_session.assert_called_once()
        kwargs = run_session.call_args.kwargs
        self.assertIsNotNone(kwargs["presentation_coordinator"])
        self.assertIsNotNone(kwargs["presentation_pump"])

    @patch("src.main.configure_logging")
    @patch("src.main.VadAudioRecorder", side_effect=KeyboardInterrupt)
    def test_exit_feedback_is_visible_when_interrupted_during_startup(
        self,
        recorder,
        configure_logging,
    ):
        with patch("builtins.print") as output:
            main()

        rendered = "\n".join(call.args[0] for call in output.call_args_list)
        self.assertEqual(rendered.count("正在启动，请稍候"), 1)
        self.assertEqual(rendered.count("已退出实验语音智能体"), 1)
        self.assertNotIn("已就绪", rendered)


if __name__ == "__main__":
    unittest.main()
