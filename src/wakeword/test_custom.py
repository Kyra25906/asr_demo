from pathlib import Path

from src.audio.recorder import AudioRecorder
from src.wakeword.detector import (
    WakeWordDetector,
)


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

KEYWORDS_FILE = (
    PROJECT_DIR
    / "models"
    / "wakeword"
    / "custom"
    / "keywords.txt"
)


def main():
    detector = WakeWordDetector(
        model_dir=MODEL_DIR,
        keywords_file=KEYWORDS_FILE,
    )

    recorder = AudioRecorder()

    input(
        "\n按 Enter 开始录制唤醒词。"
    )

    print(
        "请清楚地说“小科小科”，"
        "然后按 Enter 结束。"
    )

    audio_path = (
        recorder.record_until_enter()
    )

    detected_keywords = (
        detector.detect_file(audio_path)
    )

    if detected_keywords:
        print("\n检测成功：")

        for keyword in detected_keywords:
            print(keyword)
    else:
        print("\n没有检测到“小科小科”。")


if __name__ == "__main__":
    main()