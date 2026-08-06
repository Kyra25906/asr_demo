import json
from datetime import datetime
from pathlib import Path

from src.config import CONFIRMATIONS_FILE
from src.core.confirmation_record import ConfirmationRecord


class ConfirmationStore:
    """将确认答复记录以 UTF-8 JSONL 形式追加保存。"""

    def __init__(
        self,
        output_path: Path = CONFIRMATIONS_FILE,
    ) -> None:
        self.output_path = Path(output_path)

    def append(
        self,
        record: ConfirmationRecord,
    ) -> None:
        """校验唯一编号后追加一条完整确认记录。"""

        if self._record_id_exists(record.record_id):
            raise ValueError(
                "确认记录编号已经存在："
                f"{record.record_id}"
            )

        stored_record = record.to_dict()
        stored_record["saved_at"] = (
            datetime.now()
            .astimezone()
            .isoformat(timespec="seconds")
        )
        line = json.dumps(
            stored_record,
            ensure_ascii=False,
        )

        self.output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self.output_path.open(
            "a",
            encoding="utf-8",
        ) as output_file:
            output_file.write(line + "\n")

    def _record_id_exists(
        self,
        record_id: str,
    ) -> bool:
        """检查已有 JSONL，避免同一回答被重复追加。"""

        if not self.output_path.exists():
            return False
        if not self.output_path.is_file():
            raise ValueError(
                "确认记录输出路径不是文件："
                f"{self.output_path}"
            )

        with self.output_path.open(
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
                    existing = json.loads(line)
                except json.JSONDecodeError as error:
                    raise ValueError(
                        "确认记录文件第 "
                        f"{line_number} 行不是合法 JSON。"
                    ) from error

                if existing.get("record_id") == record_id:
                    return True

        return False
