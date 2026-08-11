from enum import Enum


class AssistantState(str, Enum):
    IDLE = "idle"
    SESSION_ACTIVE = "session_active"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"