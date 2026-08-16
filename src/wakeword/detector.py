import logging
import wave
from pathlib import Path

import numpy as np
import sherpa_onnx
import sounddevice as sd


logger = logging.getLogger(__name__)

class WakeWordDetector:
    def __init__(
        self,
        model_dir: Path,
        keywords_file: Path,
    ):
        self.model_dir = Path(model_dir)
        self.keywords_file = Path(
            keywords_file
        )

        self._validate_files()

        logger.info("正在加载唤醒词模型……")

        self.keyword_spotter = (
            sherpa_onnx.KeywordSpotter(
                tokens=str(
                    self.model_dir
                    / "tokens.txt"
                ),
                encoder=str(
                    self.model_dir
                    / (
                        "encoder-epoch-13-avg-2-"
                        "chunk-16-left-64.onnx"
                    )
                ),
                decoder=str(
                    self.model_dir
                    / (
                        "decoder-epoch-13-avg-2-"
                        "chunk-16-left-64.onnx"
                    )
                ),
                joiner=str(
                    self.model_dir
                    / (
                        "joiner-epoch-13-avg-2-"
                        "chunk-16-left-64.onnx"
                    )
                ),
                keywords_file=str(
                    self.keywords_file
                ),
                num_threads=2,
                provider="cpu",
            )
        )

        logger.info("唤醒词模型加载完成。")

    def _validate_files(self):
        required_files = [
            self.model_dir / "tokens.txt",
            self.model_dir
            / (
                "encoder-epoch-13-avg-2-"
                "chunk-16-left-64.onnx"
            ),
            self.model_dir
            / (
                "decoder-epoch-13-avg-2-"
                "chunk-16-left-64.onnx"
            ),
            self.model_dir
            / (
                "joiner-epoch-13-avg-2-"
                "chunk-16-left-64.onnx"
            ),
            self.keywords_file,
        ]

        missing_files = [
            path
            for path in required_files
            if not path.is_file()
        ]

        if missing_files:
            missing_text = "\n".join(
                str(path)
                for path in missing_files
            )

            raise FileNotFoundError(
                f"缺少唤醒模型文件：\n"
                f"{missing_text}"
            )

    def detect_file(
        self,
        audio_path: Path,
    ) -> list[str]:
        samples, sample_rate = (
            self._read_wave(audio_path)
        )

        stream = (
            self.keyword_spotter
            .create_stream()
        )

        stream.accept_waveform(
            sample_rate,
            samples,
        )

        tail_padding = np.zeros(
            int(0.8 * sample_rate),
            dtype=np.float32,
        )

        stream.accept_waveform(
            sample_rate,
            tail_padding,
        )

        stream.input_finished()

        detected_keywords = []

        while self.keyword_spotter.is_ready(
            stream
        ):
            self.keyword_spotter.decode_stream(
                stream
            )

            result = (
                self.keyword_spotter
                .get_result(stream)
            )

            if result:
                detected_keywords.append(
                    result
                )

                self.keyword_spotter.reset_stream(
                    stream
                )

        return detected_keywords

    @staticmethod
    def _read_wave(
        audio_path: Path,
    ):
        audio_path = Path(audio_path)

        with wave.open(
            str(audio_path),
            "rb",
        ) as audio_file:
            if audio_file.getnchannels() != 1:
                raise ValueError(
                    "唤醒检测要求单声道音频。"
                )

            if audio_file.getsampwidth() != 2:
                raise ValueError(
                    "唤醒检测要求16位PCM音频。"
                )

            sample_rate = (
                audio_file.getframerate()
            )

            audio_bytes = (
                audio_file.readframes(
                    audio_file.getnframes()
                )
            )

        samples = np.frombuffer(
            audio_bytes,
            dtype=np.int16,
        )

        samples = (
            samples.astype(np.float32)
            / 32768.0
        )

        return samples, sample_rate

    def wait_for_wake_word(
        self,
    ) -> str:
        sample_rate = 16_000
        samples_per_read = int(
            0.1 * sample_rate
        )

        stream = (
            self.keyword_spotter
            .create_stream()
        )

        logger.info(
            "正在等待唤醒词“小科小科”……"
        )

        with sd.InputStream(
            channels=1,
            dtype="float32",
            samplerate=sample_rate,
        ) as microphone:
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

                stream.accept_waveform(
                    sample_rate,
                    samples,
                )

                while (
                    self.keyword_spotter
                    .is_ready(stream)
                ):
                    self.keyword_spotter.decode_stream(
                        stream
                    )

                    result = (
                        self.keyword_spotter
                        .get_result(stream)
                    )

                    if result:
                        self.keyword_spotter.reset_stream(
                            stream
                        )

                        return result
