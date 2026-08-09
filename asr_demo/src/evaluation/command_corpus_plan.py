"""加载版本化语料提示计划，并根据已有尝试计算恢复进度。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.evaluation.command_corpus import CommandCorpusPrompt


@dataclass(frozen=True)
class CommandCorpusPlan:
    schema_version: int
    prompts: tuple[CommandCorpusPrompt, ...]

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError(
                "不支持的语料计划schema_version："
                f"{self.schema_version}"
            )
        if not self.prompts:
            raise ValueError("语料计划至少需要一条提示。")
        sample_ids = [prompt.sample_id for prompt in self.prompts]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("语料计划中的sample_id不能重复。")

    @classmethod
    def load(cls, path: Path) -> CommandCorpusPlan:
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise ValueError("语料计划不是合法JSON。") from error

        if not isinstance(data, dict):
            raise ValueError("语料计划根节点必须是对象。")
        _require_exact_keys(
            data,
            required={"schema_version", "prompts"},
            context="语料计划",
        )
        if not isinstance(data["prompts"], list):
            raise ValueError("prompts必须是数组。")

        prompts = tuple(
            _parse_prompt(item, index=index)
            for index, item in enumerate(data["prompts"], start=1)
        )
        return cls(
            schema_version=data["schema_version"],
            prompts=prompts,
        )


@dataclass(frozen=True)
class CaptureProgress:
    completed_sample_ids: frozenset[str]
    pending_prompts: tuple[CommandCorpusPrompt, ...]
    next_attempt_numbers: dict[str, int]


def load_capture_progress(
    plan: CommandCorpusPlan,
    attempts_path: Path,
) -> CaptureProgress:
    """只有accepted算完成；其他状态保留证据并继续采集。"""

    attempts_path = Path(attempts_path)
    plan_ids = {prompt.sample_id for prompt in plan.prompts}
    completed: set[str] = set()
    next_numbers = {prompt.sample_id: 1 for prompt in plan.prompts}

    if attempts_path.exists():
        for line_number, line in enumerate(
            attempts_path.read_text(encoding="utf-8").splitlines(),
            start=1,
        ):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                sample_id = record["sample_id"]
                attempt_number = record["attempt_number"]
                status = record["status"]
            except (json.JSONDecodeError, KeyError) as error:
                raise ValueError(
                    f"录音尝试第 {line_number} 行损坏。"
                ) from error

            if sample_id not in plan_ids:
                raise ValueError(
                    "录音尝试引用了计划外sample_id："
                    f"{sample_id}"
                )
            if (
                isinstance(attempt_number, bool)
                or not isinstance(attempt_number, int)
                or attempt_number <= 0
            ):
                raise ValueError(
                    f"录音尝试第 {line_number} 行attempt_number非法。"
                )
            if status not in {
                "accepted",
                "retry_requested",
                "skipped",
                "failed",
            }:
                raise ValueError(
                    f"录音尝试第 {line_number} 行status非法。"
                )

            next_numbers[sample_id] = max(
                next_numbers[sample_id],
                attempt_number + 1,
            )
            if status == "accepted":
                completed.add(sample_id)

    pending = tuple(
        prompt
        for prompt in plan.prompts
        if prompt.sample_id not in completed
    )
    return CaptureProgress(
        completed_sample_ids=frozenset(completed),
        pending_prompts=pending,
        next_attempt_numbers=next_numbers,
    )


def _parse_prompt(item: object, *, index: int) -> CommandCorpusPrompt:
    if not isinstance(item, dict):
        raise ValueError(f"第 {index} 条提示必须是对象。")
    _require_exact_keys(
        item,
        required={"sample_id", "expected_intent", "prompt_text"},
        optional={"critical_terms"},
        context=f"第 {index} 条提示",
    )
    critical_terms = item.get("critical_terms", [])
    if not isinstance(critical_terms, list) or not all(
        isinstance(term, str) for term in critical_terms
    ):
        raise ValueError(f"第 {index} 条提示critical_terms必须是字符串数组。")
    return CommandCorpusPrompt(
        sample_id=item["sample_id"],
        expected_intent=item["expected_intent"],
        prompt_text=item["prompt_text"],
        critical_terms=tuple(critical_terms),
    )


def _require_exact_keys(
    data: dict,
    *,
    required: set[str],
    context: str,
    optional: set[str] | None = None,
) -> None:
    optional = optional or set()
    missing = required - data.keys()
    extra = data.keys() - required - optional
    if missing:
        raise ValueError(f"{context}缺少字段：{sorted(missing)}")
    if extra:
        raise ValueError(f"{context}包含额外字段：{sorted(extra)}")
