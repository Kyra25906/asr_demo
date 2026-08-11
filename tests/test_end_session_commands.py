import unittest

from src.main import (
    is_end_session_command,
    normalize_command,
)
from src.core.interaction_command import (
    InteractionCommandParser,
    InteractionCommandType,
)


class NormalizeCommandTests(
    unittest.TestCase
):
    def test_removes_common_punctuation(
        self,
    ):
        result = normalize_command(
            "结束，实验记录！"
        )

        self.assertEqual(
            result,
            "结束实验记录",
        )

    def test_removes_spaces(
        self,
    ):
        result = normalize_command(
            "结束 实验 记录"
        )

        self.assertEqual(
            result,
            "结束实验记录",
        )

    def test_keeps_chinese_content(
        self,
    ):
        result = normalize_command(
            "结束搅拌。"
        )

        self.assertEqual(
            result,
            "结束搅拌",
        )


class EndSessionCommandTests(
    unittest.TestCase
):
    def test_accepts_standard_commands(
        self,
    ):
        """
        所有正式支持的结束指令
        都必须能够结束会话。
        """

        commands = [
            "结束实验记录",
            "结束记录",
            "结束本次实验",
            "结束实验",
            "退出实验记录",
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertTrue(
                    is_end_session_command(
                        command
                    )
                )

    def test_accepts_punctuation(
        self,
    ):
        """
        ASR可能保留句号或其他标点，
        标点不应影响控制指令。
        """

        commands = [
            "结束实验记录。",
            "结束实验记录！",
            "结束，实验记录。",
            "结束实验？",
            "退出实验记录！",
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertTrue(
                    is_end_session_command(
                        command
                    )
                )

    def test_accepts_spaces(
        self,
    ):
        """
        不同ASR或文本输入可能产生空格。
        """

        commands = [
            "结束 实验记录",
            "结束实验 记录",
            "结束 实验 记录",
            "  结束实验记录  ",
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertTrue(
                    is_end_session_command(
                        command
                    )
                )

    def test_accepts_observed_asr_variant(
        self,
    ):
        """
        只兼容已经在真实测试中
        观察到的结束命令误识别。

        不进行不受控制的模糊匹配。
        """

        commands = [
            "接受实验记录",
            "接受实验记录。",
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertTrue(
                    is_end_session_command(
                        command
                    )
                )

    def test_accepts_sensevoice_trailing_emotion(self):
        """真实ASR句尾情绪标记不属于命令正文。"""

        for command in (
            "接受实验记录。😔",
            "结束实验记录😊",
            "退出实验记录！😮",
        ):
            with self.subTest(command=command):
                self.assertTrue(is_end_session_command(command))

    def test_main_delegates_to_formal_command_parser(self):
        """main不能再维护一套会漂移的结束命令规则。"""

        cases = tuple(InteractionCommandParser.END_SESSION_COMMANDS) + (
            "接受实验记录。😔",
            "结束加热。",
            "实验结束后清洗仪器。",
        )
        for text in cases:
            with self.subTest(text=text):
                formal = InteractionCommandParser.parse(text)
                self.assertEqual(
                    is_end_session_command(text),
                    formal.command_type == InteractionCommandType.END_SESSION,
                )

    def test_rejects_operation_end_commands(
        self,
    ):
        """
        结束某个实验操作，
        不等于结束整个实验会话。
        """

        commands = [
            "结束搅拌",
            "结束加热",
            "结束离心",
            "结束滴定",
            "结束洗涤",
            "停止搅拌",
            "停止加热",
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertFalse(
                    is_end_session_command(
                        command
                    )
                )

    def test_rejects_longer_experiment_sentences(
        self,
    ):
        """
        长句中出现“结束实验”等字样，
        不应只按子字符串误判。

        当前实现采用规范化后的精确匹配，
        这些句子应返回False。
        """

        commands = [
            "实验结束后清洗所有仪器",
            "结束实验记录后生成报告",
            "记录实验结束时的温度",
            "观察反应结束时溶液的颜色",
            "加热结束后冷却至室温",
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertFalse(
                    is_end_session_command(
                        command
                    )
                )

    def test_rejects_empty_or_noise_text(
        self,
    ):
        commands = [
            "",
            " ",
            "。",
            "嗯",
            "好的",
            "继续记录",
        ]

        for command in commands:
            with self.subTest(
                command=command
            ):
                self.assertFalse(
                    is_end_session_command(
                        command
                    )
                )


if __name__ == "__main__":
    unittest.main()
