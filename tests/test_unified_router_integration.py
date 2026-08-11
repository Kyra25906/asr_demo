import json
import unittest

from src.core.intent_policy import IntentDisposition, IntentEvidence
from src.core.interaction_command import InteractionCommandType
from src.core.unified_understanding import (
    UnifiedInputKind,
    UnifiedUnderstandingInput,
)
from src.llm.client import LLMClientError, LLMGenerationResult
from src.llm.schemas import ExperimentEventType
from src.llm.unified_processor import UnifiedUnderstandingProcessor
from src.llm.unified_router import UnifiedUnderstandingRouter


class FakeLLMClient:
    def __init__(self, content=None, error=None):
        self.content = content
        self.error = error
        self.calls = []

    def generate_json(self, *, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        if self.error is not None:
            raise self.error
        return LLMGenerationResult(self.content, 1, 0.1)


def request(text):
    return UnifiedUnderstandingInput(
        raw_text=text,
        session_active=True,
        session_id="session-1",
        segment_id=1,
        pending_question_numbers=(1, 2),
        current_question_number=2,
    )


def response(kind, branch):
    data = {
        "input_kind": kind,
        "experiment": None,
        "control": None,
        "uncertain": None,
    }
    data[kind] = branch
    return json.dumps(data, ensure_ascii=False)


def control_response(command_type, **overrides):
    intent = {
        "status": "matched",
        "command_type": command_type,
        "target_question_number": None,
        "answer_text": None,
        "reason": "Fake控制候选。",
    }
    intent.update(overrides)
    return response("control", {"intent": intent})


class UnifiedRouterIntegrationTests(unittest.TestCase):
    def build_router(self, client):
        return UnifiedUnderstandingRouter(
            UnifiedUnderstandingProcessor(client)
        )

    def test_exact_command_bypasses_entire_llm_chain(self):
        client = FakeLLMClient(error=AssertionError("不应调用LLM"))

        result = self.build_router(client).route(request("结束实验记录。"))

        self.assertEqual(client.calls, [])
        self.assertFalse(result.llm_used)
        self.assertEqual(result.decision.evidence, IntentEvidence.EXACT_RULE)
        self.assertEqual(result.decision.disposition, IntentDisposition.EXECUTE)

    def test_unmatched_control_uses_llm_and_passes_risk_policy(self):
        client = FakeLLMClient(control_response("end_session"))

        result = self.build_router(client).route(
            request("今天先记录到这里吧。")
        )

        self.assertTrue(result.llm_used)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(
            result.understanding_outcome.value.input_kind,
            UnifiedInputKind.CONTROL,
        )
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.REQUEST_CONFIRMATION,
        )
        self.assertFalse(result.decision.may_execute_now)

    def test_experiment_keeps_structured_event_and_source_identity(self):
        raw_text = "加入五毫升缓冲液。"
        analysis = {
            "events": [{
                "event_type": "operation",
                "raw_text": raw_text,
                "normalized_text": raw_text,
                "entities": {
                    "action": "加入", "object": "缓冲液",
                    "instrument": None, "amount_value": "5",
                    "amount_unit": "毫升", "concentration": None,
                    "temperature": None, "duration": None,
                    "condition": None, "observation": None,
                },
                "missing_fields": [],
                "needs_confirmation": False,
                "confirmation_reason": None,
            }],
            "should_ask_follow_up": False,
            "follow_up_question": None,
            "assistant_reply": "已记录。",
        }
        client = FakeLLMClient(response(
            "experiment", {"analysis": analysis}
        ))

        result = self.build_router(client).route(request(raw_text))

        outcome = result.understanding_outcome
        self.assertFalse(outcome.degraded)
        event = outcome.value.experiment.analysis.events[0]
        self.assertEqual(event.raw_text, raw_text)
        self.assertEqual(event.source_session_id, "session-1")
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.PASS_TO_EXPERIMENT,
        )

    def test_targeted_answer_keeps_data_but_does_not_execute(self):
        client = FakeLLMClient(control_response(
            "targeted_answer",
            target_question_number=2,
            answer_text="五分钟",
        ))

        result = self.build_router(client).route(
            request("关于第二个，是五分钟。")
        )

        intent = result.understanding_outcome.value.control.intent
        self.assertEqual(intent.target_question_number, 2)
        self.assertEqual(intent.answer_text, "五分钟")
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.DO_NOT_EXECUTE,
        )

    def test_uncertain_abstains_without_control_action(self):
        client = FakeLLMClient(response(
            "uncertain", {"reason": "语义不足。"}
        ))

        result = self.build_router(client).route(request("这个差不多了。"))

        self.assertTrue(result.llm_used)
        self.assertEqual(
            result.understanding_outcome.value.input_kind,
            UnifiedInputKind.UNCERTAIN,
        )
        self.assertEqual(
            result.decision.disposition,
            IntentDisposition.PASS_TO_EXPERIMENT,
        )
        self.assertFalse(result.decision.may_execute_now)

    def test_invalid_output_degrades_to_note_without_control_action(self):
        client = FakeLLMClient("not-json")
        raw_text = "我想看看问题。"

        result = self.build_router(client).route(request(raw_text))

        outcome = result.understanding_outcome
        self.assertTrue(outcome.degraded)
        self.assertEqual(result.raw_text, raw_text)
        self.assertIsNone(outcome.value.control)
        self.assertEqual(
            outcome.value.experiment.analysis.events[0].event_type,
            ExperimentEventType.NOTE,
        )
        self.assertFalse(result.decision.may_execute_now)

    def test_client_failure_keeps_metrics_without_control_action(self):
        client = FakeLLMClient(error=LLMClientError(
            "timeout", attempts=2, processing_seconds=3.5
        ))

        result = self.build_router(client).route(request("我想看看问题。"))

        outcome = result.understanding_outcome
        self.assertTrue(outcome.degraded)
        self.assertIsNone(outcome.value.control)
        self.assertEqual(outcome.llm_attempts, 2)
        self.assertEqual(outcome.llm_processing_seconds, 3.5)
        self.assertFalse(result.decision.may_execute_now)


if __name__ == "__main__":
    unittest.main()
