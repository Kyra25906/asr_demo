import time
from datetime import datetime
from pathlib import Path

import sounddevice as sd
import soundfile as sf
import sherpa_onnx

from src.config import (
    RECORDINGS_DIR,
    SAMPLE_RATE,
    VAD_MODEL_PATH,
)


class VadAudioRecorder:
    def __init__(
        self,
        model_path: Path = VAD_MODEL_PATH,
        start_timeout_seconds: float = 30.0,
    ):
        self.model_path = Path(model_path)
        self.start_timeout_seconds = (
            start_timeout_seconds
        )

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

        print("正在加载VAD模型……")

        self.vad = (
            sherpa_onnx
            .VoiceActivityDetector(
                config,
                buffer_size_in_seconds=30,
            )
        )

        print("VAD模型加载完成。")

    def record_until_silence(self) -> Path:
        samples_per_read = int(
            0.1 * SAMPLE_RATE
        )

        wait_started_at = time.monotonic()
        speech_started = False

        print("正在等待你开始口述……")

        with sd.InputStream(
            channels=1,
            dtype="float32",
            samplerate=SAMPLE_RATE,
        ) as microphone:
            while True:
                samples, overflowed = (
                    microphone.read(
                        samples_per_read
                    )
                )

                if overflowed:
                    print(
                        "警告：麦克风输入发生溢出。"
                    )

                samples = samples.reshape(-1)

                self.vad.accept_waveform(
                    samples
                )

                if (
                    self.vad.is_speech_detected()
                    and not speech_started
                ):
                    speech_started = True
                    print(
                        "检测到人声，正在录制……"
                    )

                if (
                    not speech_started
                    and time.monotonic()
                    - wait_started_at
                    > self.start_timeout_seconds
                ):
                    raise TimeoutError(
                        "等待口述超时，"
                        "没有检测到有效人声。"
                    )

                if not self.vad.empty():
                    segment = self.vad.front
                    audio = segment.samples.copy()
                    self.vad.pop()
                    break

        if len(audio) == 0:
            raise RuntimeError(
                "VAD返回了空音频。"
            )

        RECORDINGS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        output_path = (
            RECORDINGS_DIR
            / f"vad_segment_{timestamp}.wav"
        )

        sf.write(
            output_path,
            audio,
            SAMPLE_RATE,
            subtype="PCM_16",
        )

        duration = len(audio) / SAMPLE_RATE

        print(
            f"检测到说话结束，"
            f"音频时长：{duration:.2f}秒"
        )
        print(f"录音已保存：{output_path}")

        return output_path