from faster_whisper import WhisperModel


model = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8",
)

segments, info = model.transcribe(
    "test.wav",
    language="zh",
    beam_size=5,
)

print("识别语言：", info.language)

for segment in segments:
    print(
        f"{segment.start:.2f}s → {segment.end:.2f}s："
        f"{segment.text}"
    )