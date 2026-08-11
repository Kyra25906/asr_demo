import sounddevice as sd
import sherpa_onnx

from src.config import (
    SAMPLE_RATE,
    VAD_MODEL_PATH,
)


def create_vad():
    if not VAD_MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"找不到VAD模型："
            f"{VAD_MODEL_PATH}"
        )

    config = sherpa_onnx.VadModelConfig()

    config.silero_vad.model = str(
        VAD_MODEL_PATH
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

    return sherpa_onnx.VoiceActivityDetector(
        config,
        buffer_size_in_seconds=30,
    )


def main():
    vad = create_vad()

    samples_per_read = int(
        0.1 * SAMPLE_RATE
    )

    print("VAD测试已启动。")
    print("请正常说一段话，然后保持安静。")
    print("按 Ctrl+C 退出。\n")

    speech_started = False
    segment_count = 0

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

            vad.accept_waveform(samples)

            if (
                vad.is_speech_detected()
                and not speech_started
            ):
                speech_started = True
                print("检测到人声，开始记录……")

            if (
                not vad.is_speech_detected()
                and speech_started
            ):
                speech_started = False
                print("正在等待说话结束……")

            while not vad.empty():
                segment = vad.front
                segment_samples = (
                    segment.samples
                )

                segment_count += 1

                duration = (
                    len(segment_samples)
                    / SAMPLE_RATE
                )

                print(
                    f"第{segment_count}段人声结束，"
                    f"时长：{duration:.2f}秒"
                )
                print(
                    "可以继续说下一段。\n"
                )

                vad.pop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n用户结束VAD测试。")