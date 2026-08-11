import unittest

from src.core.presentation_message import (
    DeliveryChannel,
    MessageKind,
    MessagePriority,
    MessageStatus,
    PresentationMessage,
    ScreenTarget,
    SpeechPolicy,
    VoiceDeliveryPolicy,
)


class PresentationMessageTests(unittest.TestCase):
    def test_builds_speakable_clarification(self):
        message = PresentationMessage(
            message_id="message-1",
            kind=MessageKind.CLARIFICATION,
            text="离心时间是多少？",
            priority=MessagePriority.ACTIVE_QUESTION,
            channels=(DeliveryChannel.SCREEN, DeliveryChannel.VOICE),
            screen_target=ScreenTarget.CURRENT_QUESTION,
            speech_policy=SpeechPolicy.REQUIRED,
            clarification_id="clarification-2",
            source_segment_id=2,
            requires_response=True,
            deferrable=True,
        )
        self.assertTrue(message.can_speak)
        self.assertTrue(message.deferrable)

    def test_voice_channel_requires_explicit_speech_policy(self):
        with self.assertRaises(ValueError):
            PresentationMessage(
                message_id="message-1",
                kind=MessageKind.RECORD_ACK,
                text="已记录。",
                priority=MessagePriority.ROUTINE,
                channels=(DeliveryChannel.VOICE,),
            )

    def test_speech_policy_requires_voice_channel(self):
        with self.assertRaises(ValueError):
            PresentationMessage(
                message_id="message-1",
                kind=MessageKind.RECORD_ACK,
                text="已记录。",
                priority=MessagePriority.ROUTINE,
                channels=(DeliveryChannel.SCREEN,),
                screen_target=ScreenTarget.STATUS,
                speech_policy=SpeechPolicy.ALLOWED,
            )

    def test_deferrable_message_must_require_response(self):
        with self.assertRaises(ValueError):
            PresentationMessage(
                message_id="message-1",
                kind=MessageKind.CLARIFICATION,
                text="稍后再问。",
                priority=MessagePriority.ACTIVE_QUESTION,
                channels=(DeliveryChannel.SCREEN,),
                screen_target=ScreenTarget.CURRENT_QUESTION,
                clarification_id="clarification-1",
                deferrable=True,
            )

    def test_required_response_needs_clarification_id(self):
        with self.assertRaises(ValueError):
            PresentationMessage(
                message_id="message-1",
                kind=MessageKind.CLARIFICATION,
                text="温度是多少？",
                priority=MessagePriority.ACTIVE_QUESTION,
                channels=(DeliveryChannel.SCREEN,),
                screen_target=ScreenTarget.CURRENT_QUESTION,
                requires_response=True,
            )

    def test_debug_message_cannot_leak_to_user_channels(self):
        with self.assertRaises(ValueError):
            PresentationMessage(
                message_id="debug-1",
                kind=MessageKind.DEBUG,
                text="LLM耗时2秒。",
                priority=MessagePriority.DEBUG,
                channels=(DeliveryChannel.DEBUG, DeliveryChannel.SCREEN),
            )

    def test_expired_voice_message_is_not_speakable(self):
        message = PresentationMessage(
            message_id="message-1",
            kind=MessageKind.CLARIFICATION,
            text="离心时间是多少？",
            priority=MessagePriority.ACTIVE_QUESTION,
            channels=(DeliveryChannel.SCREEN, DeliveryChannel.VOICE),
            screen_target=ScreenTarget.CURRENT_QUESTION,
            speech_policy=SpeechPolicy.REQUIRED,
            status=MessageStatus.EXPIRED,
            clarification_id="clarification-2",
            requires_response=True,
            deferrable=True,
        )
        self.assertFalse(message.can_speak)

    def test_policy_allows_ack_and_one_question_in_same_gap(self):
        policy = VoiceDeliveryPolicy()
        self.assertEqual(policy.max_messages, 2)
        self.assertEqual(policy.max_questions, 1)
        self.assertGreaterEqual(policy.max_characters, 25)

    def test_screen_message_requires_semantic_target(self):
        with self.assertRaises(ValueError):
            PresentationMessage(
                message_id="message-1",
                kind=MessageKind.RECORD_ACK,
                text="已记录。",
                priority=MessagePriority.ROUTINE,
                channels=(DeliveryChannel.SCREEN,),
            )

    def test_voice_only_message_cannot_claim_screen_target(self):
        with self.assertRaises(ValueError):
            PresentationMessage(
                message_id="message-1",
                kind=MessageKind.WAKE_ACK,
                text="我在，请说。",
                priority=MessagePriority.DIRECT_ACK,
                channels=(DeliveryChannel.VOICE,),
                screen_target=ScreenTarget.DIALOGUE,
                speech_policy=SpeechPolicy.REQUIRED,
            )


if __name__ == "__main__":
    unittest.main()
