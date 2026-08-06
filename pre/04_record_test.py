from datetime import datetime
from pathlib import Path

import sounddevice as sd
import soundfile as sf


SAMPLE_RATE = 16_000
CHANNELS = 1
RECORD_SECONDS = 15

PROJECT_DIR = Path(__file__).resolve().parent
RECORDINGS_DIR = PROJECT_DIR / "audio" / "recordings"


def main():
    RECORDINGS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    output_path = (
        RECORDINGS_DIR
        / f"microphone_test_{timestamp}.wav"
    )

    frame_count = SAMPLE_RATE * RECORD_SECONDS

    print(f"即将录制 {RECORD_SECONDS} 秒，请开始说话……")

    audio = sd.rec(
        frames=frame_count,
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
    )

    sd.wait()

    sf.write(
        output_path,
        audio,
        SAMPLE_RATE,
        subtype="PCM_16",
    )

    print(f"录音完成：{output_path}")

    info = sf.info(output_path)

    print("录音信息：")
    print(f"采样率：{info.samplerate} Hz")
    print(f"声道数：{info.channels}")
    print(f"时长：{info.duration:.2f} 秒")
    print(f"格式：{info.subtype}")


if __name__ == "__main__":
    main()