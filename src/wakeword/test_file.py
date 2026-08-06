import wave
from pathlib import Path

import numpy as np
import sherpa_onnx


PROJECT_DIR = (
    Path(__file__)
    .resolve()
    .parent
    .parent
    .parent
)

MODEL_DIR = (
    PROJECT_DIR
    / "models"
    / "wakeword"
    / "sherpa-onnx-kws-zipformer-zh-en-3M-2025-12-20"
)

TEST_AUDIO = (
    MODEL_DIR
    / "test_wavs"
    / "zh_5.wav"
)


def read_wave(audio_path: Path):
    with wave.open(
        str(audio_path),
        "rb",
    ) as audio_file:
        if audio_file.getnchannels() != 1:
            raise ValueError(
                "测试音频必须是单声道。"
            )

        if audio_file.getsampwidth() != 2:
            raise ValueError(
                "测试音频必须是16位PCM。"
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


def create_keyword_spotter():
    return sherpa_onnx.KeywordSpotter(
        tokens=str(
            MODEL_DIR / "tokens.txt"
        ),
        encoder=str(
            MODEL_DIR
            / "encoder-epoch-13-avg-2-"
              "chunk-16-left-64.onnx"
        ),
        decoder=str(
            MODEL_DIR
            / "decoder-epoch-13-avg-2-"
              "chunk-16-left-64.onnx"
        ),
        joiner=str(
            MODEL_DIR
            / "joiner-epoch-13-avg-2-"
              "chunk-16-left-64.onnx"
        ),
        keywords_file=str(
            MODEL_DIR
            / "test_wavs"
            / "keywords.txt"
        ),
        num_threads=2,
        provider="cpu",
    )


def main():
    if not MODEL_DIR.exists():
        raise FileNotFoundError(
            f"找不到模型目录：{MODEL_DIR}"
        )

    if not TEST_AUDIO.exists():
        raise FileNotFoundError(
            f"找不到测试音频：{TEST_AUDIO}"
        )

    print("正在加载关键词检测模型……")
    keyword_spotter = (
        create_keyword_spotter()
    )
    print("关键词检测模型加载完成。")

    samples, sample_rate = read_wave(
        TEST_AUDIO
    )

    stream = (
        keyword_spotter.create_stream()
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

    detected_results = []

    while keyword_spotter.is_ready(
        stream
    ):
        keyword_spotter.decode_stream(
            stream
        )

        result = (
            keyword_spotter.get_result(
                stream
            )
        )

        if result:
            detected_results.append(
                result
            )

            keyword_spotter.reset_stream(
                stream
            )

    if detected_results:
        print("\n检测结果：")

        for result in detected_results:
            print(result)
    else:
        print("\n没有检测到关键词。")


if __name__ == "__main__":
    main()