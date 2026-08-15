"""SenseVoiceSmall对项目统一ASR合同的适配器。"""

import logging
import time
from pathlib import Path
from typing import Any, Callable

import soundfile as sf

from src.asr.languages import SUPPORTED_SENSEVOICE_LANGUAGES
from src.asr.schemas import ASRResult
from src.config import (
    ASR_SENSEVOICE_MODEL,
    DEVICE,
    VAD_MODEL,
)


logger = logging.getLogger(__name__)


class SenseVoiceBackend:
    """隔离SenseVoice的加载参数、输出格式和文本后处理。"""

    def __init__(
        self,
        *,
        model_name: str = ASR_SENSEVOICE_MODEL,
        vad_model: str = VAD_MODEL,
        device: str = DEVICE,
        model_engine: Any | None = None,
        postprocess: Callable[[str], str] | None = None,
    ) -> None:
        self.model_name = model_name
        self.vad_model = vad_model
        self.device = device

        if model_engine is None:
            from funasr import AutoModel

            logger.info("正在加载SenseVoice ASR模型……")
            model_engine = AutoModel(
                model=model_name,
                vad_model=vad_model,
                vad_kwargs={
                    "max_single_segment_time": 30_000,
                },
                device=device,
            )
            logger.info("SenseVoice ASR模型加载完成")

        if postprocess is None:
            from funasr.utils.postprocess_utils import (
                rich_transcription_postprocess,
            )

            postprocess = rich_transcription_postprocess

        self._model_engine = model_engine
        self._postprocess = postprocess

    def recognize(
        self,
        audio_path: Path,
        *,
        language: str = "auto",
    ) -> ASRResult:
        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(
                f"找不到音频文件：{audio_path}"
            )
        if language not in SUPPORTED_SENSEVOICE_LANGUAGES:
            raise ValueError(
                "SenseVoice language 不受支持："
                f"{language!r}；可选值为："
                f"{sorted(SUPPORTED_SENSEVOICE_LANGUAGES)}"
            )

        audio_info = sf.info(audio_path)
        audio_duration = (
            audio_info.frames / audio_info.samplerate
        )

        logger.debug(f"正在识别：{audio_path}")
        start_time = time.perf_counter()
        result = self._model_engine.generate(
            input=str(audio_path),
            cache={},
            language=language,
            use_itn=True,
            batch_size_s=60,
        )
        recognition_seconds = (
            time.perf_counter() - start_time
        )

        if not result:
            raise RuntimeError("FunASR没有返回识别结果")

        raw_text = result[0].get("text", "")
        clean_text = self._postprocess(raw_text)

        return ASRResult(
            asr_transcript=clean_text,
            asr_model_raw_text=raw_text,
            audio_path=str(audio_path.resolve()),
            audio_duration_seconds=round(
                audio_duration,
                3,
            ),
            recognition_seconds=round(
                recognition_seconds,
                3,
            ),
            model=self.model_name,
            language=language,
            is_final=True,
        )
