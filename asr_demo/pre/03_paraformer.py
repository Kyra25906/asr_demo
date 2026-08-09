import time

from funasr import AutoModel


print("正在加载Paraformer中文流水线……")

model = AutoModel(
    model="paraformer-zh",
    vad_model="fsmn-vad",
    punc_model="ct-punc",
    device="cpu",
)

start = time.perf_counter()

result = model.generate(
    input="test.wav",
    batch_size_s=60,
)

elapsed = time.perf_counter() - start

print("完整结果：")
print(result)

print("\n识别文字：")
print(result[0]["text"])

print(f"\n识别耗时：{elapsed:.2f}秒")