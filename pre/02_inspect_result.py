from pprint import pprint

from funasr import AutoModel


model = AutoModel(
    model="iic/SenseVoiceSmall",
    vad_model="fsmn-vad",
    device="cpu",
)

result = model.generate(
    input="test.wav",
    language="auto",
    use_itn=True,
)

pprint(result)