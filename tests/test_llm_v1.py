import json
import unittest

from src.llm.processor import (
    ExperimentLLMProcessor,
)
from src.llm.schemas import (
    ExperimentEventType,
)
from src.llm.client import (
    LLMGenerationResult,
)

def make_valid_analysis(
    raw_text: str,
) -> str:
    """
    构造一份满足当前 LLM 输出协议的 JSON。

    测试重点不是模型理解能力，
    而是处理器和校验器能否正确工作。
    """

    data = {
        "events": [
            {
                "event_type": "operation",
                "raw_text": raw_text,
                "normalized_text": (
                    "使用移液枪加入"
                    "500微升缓冲液。"
                ),
                "entities": {
                    "action": "加入",
                    "object": "缓冲液",
                    "instrument": "移液枪",
                    "amount_value": "500",
                    "amount_unit": "微升",
                    "concentration": None,
                    "temperature": None,
                    "duration": None,
                    "condition": None,
                    "observation": None,
                },
                "missing_fields": [],
                "needs_confirmation": False,
                "confirmation_reason": None,
            }
        ],
        "should_ask_follow_up": False,
        "follow_up_question": None,
        "assistant_reply": "已记录。",
    }

    return json.dumps(
        data,
        ensure_ascii=False,
    )


def make_follow_up_analysis(
    raw_text: str,
) -> str:
    """
    构造一份缺少单位、
    需要向用户追问的合法结果。
    """

    data = {
        "events": [
            {
                "event_type": "operation",
                "raw_text": raw_text,
                "normalized_text": (
                    "加入500缓冲液。"
                ),
                "entities": {
                    "action": "加入",
                    "object": "缓冲液",
                    "instrument": None,
                    "amount_value": "500",
                    "amount_unit": None,
                    "concentration": None,
                    "temperature": None,
                    "duration": None,
                    "condition": None,
                    "observation": None,
                },
                "missing_fields": [
                    "amount_unit"
                ],
                "needs_confirmation": False,
                "confirmation_reason": None,
            }
        ],
        "should_ask_follow_up": True,
        "follow_up_question": (
            "加入500什么单位的缓冲液？"
        ),
        "assistant_reply": None,
    }

    return json.dumps(
        data,
        ensure_ascii=False,
    )


class FakeClient:
    """
    测试用模型客户端。

    它不访问网络，只返回预设文本
    或主动抛出预设异常。
    """

    def __init__(
        self,
        response=None,
        error=None,
    ):
        self.response = response
        self.error = error

        self.system_prompt = None
        self.user_prompt = None

    def generate_json(
        self,
        *,
        system_prompt,
        user_prompt,
    ):
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt

        if self.error is not None:
            raise self.error

        return LLMGenerationResult(
            content=self.response,
            attempts=1,
            processing_seconds=0.123,
        )

