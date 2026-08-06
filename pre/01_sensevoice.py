import time

from funasr import AutoModel
from funasr.utils.postprocess_utils import (
    rich_transcription_postprocess,
)


print("1. 正在加载模型……")

load_start = time.perf_counter()

model = AutoModel(
    model="iic/SenseVoiceSmall",
    vad_model="fsmn-vad",
    vad_kwargs={
        "max_single_segment_time": 30000,
    },
    device="cpu",
)

load_seconds = time.perf_counter() - load_start

print(f"2. 模型加载完成，耗时：{load_seconds:.2f}秒")
print("3. 开始识别……")

asr_start = time.perf_counter()

result = model.generate(
    input="test.wav",
    cache={},
    language="auto",
    use_itn=True,
    batch_size_s=60,
)

asr_seconds = time.perf_counter() - asr_start

raw_text = result[0]["text"]
clean_text = rich_transcription_postprocess(raw_text)

print("4. 识别完成")
print("原始结果：", raw_text)
print("整理结果：", clean_text)
print(f"识别耗时：{asr_seconds:.2f}秒")