from src.config import (
    ENV_FILE,
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_ATTEMPTS,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_RETRY_DELAY_SECONDS,
    LLM_TIMEOUT_SECONDS,
)
from src.llm.client import (
    OpenAICompatibleLLMClient,
)


def create_llm_client(
) -> OpenAICompatibleLLMClient:
    """
    使用 src.config 中的统一配置
    创建 LLM 客户端。
    """

    if not LLM_API_KEY:
        raise RuntimeError(
            "没有读取到 LLM_API_KEY。"
            f"请检查：{ENV_FILE}"
        )

    return OpenAICompatibleLLMClient(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        timeout_seconds=(
            LLM_TIMEOUT_SECONDS
        ),
        max_tokens=(
            LLM_MAX_TOKENS
        ),
        max_attempts=(
            LLM_MAX_ATTEMPTS
        ),
        retry_delay_seconds=(
            LLM_RETRY_DELAY_SECONDS
        ),
    )