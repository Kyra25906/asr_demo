import unittest

from src.core.unified_dispatch import (
    UnifiedDispatchDestination,
    UnifiedDispatchPlanner,
)
from src.core.unified_understanding import (
    ExperimentUnderstanding,
    UnifiedUnderstandingInput,
    UnifiedUnderstandingResult,
    UncertainUnderstanding,
    build_degraded_understanding,
)
from src.llm.processor import ProcessOutcome
from src.llm.schemas import LLMAnalysisResult
from src.llm.unified_router import UnifiedUnderstandingRouter


class FakeUnderstandingProcessor:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def understand(self, request):
        self.calls.append(request)
        return self.outcome


def request(raw_text):
    return UnifiedUnderstandingInput(
        raw_text=raw_text,
        session_active=True,
        session_id="session-1",
        segment_id=1,
        pending_question_numbers=(1,),
        current_question_number=1,
    )


class UnifiedDispatchIntegrationTests(unittest.TestCase):
    def test_exact_end_routes_then_forms_execution_candidate(self):
        processor = FakeUnderstandingProcessor(
            AssertionError("精确路径不应调用Processor")
        )
        router = UnifiedUnderstandingRouter(processor)

        route_result = router.route(request("结束实验记录。"))
        plan = UnifiedDispatchPlanner.plan(route_result)

        self.assertEqual(processor.calls, [])
        self.assertEqual(
            plan.destination,
            UnifiedDispatchDestination.END_SESSION_EXECUTION,
        )

    def test_experiment_route_flows_to_experiment_destination(self):
        raw_text = "加入五毫升缓冲液。"
        understanding = UnifiedUnderstandingResult(
            raw_text=raw_text,
            experiment=ExperimentUnderstanding(
                LLMAnalysisResult(events=[])
            ),
        )
        processor = FakeUnderstandingProcessor(
            ProcessOutcome(value=understanding)
        )

        route_result = UnifiedUnderstandingRouter(processor).route(
            request(raw_text)
        )
        plan = UnifiedDispatchPlanner.plan(route_result)

        self.assertEqual(len(processor.calls), 1)
        self.assertEqual(
            plan.destination,
            UnifiedDispatchDestination.EXPERIMENT_PIPELINE,
        )

    def test_uncertain_route_flows_to_abstention(self):
        raw_text = "这个差不多了。"
        understanding = UnifiedUnderstandingResult(
            raw_text=raw_text,
            uncertain=UncertainUnderstanding("证据不足。"),
        )
        processor = FakeUnderstandingProcessor(
            ProcessOutcome(value=understanding)
        )

        route_result = UnifiedUnderstandingRouter(processor).route(
            request(raw_text)
        )
        plan = UnifiedDispatchPlanner.plan(route_result)

        self.assertEqual(
            plan.destination,
            UnifiedDispatchDestination.ABSTENTION,
        )

    def test_degraded_route_flows_to_note_not_normal_experiment(self):
        raw_text = "我想看看问题。"
        degraded = build_degraded_understanding(
            raw_text=raw_text,
            session_id="session-1",
            segment_id=1,
            reason="timeout",
        )
        processor = FakeUnderstandingProcessor(ProcessOutcome(
            value=degraded,
            degraded=True,
            error="timeout",
        ))

        route_result = UnifiedUnderstandingRouter(processor).route(
            request(raw_text)
        )
        plan = UnifiedDispatchPlanner.plan(route_result)

        self.assertEqual(
            plan.destination,
            UnifiedDispatchDestination.DEGRADED_NOTE,
        )


if __name__ == "__main__":
    unittest.main()
