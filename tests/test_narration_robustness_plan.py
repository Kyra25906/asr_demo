"""ASR鲁棒性口述语料的计划校验与确定性解析断言。

覆盖两层：
1. 语料计划schema：31段真实语料可加载，坏数据被严格拒绝；
2. 确定性解析行为：精确命令解析器（零LLM快速路径）对每类噪声段的表现，
   把"必须依赖LLM容错"和"精确路径已知限制"文档化为断言。
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.core.interaction_command import (
    InteractionCommandParser,
    InteractionCommandType,
)
from src.evaluation.narration_robustness_plan import (
    NarrationPlanError,
    NarrationRobustnessPlan,
    NarrationSegment,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = (
    PROJECT_ROOT
    / "evaluation"
    / "narration_robustness"
    / "narration_plan.json"
)


def load_plan() -> NarrationRobustnessPlan:
    return NarrationRobustnessPlan.load(PLAN_PATH)


def parse_exact(text: str):
    return InteractionCommandParser.parse(text)


def make_segment(**overrides) -> NarrationSegment:
    base = dict(
        segment_id=1,
        challenge_type="normal",
        spoken_text="加入5毫升缓冲液并搅拌。",
        observed_asr_text="加入5毫升缓冲液并搅拌。",
        pending_question_numbers=(),
        current_question_number=None,
        expected_input_kind="experiment",
        expected_command=None,
        expected_missing_fields=(),
        expected_needs_confirmation=False,
    )
    base.update(overrides)
    return NarrationSegment(**base)


class NarrationPlanSchemaTest(unittest.TestCase):
    def test_real_plan_loads_with_31_segments(self) -> None:
        plan = load_plan()
        self.assertEqual(plan.schema_version, 1)
        self.assertEqual(len(plan.segments), 31)
        self.assertEqual(plan.segments[0].segment_id, 1)
        self.assertEqual(plan.segments[-1].segment_id, 31)
        self.assertTrue(plan.scenario)
        self.assertTrue(plan.session_id)

    def test_missing_field_rejected(self) -> None:
        with self.assertRaises(NarrationPlanError):
            NarrationSegment(
                segment_id=1,
                challenge_type="normal",
                spoken_text="",
                observed_asr_text="x",
                pending_question_numbers=(),
                current_question_number=None,
                expected_input_kind="experiment",
                expected_command=None,
                expected_missing_fields=(),
                expected_needs_confirmation=False,
            )

    def test_unknown_challenge_type_rejected(self) -> None:
        with self.assertRaises(NarrationPlanError):
            make_segment(challenge_type="not_a_challenge")

    def test_current_question_not_in_pending_rejected(self) -> None:
        with self.assertRaises(NarrationPlanError):
            make_segment(
                pending_question_numbers=(1, 2),
                current_question_number=3,
            )

    def test_control_segment_without_command_rejected(self) -> None:
        with self.assertRaises(NarrationPlanError):
            make_segment(
                expected_input_kind="control",
                expected_command=None,
            )

    def test_experiment_segment_with_command_rejected(self) -> None:
        with self.assertRaises(NarrationPlanError):
            make_segment(
                expected_command="end_session",
            )

    def test_unknown_missing_field_rejected(self) -> None:
        with self.assertRaises(NarrationPlanError):
            make_segment(expected_missing_fields=("volume",))

    def test_duplicate_pending_number_rejected(self) -> None:
        with self.assertRaises(NarrationPlanError):
            make_segment(
                pending_question_numbers=(1, 1),
                current_question_number=1,
            )

    def test_json_plan_with_extra_key_rejected(self) -> None:
        path = self._write_plan(
            [self._segment_json(segment_id=1)], extra_root={"stray": 1}
        )
        with self.assertRaises(NarrationPlanError):
            NarrationRobustnessPlan.load(path)

    def test_json_plan_with_discontinuous_ids_rejected(self) -> None:
        path = self._write_plan(
            [
                self._segment_json(segment_id=1),
                self._segment_json(segment_id=3),
            ]
        )
        with self.assertRaises(NarrationPlanError):
            NarrationRobustnessPlan.load(path)

    def test_json_plan_with_non_object_segment_rejected(self) -> None:
        path = self._write_plan(["not-an-object"])
        with self.assertRaises(NarrationPlanError):
            NarrationRobustnessPlan.load(path)

    @staticmethod
    def _segment_json(segment_id: int) -> dict:
        return {
            "segment_id": segment_id,
            "challenge_type": "normal",
            "spoken_text": f"口述{segment_id}。",
            "observed_asr_text": f"口述{segment_id}。",
            "pending_question_numbers": [],
            "current_question_number": None,
            "expected_input_kind": "experiment",
            "expected_command": None,
            "expected_missing_fields": [],
            "expected_needs_confirmation": False,
        }

    def _write_plan(
        self,
        segments: list,
        *,
        extra_root: dict | None = None,
    ) -> Path:
        data = {
            "schema_version": 1,
            "scenario": "测试场景",
            "session_id": "schema-test",
            "segments": segments,
        }
        if extra_root:
            data.update(extra_root)
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "plan.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        return path


class ExactParserRobustnessTest(unittest.TestCase):
    """精确命令解析器（零LLM快速路径）对噪声语料的确定性行为。"""

    def test_experiment_segments_never_trigger_exact_commands(self) -> None:
        plan = load_plan()
        experiment_segments = [
            segment
            for segment in plan.segments
            if segment.expected_input_kind == "experiment"
        ]
        self.assertEqual(len(experiment_segments), 14)
        for segment in experiment_segments:
            with self.subTest(segment=segment.segment_id):
                command = parse_exact(segment.observed_asr_text)
                self.assertEqual(
                    command.command_type,
                    InteractionCommandType.NORMAL,
                    f"实验段{segment.segment_id}不应误触发控制命令",
                )

    def test_review_noise_relies_on_llm_tolerance(self) -> None:
        """段5 '看待确认问题'精确解析为normal，必须依赖LLM语义容错。"""
        segment = load_plan().segments[4]
        self.assertEqual(segment.challenge_type, "asr_noise_control")
        command = parse_exact(segment.observed_asr_text)
        self.assertEqual(command.command_type, InteractionCommandType.NORMAL)

    def test_review_exact_hits_zero_llm_fast_path(self) -> None:
        """段6 '还有什么问题？'命中自然模式，零LLM快速路径。"""
        segment = load_plan().segments[5]
        self.assertEqual(segment.challenge_type, "control_review_exact")
        command = parse_exact(segment.observed_asr_text)
        self.assertEqual(
            command.command_type, InteractionCommandType.REVIEW_PENDING
        )

    def test_defer_exact_and_natural_variant(self) -> None:
        """段15/16 暂缓：词表精确命中 + 安全前缀自然规则。"""
        plan = load_plan()
        for index in (14, 15):
            with self.subTest(index=index):
                command = parse_exact(
                    plan.segments[index].observed_asr_text
                )
                self.assertEqual(
                    command.command_type,
                    InteractionCommandType.DEFER_CURRENT,
                )

    def test_wrong_number_answer_parses_targeted_question_two(self) -> None:
        """段11 '问题二，持续10分钟。'精确解析为#2（探测错编号处理）。"""
        segment = load_plan().segments[10]
        command = parse_exact(segment.observed_asr_text)
        self.assertEqual(
            command.command_type, InteractionCommandType.TARGETED_ANSWER
        )
        self.assertEqual(command.target_question_number, 2)

    def test_two_answers_known_limitation_single_target(self) -> None:
        """段12 一次答两个问题：已知限制——整句被当问题4的答案。"""
        segment = load_plan().segments[11]
        command = parse_exact(segment.observed_asr_text)
        self.assertEqual(
            command.command_type, InteractionCommandType.TARGETED_ANSWER
        )
        self.assertEqual(command.target_question_number, 4)
        self.assertIn(
            "问题五",
            command.answer_text or "",
            "精确解析器把第二个问题拼进了第一个问题的答案（已知限制）",
        )

    def test_number_only_answer_has_no_answer_text(self) -> None:
        """段13 '问题5。'只有编号没有答案，下游应转no_action。"""
        segment = load_plan().segments[12]
        command = parse_exact(segment.observed_asr_text)
        self.assertEqual(
            command.command_type, InteractionCommandType.TARGETED_ANSWER
        )
        self.assertEqual(command.target_question_number, 5)
        self.assertIsNone(command.answer_text)

    def test_affirm_and_deny_exact(self) -> None:
        """段8 '是的。'→affirm；段18 '不对，应该是7.4。'→deny。"""
        plan = load_plan()
        affirm = parse_exact(plan.segments[7].observed_asr_text)
        self.assertEqual(affirm.command_type, InteractionCommandType.AFFIRM)
        deny = parse_exact(plan.segments[17].observed_asr_text)
        self.assertEqual(deny.command_type, InteractionCommandType.DENY)

    def test_natural_end_relies_on_llm(self) -> None:
        """段28 '今天先记录到这里吧。'不在精确词表，依赖LLM结束候选。"""
        segment = load_plan().segments[27]
        self.assertEqual(segment.challenge_type, "end_session")
        command = parse_exact(segment.observed_asr_text)
        self.assertEqual(command.command_type, InteractionCommandType.NORMAL)

    def test_control_label_matches_parser_category(self) -> None:
        """语料自洽：编号型回答（段11/12/13）精确解析命中；无编号回答
        （段3/4/23）必须依赖LLM，精确解析为normal。"""
        plan = load_plan()
        numbered_indexes = (10, 11, 12)
        no_number_indexes = (2, 3, 22)
        for index in numbered_indexes:
            with self.subTest(index=index):
                command = parse_exact(
                    plan.segments[index].observed_asr_text
                )
                self.assertEqual(
                    command.command_type,
                    InteractionCommandType.TARGETED_ANSWER,
                )
        for index in no_number_indexes:
            with self.subTest(index=index):
                command = parse_exact(
                    plan.segments[index].observed_asr_text
                )
                self.assertEqual(
                    command.command_type, InteractionCommandType.NORMAL
                )


if __name__ == "__main__":
    unittest.main()
