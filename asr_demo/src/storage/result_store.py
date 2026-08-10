import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.config import RESULTS_FILE
from src.asr.schemas import ASRResult


@dataclass(frozen=True)
class StoredASREvidence:
    """一条已持久化ASR证据及其会话来源。"""

    result: ASRResult
    session_id: str
    segment_id: int
    saved_at: str


class ASRResultStore:
    def __init__(self, output_path=RESULTS_FILE):
        self.output_path = output_path

    def append(
        self,
        result: ASRResult,
        session_id: str,
        segment_id: int,
    ):
        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        record = result.to_dict()

        record["session_id"] = session_id
        record["segment_id"] = segment_id
        record["saved_at"] = (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        )

        with self.output_path.open(
            "a",
            encoding="utf-8",
        ) as output_file:
            output_file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                )
                + "\n"
            )

    def load_all(self) -> list[StoredASREvidence]:
        """兼容读取旧v1和新v2记录，不修改历史JSONL。"""

        if not self.output_path.exists():
            return []
        if not self.output_path.is_file():
            raise ValueError(
                f"ASR结果路径不是文件：{self.output_path}"
            )

        records: list[StoredASREvidence] = []
        with Path(self.output_path).open(
            "r",
            encoding="utf-8",
        ) as input_file:
            for line_number, line in enumerate(
                input_file,
                start=1,
            ):
                if not line.strip():
                    continue
                try:
                    raw_record = json.loads(line)
                    records.append(
                        self._parse_record(raw_record)
                    )
                except Exception as error:
                    raise ValueError(
                        "ASR结果记录损坏："
                        f"第{line_number}行：{error}"
                    ) from error
        return records

    @staticmethod
    def _parse_record(
        raw_record: object,
    ) -> StoredASREvidence:
        if not isinstance(raw_record, dict):
            raise ValueError("顶层必须是JSON对象。")

        metadata_keys = {
            "session_id",
            "segment_id",
            "saved_at",
        }
        if not metadata_keys.issubset(raw_record):
            raise ValueError("缺少会话来源字段。")

        session_id = raw_record["session_id"]
        segment_id = raw_record["segment_id"]
        saved_at = raw_record["saved_at"]
        if not isinstance(session_id, str) or not session_id.strip():
            raise ValueError("session_id不能为空。")
        if (
            not isinstance(segment_id, int)
            or isinstance(segment_id, bool)
            or segment_id <= 0
        ):
            raise ValueError("segment_id必须是正整数。")
        if not isinstance(saved_at, str) or not saved_at.strip():
            raise ValueError("saved_at不能为空。")

        evidence_data = {
            key: value
            for key, value in raw_record.items()
            if key not in metadata_keys
        }
        return StoredASREvidence(
            result=ASRResult.from_dict(evidence_data),
            session_id=session_id,
            segment_id=segment_id,
            saved_at=saved_at,
        )
