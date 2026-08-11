import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import EVENTS_FILE
from src.llm.schemas import (
    ExperimentEvent,
)


if TYPE_CHECKING:
    from src.llm.processor import (
        ProcessOutcome,
    )
    from src.llm.schemas import (
        LLMAnalysisResult,
    )


class ExperimentEventStore:
    """
    将结构化实验事件追加保存为 JSONL。

    每行保存一个 ExperimentEvent。
    同一段口述产生多个事件时，
    这些事件共享 session_id 和 segment_id，
    使用 event_index 区分。
    """

    def __init__(
        self,
        output_path: Path = EVENTS_FILE,
    ) -> None:
        self.output_path = Path(
            output_path
        )

    def append_analysis(self, outcome) -> int:
        """保存一次 LLM 分析产生的全部事件。"""

        events = outcome.value.events

        if not events:
            raise ValueError(
                "LLM 分析结果中没有事件，无法保存。"
            )

        saved_at = (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        )

        records = []

        for event_index, event in enumerate(events, start=1):
            self._validate_event_source(event)

            record = self._build_record(
                event=event,
                event_index=event_index,
                degraded=outcome.degraded,
                error=outcome.error,
                llm_attempts=outcome.llm_attempts,
                llm_processing_seconds=(
                    outcome.llm_processing_seconds
                ),
                saved_at=saved_at,
            )

            records.append(record)

        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        lines = [
            json.dumps(record, ensure_ascii=False)
            for record in records
        ]

        with self.output_path.open(
            "a",
            encoding="utf-8",
        ) as output_file:
            output_file.write("\n".join(lines) + "\n")

        return len(records)


    @staticmethod
    def _validate_event_source(
        event: ExperimentEvent,
    ) -> None:
        """
        确保事件可以追溯到原始 ASR 记录。
        """

        if not event.source_session_id:
            raise ValueError(
                "事件缺少 "
                "source_session_id。"
            )

        if event.source_segment_id is None:
            raise ValueError(
                "事件缺少 "
                "source_segment_id。"
            )

        if event.source_segment_id <= 0:
            raise ValueError(
                "source_segment_id "
                "必须大于 0。"
            )

        if not event.raw_text:
            raise ValueError(
                "事件 raw_text 不能为空。"
            )

    @staticmethod
    def _build_record(
        *,
        event,
        event_index: int,
        degraded: bool,
        error: str | None,
        llm_attempts: int,
        llm_processing_seconds: float,
        saved_at: str,
    ) -> dict:
        """将业务事件和本次 LLM 运行元数据转换为存储记录。"""

        record = event.to_dict()

        record["event_index"] = event_index
        record["llm_degraded"] = degraded
        record["llm_error"] = error
        record["llm_attempts"] = llm_attempts
        record["llm_processing_seconds"] = (
            llm_processing_seconds
        )
        record["saved_at"] = saved_at

        return record
