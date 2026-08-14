import unittest

from src.core.answer_fallback import (
    decide_unnumbered_answer,
    extract_entity_fields,
)
from src.core.pending_clarification import (
    ClarificationStatus,
    PendingClarification,
)


def pending_question(
    *,
    display_number: int = 1,
    missing_fields=("temperature", "duration"),
) -> PendingClarification:
    return PendingClarification(
        clarification_id=f"unified-{display_number}",
        display_number=display_number,
        source_segment_id=1,
        source_raw_text="将溶液加热。",
        question="加热到什么温度？需要加热多长时间？",
        missing_fields=missing_fields,
        status=ClarificationStatus.ACTIVE,
    )


class ExtractEntityFieldsTests(unittest.TestCase):
    def test_extracts_temperature(self):
        self.assertEqual(
            extract_entity_fields("加热到60摄氏度"),
            ("temperature",),
        )

    def test_extracts_duration(self):
        self.assertEqual(
            extract_entity_fields("时间为10分钟"),
            ("duration",),
        )

    def test_extracts_amount(self):
        fields = extract_entity_fields("加入5毫升缓冲液")
        self.assertIn("amount_value", fields)
        self.assertIn("amount_unit", fields)

    def test_empty_and_plain_text_return_nothing(self):
        self.assertEqual(extract_entity_fields(""), ())
        self.assertEqual(extract_entity_fields("随便说说"), ())


class DecideUnnumberedAnswerTests(unittest.TestCase):
    def test_single_question_with_missing_field_match_is_answer(self):
        decision = decide_unnumbered_answer(
            pending_questions=[pending_question()],
            text="时间为10分钟",
        )
        self.assertTrue(decision.is_answer)
        self.assertEqual(decision.fields, ("duration",))

    def test_single_question_temperature_answer(self):
        decision = decide_unnumbered_answer(
            pending_questions=[pending_question()],
            text="60摄氏度",
        )
        self.assertTrue(decision.is_answer)
        self.assertEqual(decision.fields, ("temperature",))

    def test_single_question_unrelated_fields_are_not_answer(self):
        # 实验记录：提供 volume，与问题缺失字段无关 → 不当作回答
        decision = decide_unnumbered_answer(
            pending_questions=[pending_question()],
            text="加入5毫升缓冲液",
        )
        self.assertFalse(decision.is_answer)

    def test_multiple_questions_never_answer(self):
        decision = decide_unnumbered_answer(
            pending_questions=[
                pending_question(display_number=1),
                pending_question(
                    display_number=2,
                    missing_fields=("duration",),
                ),
            ],
            text="时间为10分钟",
        )
        self.assertFalse(decision.is_answer)

    def test_no_questions_never_answer(self):
        decision = decide_unnumbered_answer(
            pending_questions=[],
            text="时间为10分钟",
        )
        self.assertFalse(decision.is_answer)

    def test_long_sentence_not_answer(self):
        decision = decide_unnumbered_answer(
            pending_questions=[pending_question()],
            text="先加入五毫升缓冲液，再加热到60摄氏度",
        )
        self.assertFalse(decision.is_answer)

    def test_compound_sentence_with_matching_field_is_not_answer(self):
        # 夹带无关字段（体积）即使包含温度也不当作回答——实验事实不吞
        decision = decide_unnumbered_answer(
            pending_questions=[pending_question()],
            text="加入5毫升缓冲液，加热到60摄氏度",
        )
        self.assertFalse(decision.is_answer)

    def test_plain_text_without_fields_not_answer(self):
        decision = decide_unnumbered_answer(
            pending_questions=[pending_question()],
            text="我不知道",
        )
        self.assertFalse(decision.is_answer)

    def test_decision_cannot_carry_fields_when_not_answer(self):
        from src.core.answer_fallback import UnnumberedAnswerDecision

        with self.assertRaisesRegex(ValueError, "非回答"):
            UnnumberedAnswerDecision(is_answer=False, fields=("duration",))


if __name__ == "__main__":
    unittest.main()
