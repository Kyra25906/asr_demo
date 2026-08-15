import time
import unittest

from src.core.presentation_coordinator import PresentationCoordinator
from src.core.presentation_intent import PresentationIntent
from src.core.presentation_message import (
    MessageKind,
    MessagePriority,
    ScreenTarget,
)
from src.core.presentation_pump import PresentationPump


def _record_ack(intent_id="r", step_number=1):
    return PresentationIntent(
        intent_id=intent_id,
        kind=MessageKind.RECORD_ACK,
        args={"result": "recorded", "step_number": step_number},
        priority=MessagePriority.ROUTINE,
        screen_target=ScreenTarget.STATUS,
    )


def _wait_until(condition, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return condition()


class FakeRenderer:
    def __init__(self):
        self.rendered = []

    def render(self, intent):
        self.rendered.append(intent)
        return f"rendered:{intent.kind.value}"


class FakeOutput:
    def __init__(self):
        self.outputs = []

    def __call__(self, text):
        self.outputs.append(text)


class PresentationPumpTests(unittest.TestCase):
    def test_pump_renders_and_outputs_submitted_intents(self):
        coordinator = PresentationCoordinator()
        renderer = FakeRenderer()
        output = FakeOutput()
        pump = PresentationPump(coordinator, renderer, output)

        pump.start()
        try:
            coordinator.submit([_record_ack("r1", 1)])
            self.assertTrue(
                _wait_until(lambda: len(output.outputs) >= 1),
                "pump 未在超时内渲染并输出消息",
            )
        finally:
            pump.stop(timeout=1)

        self.assertEqual(len(renderer.rendered), 1)
        self.assertEqual(output.outputs, ["rendered:record_ack"])

    def test_pump_outputs_in_fifo_order(self):
        coordinator = PresentationCoordinator()
        renderer = FakeRenderer()
        output = FakeOutput()
        pump = PresentationPump(coordinator, renderer, output)

        pump.start()
        try:
            coordinator.submit(
                [_record_ack("r1", 1), _record_ack("r2", 2)]
            )
            self.assertTrue(
                _wait_until(lambda: len(output.outputs) >= 2),
                "pump 未在超时内输出两条消息",
            )
        finally:
            pump.stop(timeout=1)

        self.assertEqual(output.outputs, ["rendered:record_ack"] * 2)
        self.assertEqual(len(renderer.rendered), 2)

    def test_stop_stops_the_thread(self):
        coordinator = PresentationCoordinator()
        pump = PresentationPump(coordinator, FakeRenderer(), FakeOutput())

        pump.start()
        pump.stop(timeout=1)

        self.assertFalse(pump._thread.is_alive())


if __name__ == "__main__":
    unittest.main()
