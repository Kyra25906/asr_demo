import json

from src.llm.schemas import (
    ExperimentEntities,
    ExperimentEvent,
    ExperimentEventType,
    LLMAnalysisResult,
)


def main():
    operation = ExperimentEvent(
        event_type=(
            ExperimentEventType.OPERATION
        ),
        raw_text=(
            "使用移液枪移取500微升"
            "缓冲液加入离心管。"
        ),
        normalized_text=(
            "使用移液枪移取500微升"
            "缓冲液，加入离心管。"
        ),
        entities=ExperimentEntities(
            action="加入",
            object="缓冲液",
            instrument="移液枪",
            amount_value="500",
            amount_unit="微升",
            condition="加入离心管",
        ),
        source_session_id=(
            "test_session_001"
        ),
        source_segment_id=1,
    )

    observation = ExperimentEvent(
        event_type=(
            ExperimentEventType.OBSERVATION
        ),
        raw_text="溶液变成蓝色。",
        normalized_text="溶液变为蓝色。",
        entities=ExperimentEntities(
            object="溶液",
            observation="变为蓝色",
        ),
        source_session_id=(
            "test_session_001"
        ),
        source_segment_id=2,
    )

    result = LLMAnalysisResult(
        events=[
            operation,
            observation,
        ],
        should_ask_follow_up=False,
        assistant_reply=(
            "已记录试剂加入操作"
            "和颜色变化。"
        ),
    )

    print(
        json.dumps(
            result.to_dict(),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()