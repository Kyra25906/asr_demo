import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import numpy as np

from src.audio.vad_recorder import VadAudioRecorder


class FakeSegment:
    def __init__(self, *, samples, start):
        self.samples = np.array(samples, dtype=np.float32)
        self.start = start


class FakeVad:
    def __init__(self, *, speech_on_read, ready_on_read, segment):
        self.speech_on_read = speech_on_read
        self.ready_on_read = ready_on_read
        self.segment = segment
        self.read_count = 0
        self.reset_count = 0
        self.pop_count = 0

    def reset(self):
        self.reset_count += 1
        self.read_count = 0

    def accept_waveform(self, samples):
        self.read_count += 1

    def is_speech_detected(self):
        return self.read_count >= self.speech_on_read

    def empty(self):
        return self.read_count < self.ready_on_read

    @property
    def front(self):
        if isinstance(self.segment, list):
            return self.segment[self.pop_count]
        return self.segment

    def pop(self):
        self.pop_count += 1


class FakeInputStream:
    def __init__(self, chunks, *, events=None):
        self._chunks = iter(chunks)
        self._events = events

    def __enter__(self):
        if self._events is not None:
            self._events.append("stream_entered")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self, sample_count):
        return next(self._chunks), False


class VadAudioRecorderPreRollTests(unittest.TestCase):
    def test_freezes_pre_roll_at_trigger_and_writes_assembled_audio(self):
        vad = FakeVad(
            speech_on_read=2,
            ready_on_read=3,
            segment=FakeSegment(samples=[3, 4, 5, 6], start=2),
        )
        chunks = [
            np.array([[1], [2]], dtype=np.float32),
            np.array([[3], [4]], dtype=np.float32),
            np.array([[5], [6]], dtype=np.float32),
        ]
        writes = []

        with tempfile.TemporaryDirectory() as directory:
            recorder = VadAudioRecorder(
                start_timeout_seconds=10,
                pre_roll_seconds=4 / 16_000,
                vad=vad,
                input_stream_factory=lambda **kwargs: FakeInputStream(
                    chunks
                ),
                audio_writer=lambda *args, **kwargs: writes.append(
                    (args, kwargs)
                ),
                clock=lambda: 0.0,
                now=lambda: datetime(2026, 8, 9, 12, 0, 0),
                recordings_dir=Path(directory),
            )

            output_path = recorder.record_until_silence()

        self.assertEqual(output_path.name, "vad_segment_20260809_120000_000000.wav")
        self.assertEqual(len(writes), 1)
        np.testing.assert_array_equal(
            writes[0][0][1],
            np.array([1, 2, 3, 4, 5, 6], dtype=np.float32),
        )
        self.assertEqual(vad.pop_count, 1)
        self.assertEqual(vad.reset_count, 2)

    def test_timeout_resets_vad_and_does_not_write_audio(self):
        vad = FakeVad(
            speech_on_read=99,
            ready_on_read=99,
            segment=FakeSegment(samples=[1], start=0),
        )
        times = iter([0.0, 2.0])
        writes = []

        recorder = VadAudioRecorder(
            start_timeout_seconds=1,
            vad=vad,
            input_stream_factory=lambda **kwargs: FakeInputStream(
                [np.array([[0]], dtype=np.float32)]
            ),
            audio_writer=lambda *args, **kwargs: writes.append(args),
            clock=lambda: next(times),
        )

        with self.assertRaises(TimeoutError):
            recorder.record_until_silence()

        self.assertEqual(writes, [])
        self.assertEqual(vad.reset_count, 2)
        self.assertEqual(vad.pop_count, 0)

    def test_consecutive_recordings_do_not_share_pre_roll(self):
        vad = FakeVad(
            speech_on_read=2,
            ready_on_read=2,
            segment=[
                FakeSegment(samples=[2, 3], start=1),
                FakeSegment(samples=[8, 9], start=1),
            ],
        )
        sessions = iter(
            [
                [np.array([[1]]), np.array([[2]])],
                [np.array([[7]]), np.array([[8]])],
            ]
        )
        writes = []

        with tempfile.TemporaryDirectory() as directory:
            recorder = VadAudioRecorder(
                pre_roll_seconds=2 / 16_000,
                vad=vad,
                input_stream_factory=lambda **kwargs: FakeInputStream(
                    next(sessions)
                ),
                audio_writer=lambda *args, **kwargs: writes.append(args[1]),
                clock=lambda: 0.0,
                recordings_dir=Path(directory),
            )

            recorder.record_until_silence()
            recorder.record_until_silence()

        np.testing.assert_array_equal(writes[0], [1, 2, 3])
        np.testing.assert_array_equal(writes[1], [7, 8, 9])
        self.assertEqual(vad.pop_count, 2)
        self.assertEqual(vad.reset_count, 4)

    def test_invalid_pre_roll_duration_is_rejected(self):
        vad = FakeVad(
            speech_on_read=1,
            ready_on_read=1,
            segment=FakeSegment(samples=[1], start=0),
        )

        with self.assertRaisesRegex(ValueError, "pre_roll_seconds"):
            VadAudioRecorder(pre_roll_seconds=0, vad=vad)

    def test_ready_message_is_emitted_only_after_stream_opens(self):
        events = []
        vad = FakeVad(
            speech_on_read=1,
            ready_on_read=1,
            segment=FakeSegment(samples=[1], start=0),
        )

        with tempfile.TemporaryDirectory() as directory:
            recorder = VadAudioRecorder(
                pre_roll_seconds=1 / 16_000,
                vad=vad,
                input_stream_factory=lambda **kwargs: FakeInputStream(
                    [np.array([[1]], dtype=np.float32)],
                    events=events,
                ),
                audio_writer=lambda *args, **kwargs: None,
                clock=lambda: 0.0,
                status_callback=lambda message: events.append("ready"),
                recordings_dir=Path(directory),
            )

            recorder.record_until_silence()

        self.assertEqual(events[:2], ["stream_entered", "ready"])


if __name__ == "__main__":
    unittest.main()
