from funasr import AutoModel


model = AutoModel(
    model="paraformer-zh",
    vad_model="fsmn-vad",
    punc_model="ct-punc",
    device="cpu",
)

result = model.generate(
    input="test.wav",
    batch_size_s=60,
)

print(result[0]["text"])