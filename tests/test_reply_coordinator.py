import unittest

from src.core.reply_coordinator import ReplyCoordinator
from src.llm.schemas import (
    ExperimentEntities,
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)


def make_analysis(
    *,
    segment_id: int,
    raw_text: str,
    entities: ExperimentEntities | None = None,
    missing_fields: list[str] | None = None,
    needs_confirmation: bool = False,
    question: str | None = None,
) -> LLMAnalysisResult:
    missing_fields = missing_fields or []
    should_ask = bool(missing_fields) or needs_confirmation

    event = ExperimentEvent(
        event_type=ExperimentEventType.OPERATION,
        raw_text=raw_text,
        normalized_text=raw_text,
        entities=entities or ExperimentEntities(),
        missing_fields=missing_fields,
        needs_confirmation=needs_confirmation,
        confirmation_reason=(
            "疑似 ASR 错词" if needs_confirmation else None
        ),
        source_session_id="session_001",
        source_segment_id=segment_id,
    )

    return LLMAnalysisResult(
        events=[event],
        should_ask_follow_up=should_ask,
        follow_up_question=question if should_ask else None,
        assistant_reply=None,
    )


class ReplyCoordinatorTests(unittest.TestCase):
    def test_registers_question_with_source(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=3,
            raw_text="将溶液加热。",
            analysis=make_analysis(
                segment_id=3,
                raw_text="将溶液加热。",
                missing_fields=["temperature", "duration"],
                question="加热到多少度，需要多长时间？",
            ),
        )

        reply = coordinator.pop_next_reply()

        self.assertIsNotNone(reply)
        self.assertEqual(reply.source_segment_id, 3)
        self.assertIn("第 3 段", reply.text)
        self.assertIn("将溶液加热", reply.text)
        self.assertIn("加热到多少度", reply.text)

    def test_later_entity_partially_resolves_old_question(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=3,
            raw_text="将溶液加热。",
            analysis=make_analysis(
                segment_id=3,
                raw_text="将溶液加热。",
                missing_fields=["temperature", "duration"],
                question="加热到多少度，需要多长时间？",
            ),
        )
        coordinator.pop_next_reply()

        coordinator.ingest_analysis(
            segment_id=4,
            raw_text="温度为60摄氏度。",
            analysis=make_analysis(
                segment_id=4,
                raw_text="温度为60摄氏度。",
                entities=ExperimentEntities(temperature="60摄氏度"),
            ),
        )

        active = coordinator.active_clarifications()
        reply = coordinator.pop_next_reply()

        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].missing_fields, ("duration",))
        self.assertIsNotNone(reply)
        self.assertIn("仍需确认：时间", reply.text)
        self.assertNotIn("温度、时间", reply.text)

    def test_later_entities_fully_resolve_old_question(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=3,
            raw_text="将溶液加热。",
            analysis=make_analysis(
                segment_id=3,
                raw_text="将溶液加热。",
                missing_fields=["temperature", "duration"],
                question="加热到多少度，需要多长时间？",
            ),
        )
        coordinator.pop_next_reply()

        coordinator.ingest_analysis(
            segment_id=4,
            raw_text="在60摄氏度加热十分钟。",
            analysis=make_analysis(
                segment_id=4,
                raw_text="在60摄氏度加热十分钟。",
                entities=ExperimentEntities(
                    temperature="60摄氏度",
                    duration="10分钟",
                ),
            ),
        )

        self.assertEqual(coordinator.active_clarifications(), ())
        self.assertIsNone(coordinator.pop_next_reply())

    def test_unrelated_entity_does_not_resolve_question(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=1,
            raw_text="加入缓冲液。",
            analysis=make_analysis(
                segment_id=1,
                raw_text="加入缓冲液。",
                missing_fields=["amount_unit"],
                question="加入量使用什么单位？",
            ),
        )
        coordinator.pop_next_reply()

        coordinator.ingest_analysis(
            segment_id=2,
            raw_text="温度为25摄氏度。",
            analysis=make_analysis(
                segment_id=2,
                raw_text="温度为25摄氏度。",
                entities=ExperimentEntities(temperature="25摄氏度"),
            ),
        )

        active = coordinator.active_clarifications()
        self.assertEqual(active[0].missing_fields, ("amount_unit",))
        self.assertIsNone(coordinator.pop_next_reply())

    def test_asr_confirmation_stays_active(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=7,
            raw_text="使用一液枪吸取500微生样品。",
            analysis=make_analysis(
                segment_id=7,
                raw_text="使用一液枪吸取500微生样品。",
                needs_confirmation=True,
                question="请确认是否为移液枪和500微升？",
            ),
        )

        reply = coordinator.pop_next_reply()
        active = coordinator.active_clarifications()

        self.assertIsNotNone(reply)
        self.assertIn("第 7 段", reply.text)
        self.assertEqual(len(active), 1)
        self.assertTrue(active[0].requires_confirmation)

    def test_pop_returns_at_most_one_reply(self):
        coordinator = ReplyCoordinator()

        for segment_id in (1, 2):
            raw_text = f"第{segment_id}段。"
            coordinator.ingest_analysis(
                segment_id=segment_id,
                raw_text=raw_text,
                analysis=make_analysis(
                    segment_id=segment_id,
                    raw_text=raw_text,
                    missing_fields=["duration"],
                    question="持续多长时间？",
                ),
            )

        first = coordinator.pop_next_reply()
        second = coordinator.pop_next_reply()
        third = coordinator.pop_next_reply()

        self.assertEqual(first.source_segment_id, 1)
        self.assertEqual(second.source_segment_id, 2)
        self.assertIsNone(third)

    def test_invalid_follow_up_is_rejected(self):
        coordinator = ReplyCoordinator()
        invalid_analysis = make_analysis(
            segment_id=1,
            raw_text="加热。",
            missing_fields=["temperature"],
            question="临时问题",
        )
        invalid_analysis.follow_up_question = None

        with self.assertRaises(ValueError):
            coordinator.ingest_analysis(
                segment_id=1,
                raw_text="加热。",
                analysis=invalid_analysis,
            )

    def test_degraded_note_does_not_create_false_question(self):
        coordinator = ReplyCoordinator()
        raw_text = "模型失败时保留的ASR原文。"
        degraded_analysis = LLMAnalysisResult(
            events=[
                ExperimentEvent(
                    event_type=ExperimentEventType.NOTE,
                    raw_text=raw_text,
                    normalized_text=raw_text,
                    source_session_id="session_001",
                    source_segment_id=1,
                )
            ],
            should_ask_follow_up=False,
            follow_up_question=None,
            assistant_reply=None,
        )

        coordinator.ingest_analysis(
            segment_id=1,
            raw_text=raw_text,
            analysis=degraded_analysis,
        )

        self.assertEqual(coordinator.active_clarifications(), ())
        self.assertIsNone(coordinator.pop_next_reply())

    def test_affirmative_answer_resolves_asr_confirmation(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=7,
            raw_text="使用一液枪吸取500微生样品。",
            analysis=make_analysis(
                segment_id=7,
                raw_text="使用一液枪吸取500微生样品。",
                needs_confirmation=True,
                question="请确认是否为移液枪和500微升？",
            ),
        )

        resolution = coordinator.try_confirm_oldest(
            segment_id=8,
            raw_text="是的，是移液枪和500微升。",
        )

        self.assertIsNotNone(resolution)
        self.assertTrue(resolution.fully_resolved)
        self.assertEqual(resolution.source_segment_id, 7)
        self.assertEqual(resolution.answer_segment_id, 8)
        self.assertEqual(coordinator.active_clarifications(), ())

    def test_negative_answer_does_not_close_confirmation(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=1,
            raw_text="使用一液枪。",
            analysis=make_analysis(
                segment_id=1,
                raw_text="使用一液枪。",
                needs_confirmation=True,
                question="请确认是否为移液枪？",
            ),
        )

        resolution = coordinator.try_confirm_oldest(
            segment_id=2,
            raw_text="不是。",
        )

        self.assertIsNone(resolution)
        self.assertEqual(len(coordinator.active_clarifications()), 1)

    def test_normal_operation_starting_with_dui_is_not_confirmation(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=1,
            raw_text="使用一液枪。",
            analysis=make_analysis(
                segment_id=1,
                raw_text="使用一液枪。",
                needs_confirmation=True,
                question="请确认是否为移液枪？",
            ),
        )

        resolution = coordinator.try_confirm_oldest(
            segment_id=2,
            raw_text="对溶液继续加热。",
        )

        self.assertIsNone(resolution)
        self.assertEqual(len(coordinator.active_clarifications()), 1)

    def test_only_oldest_asr_confirmation_is_closed(self):
        coordinator = ReplyCoordinator()

        for segment_id in (1, 2):
            raw_text = f"第{segment_id}段疑似错词。"
            coordinator.ingest_analysis(
                segment_id=segment_id,
                raw_text=raw_text,
                analysis=make_analysis(
                    segment_id=segment_id,
                    raw_text=raw_text,
                    needs_confirmation=True,
                    question="请确认该错词？",
                ),
            )

        resolution = coordinator.try_confirm_oldest(
            segment_id=3,
            raw_text="确认。",
        )

        self.assertEqual(resolution.source_segment_id, 1)
        active = coordinator.active_clarifications()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].source_segment_id, 2)

    def test_confirmation_keeps_other_missing_fields_active(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=1,
            raw_text="使用一液枪加热样品。",
            analysis=make_analysis(
                segment_id=1,
                raw_text="使用一液枪加热样品。",
                missing_fields=["duration"],
                needs_confirmation=True,
                question="请确认移液枪，并补充加热时间。",
            ),
        )

        resolution = coordinator.try_confirm_oldest(
            segment_id=2,
            raw_text="是的，是移液枪。",
        )

        self.assertFalse(resolution.fully_resolved)
        self.assertEqual(resolution.remaining_fields, ("duration",))
        active = coordinator.active_clarifications()
        self.assertFalse(active[0].requires_confirmation)
        self.assertEqual(active[0].missing_fields, ("duration",))

    def test_prepare_confirmation_does_not_change_state(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=1,
            raw_text="使用一液枪。",
            analysis=make_analysis(
                segment_id=1,
                raw_text="使用一液枪。",
                needs_confirmation=True,
                question="请确认是否为移液枪？",
            ),
        )

        prepared = coordinator.prepare_confirmation(
            segment_id=2,
            raw_text="是的。",
        )

        self.assertIsNotNone(prepared)
        active = coordinator.active_clarifications()
        self.assertEqual(len(active), 1)
        self.assertTrue(active[0].requires_confirmation)

        resolution = coordinator.commit_confirmation(prepared)

        self.assertTrue(resolution.fully_resolved)
        self.assertEqual(coordinator.active_clarifications(), ())

    def test_stale_confirmation_plan_is_rejected(self):
        coordinator = ReplyCoordinator()
        coordinator.ingest_analysis(
            segment_id=1,
            raw_text="使用一液枪。",
            analysis=make_analysis(
                segment_id=1,
                raw_text="使用一液枪。",
                needs_confirmation=True,
                question="请确认是否为移液枪？",
            ),
        )
        prepared = coordinator.prepare_confirmation(
            segment_id=2,
            raw_text="是的。",
        )
        coordinator.commit_confirmation(prepared)

        with self.assertRaises(ValueError):
            coordinator.commit_confirmation(prepared)


if __name__ == "__main__":
    unittest.main()
