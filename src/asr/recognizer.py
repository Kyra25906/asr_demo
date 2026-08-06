import time
from pathlib import Path

import soundfile as sf
from funasr import AutoModel
from funasr.utils.postprocess_utils import (
    rich_transcription_postprocess,
)

from src.config import ASR_MODEL, DEVICE, VAD_MODEL
from src.asr.schemas import ASRResult


class SpeechRecognizer:
    def __init__(self):
        print("正在加载ASR模型……")

        self.model = AutoModel(
            model=ASR_MODEL,
            vad_model=VAD_MODEL,
            vad_kwargs={
                "max_single_segment_time": 30_000,
            },
            device=DEVICE,
        )

        print("ASR模型加载完成")

    def recognize(self, audio_path: Path) -> ASRResult:
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(f"找不到音频文件：{audio_path}")

        audio_info = sf.info(audio_path)
        audio_duration = audio_info.frames / audio_info.samplerate

        print(f"正在识别：{audio_path}")

        start_time = time.perf_counter()

        result = self.model.generate(
            input=str(audio_path),
            cache={},
            language="auto",
            use_itn=True,
            batch_size_s=60,
        )

        recognition_seconds = time.perf_counter() - start_time

        if not result:
            raise RuntimeError("FunASR没有返回识别结果")

        raw_text = result[0].get("text", "")
        clean_text = rich_transcription_postprocess(raw_text)

        return ASRResult(
            text=clean_text,
            raw_text=raw_text,
            audio_path=str(audio_path.resolve()),
            audio_duration_seconds=round(audio_duration, 3),
            recognition_seconds=round(recognition_seconds, 3),
            model=ASR_MODEL,
            language="auto",
            is_final=True,
        )