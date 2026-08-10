import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

from src.asr.backend import ASRBackend
from src.asr.factory import create_asr_backend
from src.asr.schemas import ASRResult
from src.asr.sensevoice_backend import SenseVoiceBackend


class FakeEngine:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate(self, **kwargs):
        self.calls.append(kwargs)
        return self.result


class FakeBackend:
    def recognize(self, audio_path, *, language="auto"):
        return ASRResult(
            text="测试",
            raw_text="测试",
            audio_path=str(audio_path),
            audio_duration_seconds=1.0,
            recognition_seconds=0.1,
            model="fake",
            language=language,
        )


def write_silent_wav(path: Path) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16_000)
        output.writeframes(b"\x00\x00" * 1_600)


class ASRBackendFactoryTests(unittest.TestCase):
    def test_protocol_accepts_structural_fake(self):
        self.assertIsInstance(FakeBackend(), ASRBackend)

    def test_factory_creates_configured_sensevoice_backend(self):
        sentinel = FakeBackend()

        with patch(
            "src.asr.sensevoice_backend.SenseVoiceBackend",
            return_value=sentinel,
        ) as backend_class:
            result = create_asr_backend(" SENSEVOICE ")

        self.assertIs(result, sentinel)
        backend_class.assert_called_once_with()

    def test_factory_rejects_unknown_backend(self):
        with self.assertRaisesRegex(
            ValueError,
            "ASR_BACKEND 不受支持",
        ):
            create_asr_backend("seaco_paraformer")


class SenseVoiceBackendTests(unittest.TestCase):
    def test_converts_model_output_to_shared_result(self):
        engine = FakeEngine([
            {"text": "<|zh|>移液枪😊"},
        ])

        with tempfile.TemporaryDirectory() as directory:
            audio_path = Path(directory) / "sample.wav"
            write_silent_wav(audio_path)
            backend = SenseVoiceBackend(
                model_name="test-sensevoice",
                model_engine=engine,
                postprocess=lambda text: "移液枪",
            )

            result = backend.recognize(
                audio_path,
                language="zh",
            )

        self.assertEqual(result.text, "移液枪")
        self.assertEqual(
            result.raw_text,
            "<|zh|>移液枪😊",
        )
        self.assertEqual(result.model, "test-sensevoice")
        self.assertEqual(result.language, "zh")
        self.assertEqual(result.audio_duration_seconds, 0.1)
        self.assertEqual(len(engine.calls), 1)
        self.assertEqual(engine.calls[0]["language"], "zh")
        self.assertTrue(engine.calls[0]["use_itn"])

    def test_missing_audio_fails_before_model_call(self):
        engine = FakeEngine([{"text": "不应调用"}])
        backend = SenseVoiceBackend(
            model_engine=engine,
            postprocess=lambda text: text,
        )

        with self.assertRaises(FileNotFoundError):
            backend.recognize(Path("missing.wav"))

        self.assertEqual(engine.calls, [])

    def test_unsupported_language_fails_before_model_call(self):
        engine = FakeEngine([{"text": "不应调用"}])

        with tempfile.TemporaryDirectory() as directory:
            audio_path = Path(directory) / "sample.wav"
            write_silent_wav(audio_path)
            backend = SenseVoiceBackend(
                model_engine=engine,
                postprocess=lambda text: text,
            )

            with self.assertRaisesRegex(
                ValueError,
                "language 不受支持",
            ):
                backend.recognize(
                    audio_path,
                    language="fr",
                )

        self.assertEqual(engine.calls, [])

    def test_empty_model_result_is_explicit_failure(self):
        engine = FakeEngine([])

        with tempfile.TemporaryDirectory() as directory:
            audio_path = Path(directory) / "sample.wav"
            write_silent_wav(audio_path)
            backend = SenseVoiceBackend(
                model_engine=engine,
                postprocess=lambda text: text,
            )

            with self.assertRaisesRegex(
                RuntimeError,
                "没有返回识别结果",
            ):
                backend.recognize(audio_path)


if __name__ == "__main__":
    unittest.main()
