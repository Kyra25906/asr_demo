import json
import os
from pathlib import Path

from dotenv import load_dotenv

from src.llm.client import (
    OpenAICompatibleLLMClient,
)
from src.llm.processor import (
    ExperimentLLMProcessor,
)


# 找到项目根目录：
# asr_demo/scripts/test_deepseek_llm.py
#                 ↓ parents[1]
# asr_demo/
PROJECT_DIR = (
    Path(__file__)
    .resolve()
    .parents[1]
)

ENV_FILE = PROJECT_DIR / ".env"


def load_llm_config() -> dict:
    """
    从项目根目录的 .env 文件读取模型配置。

    不打印 API Key，避免密钥泄露。
    """

    if not ENV_FILE.exists():
        raise RuntimeError(
            f"没有找到配置文件：{ENV_FILE}"
        )

    load_dotenv(
        ENV_FILE,
        override=False,
    )

    required_variables = [
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
    ]

    missing_variables = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing_variables:
        raise RuntimeError(
            "缺少 LLM 配置："
            + ", ".join(missing_variables)
            + f"。请检查 {ENV_FILE}"
        )

    try:
        timeout_seconds = float(
            os.getenv(
                "LLM_TIMEOUT_SECONDS",
                "30",
            )
        )
    except ValueError as error:
        raise RuntimeError(
            "LLM_TIMEOUT_SECONDS "
            "必须是有效数字。"
        ) from error

    return {
        "base_url": os.environ[
            "LLM_BASE_URL"
        ],
        "api_key": os.environ[
            "LLM_API_KEY"
        ],
        "model": os.environ[
            "LLM_MODEL"
        ],
        "timeout_seconds": (
            timeout_seconds
        ),
    }


def print_analysis_result(
    *,
    segment_id: int,
    raw_text: str,
    outcome,
) -> None:
    """
    以便于人工验收的格式输出分析结果。
    """

    print("\n" + "=" * 60)
    print(f"第 {segment_id} 条输入")
    print("-" * 60)
    print(raw_text)

    print("\n处理状态")
    print("-" * 60)
    print(
        f"是否降级："
        f"{outcome.degraded}"
    )

    if outcome.error:
        print(
            f"错误信息："
            f"{outcome.error}"
        )

    print("\n结构化结果")
    print("-" * 60)
    print(
        json.dumps(
            outcome.value.to_dict(),
            ensure_ascii=False,
            indent=2,
        )
    )


def print_summary_result(
    outcome,
) -> None:
    """
    输出阶段总结结果。
    """

    print("\n" + "=" * 60)
    print("阶段总结")
    print("-" * 60)

    print(
        f"是否降级："
        f"{outcome.degraded}"
    )

    if outcome.error:
        print(
            f"错误信息："
            f"{outcome.error}"
        )

    print(
        json.dumps(
            outcome.value.to_dict(),
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    config = load_llm_config()

    print("DeepSeek LLM 验收开始")
    print(
        f"服务地址："
        f"{config['base_url']}"
    )
    print(
        f"模型名称："
        f"{config['model']}"
    )
    print(
        f"请求超时："
        f"{config['timeout_seconds']} 秒"
    )
    print("API Key：已加载，不显示内容")

    client = OpenAICompatibleLLMClient(
        base_url=config[
            "base_url"
        ],
        api_key=config[
            "api_key"
        ],
        model=config[
            "model"
        ],
        timeout_seconds=config[
            "timeout_seconds"
        ],
    )

    processor = ExperimentLLMProcessor(
        client=client
    )

    test_inputs = [
        (
            "使用移液枪移取500微升"
            "缓冲液加入离心管。"
        ),
        "加入500缓冲液。",
        "然后静置。",
        "温度是37摄氏度。",
        "用营业枪加入缓冲液。",
    ]

    session_id = (
        "deepseek_acceptance_001"
    )

    context: list[str] = []
    event_records: list[dict] = []

    for segment_id, raw_text in enumerate(
        test_inputs,
        start=1,
    ):
        outcome = (
            processor.analyze_segment(
                raw_text=raw_text,
                session_id=session_id,
                segment_id=segment_id,
                context=tuple(context),
            )
        )

        print_analysis_result(
            segment_id=segment_id,
            raw_text=raw_text,
            outcome=outcome,
        )

        # 无论是否降级，都保留本段事件，
        # 这样可以验证失败不会造成记录丢失。
        for event in outcome.value.events:
            event_records.append(
                event.to_dict()
            )

        # 这里只将原始口述加入上下文。
        # 正式版本可以改为最近事件摘要。
        context.append(raw_text)

    summary_outcome = processor.summarize(
        event_records,
        scope="stage",
    )

    print_summary_result(
        summary_outcome
    )

    print("\n" + "=" * 60)
    print("DeepSeek LLM 验收结束")
    print(
        f"共处理 "
        f"{len(test_inputs)} 段输入"
    )
    print(
        f"共生成 "
        f"{len(event_records)} 条事件"
    )


if __name__ == "__main__":
    main()