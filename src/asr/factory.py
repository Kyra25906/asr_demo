"""根据集中配置创建程序级ASR后端。"""

from src.asr.backend import ASRBackend
from src.config import ASR_BACKEND


SUPPORTED_ASR_BACKENDS = frozenset({
    "sensevoice",
})


def create_asr_backend(
    backend_name: str | None = None,
) -> ASRBackend:
    """创建指定后端；未知名称在加载模型前明确失败。"""

    normalized_name = (
        ASR_BACKEND
        if backend_name is None
        else backend_name
    ).strip().lower()

    if normalized_name == "sensevoice":
        from src.asr.sensevoice_backend import (
            SenseVoiceBackend,
        )

        return SenseVoiceBackend()

    raise ValueError(
        "ASR_BACKEND 不受支持："
        f"{normalized_name!r}；可选值为："
        f"{sorted(SUPPORTED_ASR_BACKENDS)}"
    )

