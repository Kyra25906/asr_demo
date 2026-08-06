from pathlib import Path

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

    detected_keyword = (
        detector.wait_for_wake_word()
    )

    print(
        f"\n唤醒成功：{detected_keyword}"
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户结束唤醒测试。")