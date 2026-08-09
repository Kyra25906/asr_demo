"""以原子替换方式保存控制命令语料录音尝试。"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from src.evaluation.command_corpus import RecordingAttempt


class CommandCorpusStore:
    """严格校验旧清单后，追加一条UTF-8 JSONL记录。"""

    def __init__(
        self,
        output_path: Path,
        *,
        replace_func: Callable[[str | Path, str | Path], Any] = os.replace,
    ) -> None:
        self.output_path = Path(output_path)
        self._replace_func = replace_func

    def append(self, attempt: RecordingAttempt) -> None:
        """以sample_id和attempt_number组成的唯一键追加记录。"""

        existing_text, existing_ids = self._read_and_validate()
        if attempt.attempt_id in existing_ids:
            raise ValueError(
                "录音尝试 attempt_id 已经存在："
                f"{attempt.attempt_id}"
            )

        record = attempt.to_dict()
        record["saved_at"] = (
            datetime.now().astimezone().isoformat(timespec="seconds")
        )
        new_line = json.dumps(record, ensure_ascii=False)

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{self.output_path.name}.",
                suffix=".tmp",
                dir=self.output_path.parent,
                delete=False,
            ) as temporary_file:
                temporary_path = Path(temporary_file.name)
                if existing_text:
                    temporary_file.write(existing_text)
                    if not existing_text.endswith(("\n", "\r")):
                        temporary_file.write("\n")
                temporary_file.write(new_line + "\n")
                temporary_file.flush()
                os.fsync(temporary_file.fileno())

            self._replace_func(temporary_path, self.output_path)
            temporary_path = None
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

    def _read_and_validate(self) -> tuple[str, set[str]]:
        """完整验证已有内容，拒绝在损坏文件后继续写。"""

        if not self.output_path.exists():
            return "", set()
        if not self.output_path.is_file():
            raise ValueError(
                "语料清单输出路径不是文件："
                f"{self.output_path}"
            )

        existing_text = self.output_path.read_text(encoding="utf-8")
        attempt_ids: set[str] = set()

        for line_number, line in enumerate(
            existing_text.splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"语料清单第 {line_number} 行不是合法 JSON。"
                ) from error

            attempt_id = record.get("attempt_id")
            if not isinstance(attempt_id, str) or not attempt_id.strip():
                raise ValueError(
                    f"语料清单第 {line_number} 行缺少 attempt_id。"
                )
            if attempt_id in attempt_ids:
                raise ValueError(
                    "语料清单内部存在重复 attempt_id："
                    f"{attempt_id}"
                )
            attempt_ids.add(attempt_id)

        return existing_text, attempt_ids
