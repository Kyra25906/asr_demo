import json
from datetime import datetime

from src.config import RESULTS_FILE
from src.asr.schemas import ASRResult


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