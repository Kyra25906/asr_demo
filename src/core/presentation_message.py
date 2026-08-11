from dataclasses import dataclass
from enum import Enum, IntEnum


class MessageKind(str, Enum):
    """消息表达的业务含义，而不是界面颜色或控件类型。"""

    WAKE_ACK = "wake_ack"
    TRANSCRIPT = "transcript"
    RECORD_ACK = "record_ack"
    CONFIRMATION_ACK = "confirmation_ack"
    CLARIFICATION = "clarification"
    CLARIFICATION_DEFERRED = "clarification_deferred"
    CLARIFICATION_REVIEW = "clarification_review"
    SAFETY_ALERT = "safety_alert"
    SYSTEM_ISSUE = "system_issue"
    STAGE_SUMMARY = "stage_summary"
    SESSION_SUMMARY = "session_summary"
    DEBUG = "debug"


class MessagePriority(IntEnum):
    """数值越小，越应该优先交给用户。"""

    CRITICAL = 0
    DIRECT_ACK = 10
    ACTIVE_QUESTION = 20
    REVIEW = 30
    SUMMARY = 40
    ROUTINE = 50
    DEBUG = 100


class DeliveryChannel(str, Enum):
    """消息允许到达的输出渠道。"""

    SCREEN = "screen"
    VOICE = "voice"
    DEBUG = "debug"


class ScreenTarget(str, Enum):
    """前端的语义区域；具体颜色和布局仍由前端决定。"""

    DIALOGUE = "dialogue"
    CURRENT_QUESTION = "current_question"
    RECORD_TIMELINE = "record_timeline"
    STATUS = "status"
    ALERT = "alert"
    SUMMARY = "summary"


class SpeechPolicy(str, Enum):
    """TTS 对这条消息的处理要求。"""

    NEVER = "never"
    ALLOWED = "allowed"
    REQUIRED = "required"


class MessageStatus(str, Enum):
    """展示消息自身的生命周期，不代替待确认项的业务状态。"""

    QUEUED = "queued"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass(frozen=True)
class PresentationMessage:
    """业务模块交给屏幕、TTS 或记录层的统一消息。"""

    message_id: str
    kind: MessageKind
    text: str
    priority: MessagePriority
    channels: tuple[DeliveryChannel, ...]
    screen_target: ScreenTarget | None = None
    speech_policy: SpeechPolicy = SpeechPolicy.NEVER
    status: MessageStatus = MessageStatus.QUEUED
    source_segment_id: int | None = None
    clarification_id: str | None = None
    conversation_group_id: str | None = None
    requires_response: bool = False
    deferrable: bool = False

    def __post_init__(self) -> None:
        if not self.message_id.strip():
            raise ValueError("message_id 不能为空。")
        if not self.text.strip():
            raise ValueError("text 不能为空。")
        if not self.channels:
            raise ValueError("channels 至少包含一个输出渠道。")
        if len(self.channels) != len(set(self.channels)):
            raise ValueError("channels 不得重复。")
        if DeliveryChannel.SCREEN in self.channels:
            if self.screen_target is None:
                raise ValueError("SCREEN 消息必须指定 screen_target。")
        elif self.screen_target is not None:
            raise ValueError("非 SCREEN 消息不能指定 screen_target。")
        if self.source_segment_id is not None and self.source_segment_id <= 0:
            raise ValueError("source_segment_id 必须大于 0。")
        if self.speech_policy != SpeechPolicy.NEVER:
            if DeliveryChannel.VOICE not in self.channels:
                raise ValueError("允许 TTS 的消息必须包含 VOICE 渠道。")
        elif DeliveryChannel.VOICE in self.channels:
            raise ValueError("包含 VOICE 渠道时必须声明 TTS 策略。")
        if self.requires_response and not self.clarification_id:
            raise ValueError("需要回答的消息必须关联 clarification_id。")
        if self.deferrable and not self.requires_response:
            raise ValueError("只有需要回答的消息才能被暂缓。")
        if self.kind == MessageKind.DEBUG:
            if self.channels != (DeliveryChannel.DEBUG,):
                raise ValueError("DEBUG 消息只能进入 DEBUG 渠道。")
            if self.speech_policy != SpeechPolicy.NEVER:
                raise ValueError("DEBUG 消息不能由 TTS 朗读。")

    @property
    def can_speak(self) -> bool:
        return (
            self.status == MessageStatus.QUEUED
            and DeliveryChannel.VOICE in self.channels
            and self.speech_policy != SpeechPolicy.NEVER
        )


@dataclass(frozen=True)
class VoiceDeliveryPolicy:
    """一次安全间隔的语音认知负担预算，而不是单消息限制。"""

    max_messages: int = 2
    max_characters: int = 50
    max_questions: int = 1

    def __post_init__(self) -> None:
        if self.max_messages <= 0:
            raise ValueError("max_messages 必须大于 0。")
        if self.max_characters <= 0:
            raise ValueError("max_characters 必须大于 0。")
        if self.max_questions <= 0:
            raise ValueError("max_questions 必须大于 0。")
