import logging
import time
from datetime import datetime
from pathlib import Path

import sounddevice as sd
import soundfile as sf
import sherpa_onnx

from src.audio.pre_roll_timeline import PreRollTimelineBuffer
from src.audio.timeline_speech_assembler import TimelineSpeechAssembler
from src.config import (
    RECORDINGS_DIR,
    SAMPLE_RATE,
    VAD_MODEL_PATH,
)


logger = logging.getLogger(__name__)


class VadAudioRecorder:
    def __init__(
        self,
        model_path: Path = VAD_MODEL_PATH,
        start_timeout_seconds: float = 30.0,
        pre_roll_seconds: float = 0.5,
        *,
        vad=None,
        input_stream_factory=None,
        audio_writer=None,
        clock=None,
        now=None,
        status_callback=None,
        recordings_dir: Path = RECORDINGS_DIR,
    ):
        self.model_path = Path(model_path)
        self.start_timeout_seconds = (
            start_timeout_seconds
        )
        self.pre_roll_seconds = pre_roll_seconds
        self._input_stream_factory = (
            input_stream_factory or sd.InputStream
        )
        self._audio_writer = audio_writer or sf.write
        self._clock = clock or time.monotonic
        self._now = now or datetime.now
        self._status_callback = status_callback or logger.info
        self._recordings_dir = Path(recordings_dir)
        self._timeline_assembler = TimelineSpeechAssembler()

        if pre_roll_seconds <= 0:
            raise ValueError("pre_roll_seconds 必须大于 0。")

        if vad is not None:
            self.vad = vad
            return

        if not self.model_path.is_file():
            raise FileNotFoundError(
                f"找不到VAD模型："
                f"{self.model_path}"
            )

        config = sherpa_onnx.VadModelConfig()

        config.silero_vad.model = str(
            self.model_path
        )

        config.silero_vad.threshold = 0.25

        config.silero_vad.min_silence_duration = (
            2.0
        )

        config.silero_vad.min_speech_duration = (
            0.3
        )

        config.silero_vad.max_speech_duration = (
            30.0
        )

        config.silero_vad.window_size = 512

        config.sample_rate = SAMPLE_RATE
        config.num_threads = 1

        logger.info("正在加载VAD模型……")

        self.vad = (
            sherpa_onnx
            .VoiceActivityDetector(
                config,
                buffer_size_in_seconds=30,
            )
        )

        logger.info("VAD模型加载完成。")

    def record_until_silence(self) -> Path:
        samples_per_read = int(
            0.1 * SAMPLE_RATE
        )

        wait_started_at = self._clock()
        speech_started = False
        frozen_pre_roll = None
        timeline = PreRollTimelineBuffer.from_seconds(
            duration_seconds=self.pre_roll_seconds,
            sample_rate=SAMPLE_RATE,
        )

        self.vad.reset()
        try:
            with self._input_stream_factory(
                channels=1,
                dtype="float32",
                samplerate=SAMPLE_RATE,
            ) as microphone:
                self._status_callback(
                    "麦克风已准备好，请开始口述……"
                )
                while True:
                    samples, overflowed = (
                        microphone.read(
                            samples_per_read
                        )
                    )

                    if overflowed:
                        logger.warning(
                            "警告：麦克风输入发生溢出。"
                        )

                    samples = samples.reshape(-1)
                    if frozen_pre_roll is None:
                        timeline.append(samples)

                    self.vad.accept_waveform(
                        samples
                    )

                    if (
                        self.vad.is_speech_detected()
                        and not speech_started
                    ):
                        speech_started = True
                        frozen_pre_roll = timeline.snapshot()
                        logger.info(
                            "检测到人声，正在录制……"
                        )

                    if (
                        not speech_started
                        and self._clock()
                        - wait_started_at
                        > self.start_timeout_seconds
                    ):
                        raise TimeoutError(
                            "等待口述超时，"
                            "没有检测到有效人声。"
                        )

                    if not self.vad.empty():
                        segment = self.vad.front
                        if frozen_pre_roll is None:
                            frozen_pre_roll = timeline.snapshot()
                        audio = self._timeline_assembler.assemble(
                            pre_roll=frozen_pre_roll,
                            speech_segment=segment.samples,
                            speech_start_sample=segment.start,
                        )
                        self.vad.pop()
                        break
        finally:
            self.vad.reset()

        if len(audio) == 0:
            raise RuntimeError(
                "VAD返回了空音频。"
            )

        self._recordings_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = self._now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        output_path = (
            self._recordings_dir
            / f"vad_segment_{timestamp}.wav"
        )

        self._audio_writer(
            output_path,
            audio,
            SAMPLE_RATE,
            subtype="PCM_16",
        )

        duration = len(audio) / SAMPLE_RATE

        logger.info(
            "检测到说话结束，音频时长：%.2f秒",
            duration,
        )
        logger.info("录音已保存：%s", output_path)

        return output_path
