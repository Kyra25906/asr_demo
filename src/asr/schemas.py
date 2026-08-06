from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class ASRResult:
    text: str
    raw_text: str
    audio_path: str
    audio_duration_seconds: float
    recognition_seconds: float
    model: str
    language: str
    is_final: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)