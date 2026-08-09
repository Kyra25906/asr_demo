"""真实句首预缓冲验收：先录制回听，之后才能单独运行ASR。"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
import winsound
from pathlib import Path

from src.asr.recognizer import SpeechRecognizer
from src.audio.vad_recorder import VadAudioRecorder
from src.config import PROJECT_DIR
from src.evaluation.command_corpus import (
    RecordingStatus,
)
from src.evaluation.command_corpus_capture import (
    CommandCorpusCaptureCoordinator,
    ReviewDecision,
)
from src.evaluation.command_corpus_plan import CommandCorpusPlan
from src.evaluation.command_corpus_store import CommandCorpusStore


OUTPUT_DIR = PROJECT_DIR / "evaluation" / "pre_roll_real"
ATTEMPTS_FILE = OUTPUT_DIR / "attempts.jsonl"
ASR_RESULTS_FILE = OUTPUT_DIR / "asr_results.jsonl"
PLAN_FILE = OUTPUT_DIR / "capture_plan.json"
PROMPTS = CommandCorpusPlan.load(PLAN_FILE).prompts


def load_next_attempt_numbers(path: Path) -> dict[str, int]:
    """读取已有证据，为每条提示返回不会重复的下一个尝试号。"""

    next_numbers: dict[str, int] = {}
    if not path.exists():
        return next_numbers

    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            sample_id = record["sample_id"]
            attempt_number = int(record["attempt_number"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValueError(
                f"已有验收记录第 {line_number} 行损坏。"
            ) from error
        next_numbers[sample_id] = max(
            next_numbers.get(sample_id, 1),
            attempt_number + 1,
        )
    return next_numbers


def record_and_review() -> None:
    """逐条录音、播放并保存人工回听结论，不运行ASR。"""

    print("本阶段只判断WAV，不运行ASR。")
    print("请在看到提示后按回车，再完整朗读一次。")
    print("播放结束后标记：y完整、t截断、d重复、r重录、s跳过。\n")

    recorder = VadAudioRecorder(start_timeout_seconds=30.0)
    store = CommandCorpusStore(ATTEMPTS_FILE)
    coordinator = CommandCorpusCaptureCoordinator(
        recorder=recorder,
        player=_play_wav,
        store=store,
    )
    next_numbers = load_next_attempt_numbers(ATTEMPTS_FILE)

    for prompt_index, prompt in enumerate(PROMPTS, start=1):
        while True:
            attempt_number = next_numbers.get(prompt.sample_id, 1)
            print(f"\n[{prompt_index}/{len(PROMPTS)}] 请朗读：{prompt.prompt_text}")
            input("准备好后按回车开始等待人声：")

            outcome = coordinator.capture_once(
                prompt=prompt,
                attempt_number=attempt_number,
                review=_ask_review_decision,
            )
            next_numbers[prompt.sample_id] = attempt_number + 1

            if outcome.attempt.status == RecordingStatus.FAILED:
                print(
                    "录音失败并已保存证据："
                    f"{outcome.attempt.error}"
                )
                retry = input(
                    "输入 r 重试，其余输入跳到下一句："
                ).strip().lower()
                if retry == "r":
                    continue
                break

            if outcome.should_retry:
                continue
            break

    print(f"\n人工回听记录已保存：{ATTEMPTS_FILE}")
    print("请先检查结果；确认完成后再运行 --asr。")


def _play_wav(audio_path: Path) -> None:
    print(f"正在播放：{audio_path}")
    winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)


def _ask_review_decision(audio_path: Path) -> ReviewDecision:
    choice = input(
        "回听结论 [y完整/t截断/d重复/r重录/s跳过]："
    ).strip().lower()
    return {
        "y": ReviewDecision.ACCEPT,
        "d": ReviewDecision.DUPLICATED,
        "r": ReviewDecision.RETRY,
        "s": ReviewDecision.SKIP,
    }.get(choice, ReviewDecision.TRUNCATED)


def recognize_reviewed_audio() -> None:
    """只识别人工已经判定为完整的WAV，并保存派生结果。"""

    if not ATTEMPTS_FILE.is_file():
        raise FileNotFoundError(f"找不到人工回听记录：{ATTEMPTS_FILE}")

    records = [
        json.loads(line)
        for line in ATTEMPTS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    accepted = [record for record in records if record["status"] == "accepted"]
    if not accepted:
        raise RuntimeError("没有人工确认完整的WAV，不能进入ASR阶段。")

    recognizer = SpeechRecognizer()
    results = []
    for record in accepted:
        result = recognizer.recognize(Path(record["audio_path"]))
        item = {
            "attempt_id": record["attempt_id"],
            "prompt_text": record["prompt_text"],
            "audio_path": record["audio_path"],
            "observed_asr_text": result.text,
            "raw_asr_text": result.raw_text,
        }
        results.append(item)
        print(f"提示：{record['prompt_text']}")
        print(f"ASR：{result.text}\n")

    _atomic_write_jsonl(ASR_RESULTS_FILE, results)
    print(f"ASR派生结果已保存：{ASR_RESULTS_FILE}")


def _atomic_write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            for record in records:
                temporary_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--asr",
        action="store_true",
        help="在人工回听完成后识别已接受的WAV。",
    )
    args = parser.parse_args()
    if args.asr:
        recognize_reviewed_audio()
    else:
        record_and_review()


if __name__ == "__main__":
    main()
