"""运行一轮可恢复的固定语料采集会话。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.evaluation.command_corpus import (
    CommandCorpusPrompt,
    RecordingStatus,
)
from src.evaluation.command_corpus_capture import (
    CaptureOutcome,
    CommandCorpusCaptureCoordinator,
    ReviewDecision,
)
from src.evaluation.command_corpus_plan import (
    CommandCorpusPlan,
    load_capture_progress,
)


@dataclass(frozen=True)
class CaptureSessionSummary:
    total_prompts: int
    completed_before: int
    newly_completed: int
    completed_after: int
    remaining_prompts: int


class CommandCorpusCaptureSession:
    """遍历未完成提示，并在每次追加记录后重新形成可恢复进度。"""

    def __init__(
        self,
        *,
        plan: CommandCorpusPlan,
        attempts_path: Path,
        coordinator: CommandCorpusCaptureCoordinator,
    ) -> None:
        self._plan = plan
        self._attempts_path = Path(attempts_path)
        self._coordinator = coordinator

    def run(
        self,
        *,
        before_capture: Callable[[CommandCorpusPrompt, int, int, int], None],
        review: Callable[[CommandCorpusPrompt, Path], ReviewDecision],
        retry_after_problem: Callable[[CaptureOutcome], bool],
    ) -> CaptureSessionSummary:
        initial = load_capture_progress(self._plan, self._attempts_path)
        completed_before = len(initial.completed_sample_ids)
        pending_total = len(initial.pending_prompts)
        next_numbers = dict(initial.next_attempt_numbers)

        for position, prompt in enumerate(
            initial.pending_prompts,
            start=1,
        ):
            while True:
                attempt_number = next_numbers[prompt.sample_id]
                before_capture(
                    prompt,
                    attempt_number,
                    position,
                    pending_total,
                )
                outcome = self._coordinator.capture_once(
                    prompt=prompt,
                    attempt_number=attempt_number,
                    review=lambda path, current=prompt: review(
                        current,
                        path,
                    ),
                )
                next_numbers[prompt.sample_id] = attempt_number + 1

                if outcome.should_retry:
                    continue
                if (
                    outcome.attempt.status
                    in {
                        RecordingStatus.FAILED,
                        RecordingStatus.RETRY_REQUESTED,
                    }
                    and retry_after_problem(outcome)
                ):
                    continue
                break

        final = load_capture_progress(self._plan, self._attempts_path)
        completed_after = len(final.completed_sample_ids)
        return CaptureSessionSummary(
            total_prompts=len(self._plan.prompts),
            completed_before=completed_before,
            newly_completed=completed_after - completed_before,
            completed_after=completed_after,
            remaining_prompts=len(final.pending_prompts),
        )
