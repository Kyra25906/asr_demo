import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from src.config import (
    CHANNELS,
    DTYPE,
    RECORDINGS_DIR,
    SAMPLE_RATE,
)


logger = logging.getLogger(__name__)


class AudioRecorder:
    def __init__(
        self,
        sample_rate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.dtype = dtype

    def record_until_enter(self) -> Path:
        chunks = []

        def callback(
            indata,
            frames,
            time_info,
            status,
        ):
            if status:
                logger.warning("录音状态：%s", status)

            chunks.append(indata.copy())

        logger.info("正在录音，再按 Enter 结束……")

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype=self.dtype,
            callback=callback,
        ):
            input()

        if not chunks:
            raise RuntimeError(
                "没有采集到音频，请检查麦克风。"
            )

        audio = np.concatenate(
            chunks,
            axis=0,
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
            / f"segment_{timestamp}.wav"
        )

        sf.write(
            output_path,
            audio,
            self.sample_rate,
            subtype="PCM_16",
        )

        logger.info("录音已保存：%s", output_path)

        return output_path
