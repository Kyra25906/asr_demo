import json
import unittest

from scripts.compare_intent_architectures import (
    FIXED_TEXT,
    build_unified_user_prompt,
    parse_unified_response,
)


class IntentArchitectureComparisonTests(unittest.TestCase):
    def test_user_prompt_contains_only_fixed_synthetic_input(self):
        payload = json.loads(build_unified_user_prompt(FIXED_TEXT))

        self.assertEqual(payload["current_asr_raw_text"], FIXED_TEXT)
        self.assertEqual(payload["recent_context"], [])

    def test_parses_strict_experiment_response(self):
        analysis = {
            "events": [{
                "event_type": "operation",
                "raw_text": FIXED_TEXT,
                "normalized_text": FIXED_TEXT,
                "entities": {
                    "action": "加入",
                    "object": "缓冲液",
                    "instrument": None,
                    "amount_value": "5",
                    "amount_unit": "毫升",
                    "concentration": None,
                    "temperature": None,
                    "duration": None,
                    "condition": None,
                    "observation": None,
                },
                "missing_fields": [],
                "needs_confirmation": False,
                "confirmation_reason": None,
            }],
            "should_ask_follow_up": False,
            "follow_up_question": None,
            "assistant_reply": "已记录。",
        }
        content = json.dumps({
            "input_kind": "experiment",
            "intent": None,
            "analysis": analysis,
        }, ensure_ascii=False)

        result = parse_unified_response(
            content,
            raw_text=FIXED_TEXT,
            segment_id=1,
        )

        self.assertEqual(result.input_kind, "experiment")
        self.assertEqual(result.event_count, 1)

    def test_rejects_mixed_or_extra_top_level_fields(self):
        for data in (
            {
                "input_kind": "experiment",
                "intent": {},
                "analysis": {},
            },
            {
                "input_kind": "uncertain",
                "intent": {},
                "analysis": None,
                "execute_now": True,
            },
        ):
            with self.subTest(data=data):
                with self.assertRaises(ValueError):
                    parse_unified_response(
                        json.dumps(data),
                        raw_text=FIXED_TEXT,
                        segment_id=1,
                    )


if __name__ == "__main__":
    unittest.main()
