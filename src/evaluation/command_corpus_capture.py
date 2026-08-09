"""协调一次语料录音、回放、人工决策和证据保存。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Protocol

from src.evaluation.command_corpus import (
    CommandCorpusPrompt,
    RecordingAttempt,
    RecordingStatus,
    SpokenTextStatus,
)


class AudioRecorder(Protocol):
    def record_until_silence(self) -> Path: ...


class AttemptStore(Protocol):
    def append(self, attempt: RecordingAttempt) -> None: ...


class ReviewDecision(str, Enum):
    ACCEPT = "accept"
    TRUNCATED = "truncated"
    DUPLICATED = "duplicated"
    RETRY = "retry"
    SKIP = "skip"


@dataclass(frozen=True)
class CaptureOutcome:
    attempt: RecordingAttempt
    should_retry: bool


class CommandCorpusCaptureCoordinator:
    """把外部资源结果转换成稳定的录音尝试记录。"""

    def __init__(
        self,
        *,
        recorder: AudioRecorder,
        player: Callable[[Path], None],
        store: AttemptStore,
    ) -> None:
        self._recorder = recorder
        self._player = player
        self._store = store

    def capture_once(
        self,
        *,
        prompt: CommandCorpusPrompt,
        attempt_number: int,
        review: Callable[[Path], ReviewDecision],
    ) -> CaptureOutcome:
        try:
            audio_path = Path(
                self._recorder.record_until_silence()
            ).resolve()
        except Exception as error:
            attempt = RecordingAttempt.from_prompt(
                prompt,
                attempt_number=attempt_number,
                status=RecordingStatus.FAILED,
                error=f"{type(error).__name__}: {error}",
            )
            self._store.append(attempt)
            return CaptureOutcome(attempt=attempt, should_retry=False)

        try:
            self._player(audio_path)
        except Exception as error:
            attempt = RecordingAttempt.from_prompt(
                prompt,
                attempt_number=attempt_number,
                status=RecordingStatus.RETRY_REQUESTED,
                audio_path=audio_path,
                capture_note=(
                    "WAV已保存，但即时回放失败："
                    f"{type(error).__name__}: {error}"
                ),
            )
            self._store.append(attempt)
            return CaptureOutcome(attempt=attempt, should_retry=False)

        decision = review(audio_path)
        attempt = self._build_reviewed_attempt(
            prompt=prompt,
            attempt_number=attempt_number,
            audio_path=audio_path,
            decision=decision,
        )
        self._store.append(attempt)
        return CaptureOutcome(
            attempt=attempt,
            should_retry=decision == ReviewDecision.RETRY,
        )

    @staticmethod
    def _build_reviewed_attempt(
        *,
        prompt: CommandCorpusPrompt,
        attempt_number: int,
        audio_path: Path,
        decision: ReviewDecision,
    ) -> RecordingAttempt:
        if decision == ReviewDecision.ACCEPT:
            return RecordingAttempt.from_prompt(
                prompt,
                attempt_number=attempt_number,
                status=RecordingStatus.ACCEPTED,
                audio_path=audio_path,
                spoken_text=prompt.prompt_text,
                spoken_text_status=SpokenTextStatus.USER_CONFIRMED,
                capture_note="人工回听：句首完整且没有重复。",
            )

        notes = {
            ReviewDecision.TRUNCATED: "人工回听：句首被截断。",
            ReviewDecision.DUPLICATED: "人工回听：句首出现重复。",
            ReviewDecision.RETRY: "人工要求重录。",
            ReviewDecision.SKIP: "人工跳过本条；WAV仍保留。",
        }
        status = (
            RecordingStatus.SKIPPED
            if decision == ReviewDecision.SKIP
            else RecordingStatus.RETRY_REQUESTED
        )
        return RecordingAttempt.from_prompt(
            prompt,
            attempt_number=attempt_number,
            status=status,
            audio_path=audio_path,
            capture_note=notes[decision],
        )