class LLMV1Tests(
    unittest.TestCase
):
    def test_accepts_valid_output_and_injects_source(
        self,
    ):
        """
        合法输出应通过校验，
        来源编号应由程序注入。
        """

        raw_text = (
            "使用移液枪加入"
            "500微升缓冲液。"
        )

        client = FakeClient(
            response=make_valid_analysis(
                raw_text
            )
        )

        processor = (
            ExperimentLLMProcessor(
                client=client
            )
        )

        outcome = (
            processor.analyze_segment(
                raw_text=raw_text,
                session_id="session_001",
                segment_id=3,
                context=(
                    "已经准备离心管。",
                ),
            )
        )

        self.assertFalse(
            outcome.degraded
        )
        self.assertIsNone(
            outcome.error
        )

        self.assertEqual(
            len(outcome.value.events),
            1,
        )

        event = outcome.value.events[0]

        self.assertEqual(
            event.event_type,
            ExperimentEventType.OPERATION,
        )
        self.assertEqual(
            event.raw_text,
            raw_text,
        )
        self.assertEqual(
            event.source_session_id,
            "session_001",
        )
        self.assertEqual(
            event.source_segment_id,
            3,
        )
        self.assertEqual(
            outcome.llm_attempts,
            1,
        )

        self.assertEqual(
            outcome.llm_processing_seconds,
            0.123,
        )

    def test_rejects_changed_raw_text_and_falls_back(
        self,
    ):
        """
        模型擅自修改 ASR 原文时，
        整份结果必须被拒绝并降级。
        """

        actual_raw_text = (
            "使用营业枪加入"
            "500微升缓冲液。"
        )

        changed_raw_text = (
            "使用移液枪加入"
            "500微升缓冲液。"
        )

        client = FakeClient(
            response=make_valid_analysis(
                changed_raw_text
            )
        )

        processor = (
            ExperimentLLMProcessor(
                client=client
            )
        )

        outcome = (
            processor.analyze_segment(
                raw_text=actual_raw_text,
                session_id="session_001",
                segment_id=1,
            )
        )

        self.assertTrue(
            outcome.degraded
        )
        self.assertIsNotNone(
            outcome.error
        )

        event = outcome.value.events[0]

        self.assertEqual(
            event.event_type,
            ExperimentEventType.NOTE,
        )
        self.assertEqual(
            event.raw_text,
            actual_raw_text,
        )
        self.assertEqual(
            event.normalized_text,
            actual_raw_text,
        )

    def test_rejects_extra_field(
        self,
    ):
        """
        模型输出未知字段时必须拒绝，
        防止协议悄悄发生变化。
        """

        raw_text = "记录温度。"

        data = json.loads(
            make_valid_analysis(
                raw_text
            )
        )

        data["unexpected"] = True

        client = FakeClient(
            response=json.dumps(
                data,
                ensure_ascii=False,
            )
        )

        processor = (
            ExperimentLLMProcessor(
                client=client
            )
        )

        outcome = (
            processor.analyze_segment(
                raw_text=raw_text,
                session_id="session_001",
                segment_id=1,
            )
        )

        self.assertTrue(
            outcome.degraded
        )
        self.assertIsNotNone(
            outcome.error
        )
        self.assertIn(
            "额外",
            outcome.error,
        )

    def test_client_error_falls_back_without_losing_raw_text(
        self,
    ):
        """
        模型超时或网络失败时，
        ASR 原文仍必须被保留。
        """

        raw_text = "溶液变成蓝色。"

        client = FakeClient(
            error=TimeoutError(
                "模拟模型超时"
            )
        )

        processor = (
            ExperimentLLMProcessor(
                client=client
            )
        )

        outcome = (
            processor.analyze_segment(
                raw_text=raw_text,
                session_id="session_002",
                segment_id=4,
            )
        )

        self.assertTrue(
            outcome.degraded
        )
        self.assertIsNotNone(
            outcome.error
        )
        self.assertIn(
            "TimeoutError",
            outcome.error,
        )

        event = outcome.value.events[0]

        self.assertEqual(
            event.raw_text,
            raw_text,
        )
        self.assertEqual(
            event.normalized_text,
            raw_text,
        )
        self.assertEqual(
            event.source_session_id,
            "session_002",
        )
        self.assertEqual(
            event.source_segment_id,
            4,
        )
        self.assertEqual(
            outcome.llm_attempts,
            0,
        )

        self.assertEqual(
            outcome.llm_processing_seconds,
            0.0,
        )

    def test_context_is_sent_to_model(
        self,
    ):
        """
        最近上下文必须进入用户提示词，
        供模型理解“然后”等指代。
        """

        raw_text = "然后静置十分钟。"

        client = FakeClient(
            response=make_valid_analysis(
                raw_text
            )
        )

        processor = (
            ExperimentLLMProcessor(
                client=client
            )
        )

        processor.analyze_segment(
            raw_text=raw_text,
            session_id="session_001",
            segment_id=2,
            context=(
                "向离心管加入缓冲液。",
            ),
        )

        self.assertIsNotNone(
            client.user_prompt
        )
        self.assertIn(
            "向离心管加入缓冲液",
            client.user_prompt,
        )
        self.assertIn(
            raw_text,
            client.user_prompt,
        )

    def test_accepts_consistent_follow_up(
        self,
    ):
        """
        缺少单位时，
        缺失字段、追问标志和问题文本
        互相一致，应通过校验。
        """

        raw_text = "加入500缓冲液。"

        client = FakeClient(
            response=make_follow_up_analysis(
                raw_text
            )
        )

        processor = (
            ExperimentLLMProcessor(
                client=client
            )
        )

        outcome = (
            processor.analyze_segment(
                raw_text=raw_text,
                session_id="session_003",
                segment_id=1,
            )
        )

        self.assertFalse(
            outcome.degraded
        )
        self.assertTrue(
            outcome.value.should_ask_follow_up
        )
        self.assertEqual(
            outcome.value.follow_up_question,
            "加入500什么单位的缓冲液？",
        )
        self.assertEqual(
            outcome.value.events[
                0
            ].missing_fields,
            ["amount_unit"],
        )

    def test_rejects_inconsistent_follow_up(
        self,
    ):
        """
        事件声明缺少单位，
        却把 should_ask_follow_up 设为 false，
        必须拒绝。
        """

        raw_text = "加入500缓冲液。"

        data = json.loads(
            make_follow_up_analysis(
                raw_text
            )
        )

        data[
            "should_ask_follow_up"
        ] = False

        data[
            "follow_up_question"
        ] = None

        client = FakeClient(
            response=json.dumps(
                data,
                ensure_ascii=False,
            )
        )

        processor = (
            ExperimentLLMProcessor(
                client=client
            )
        )

        outcome = (
            processor.analyze_segment(
                raw_text=raw_text,
                session_id="session_003",
                segment_id=1,
            )
        )

        self.assertTrue(
            outcome.degraded
        )
        self.assertIsNotNone(
            outcome.error
        )
        self.assertIn(
            "追问标志",
            outcome.error,
        )

    def test_accepts_valid_summary(
        self,
    ):
        """
        合法的阶段总结应转换成
        ExperimentSummary。
        """

        response = json.dumps(
            {
                "summary": (
                    "已完成缓冲液加入。"
                ),
                "completed_steps": [
                    "向离心管加入缓冲液"
                ],
                "key_observations": [],
                "anomalies": [],
                "unresolved_questions": [],
            },
            ensure_ascii=False,
        )

        client = FakeClient(
            response=response
        )

        processor = (
            ExperimentLLMProcessor(
                client=client
            )
        )

        outcome = processor.summarize(
            event_records=[],
            scope="stage",
        )

        self.assertFalse(
            outcome.degraded
        )
        self.assertEqual(
            outcome.value.summary,
            "已完成缓冲液加入。",
        )
        self.assertEqual(
            outcome.value.completed_steps,
            [
                "向离心管加入缓冲液"
            ],
        )

    def test_invalid_summary_falls_back(
        self,
    ):
        """
        总结 JSON 非法时，
        已有实验事件不受影响，
        返回明确的降级总结。
        """

        client = FakeClient(
            response="不是 JSON"
        )

        processor = (
            ExperimentLLMProcessor(
                client=client
            )
        )

        outcome = processor.summarize(
            event_records=[],
            scope="session",
        )

        self.assertTrue(
            outcome.degraded
        )
        self.assertIsNotNone(
            outcome.error
        )
        self.assertIn(
            "总结暂时不可用",
            outcome.value.summary,
        )


if __name__ == "__main__":
    unittest.main()