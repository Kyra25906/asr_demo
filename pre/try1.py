from funasr import AutoModel
from funasr.utils.postprocess_utils import rich_transcription_postprocess


print("正在加载模型……")

model = AutoModel(
    model="iic/SenseVoiceSmall",
    vad_model="fsmn-vad",
    vad_kwargs={
        "max_single_segment_time": 30000
    },
    device="cpu",
)

print("模型加载完成，开始识别……")

result = model.generate(
    input="test.wma",
    cache={},
    language="auto",
    use_itn=True,
)

raw_text = result[0]["text"]
text = rich_transcription_postprocess(raw_text)

print("识别结果：")
print(text)