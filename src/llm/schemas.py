from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class ExperimentEventType(str, Enum):
    OPERATION = "operation"
    OBSERVATION = "observation"
    MEASUREMENT = "measurement"
    ANOMALY = "anomaly"
    NOTE = "note"


@dataclass
class ExperimentEntities:
    action: str | None = None
    object: str | None = None
    instrument: str | None = None
    amount_value: str | None = None
    amount_unit: str | None = None
    concentration: str | None = None
    temperature: str | None = None
    duration: str | None = None
    condition: str | None = None
    observation: str | None = None


@dataclass
class ExperimentEvent:
    event_type: ExperimentEventType
    raw_text: str
    normalized_text: str
    entities: ExperimentEntities = field(default_factory=ExperimentEntities)
    missing_fields: list[str] = field(default_factory=list)
    needs_confirmation: bool = False
    confirmation_reason: str | None = None
    source_session_id: str | None = None
    source_segment_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["event_type"] = self.event_type.value
        return data


@dataclass
class LLMAnalysisResult:
    events: list[ExperimentEvent] = field(default_factory=list)
    should_ask_follow_up: bool = False
    follow_up_question: str | None = None
    assistant_reply: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "events": [event.to_dict() for event in self.events],
            "should_ask_follow_up": self.should_ask_follow_up,
            "follow_up_question": self.follow_up_question,
            "assistant_reply": self.assistant_reply,
        }


@dataclass
class ExperimentSummary:
    summary: str
    completed_steps: list[str] = field(default_factory=list)
    key_observations: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)
    unresolved_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
