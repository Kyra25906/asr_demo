"""独立采集24条控制命令固定语料，支持断点恢复。"""

from __future__ import annotations

import argparse
import winsound
from pathlib import Path

from src.audio.vad_recorder import VadAudioRecorder
from src.config import PROJECT_DIR
from src.evaluation.command_corpus import CommandCorpusPrompt
from src.evaluation.command_corpus_capture import (
    CaptureOutcome,
    CommandCorpusCaptureCoordinator,
    ReviewDecision,
)
from src.evaluation.command_corpus_plan import (
    CommandCorpusPlan,
    load_capture_progress,
)
from src.evaluation.command_corpus_session import (
    CommandCorpusCaptureSession,
)
from src.evaluation.command_corpus_store import CommandCorpusStore


PLAN_FILE = PROJECT_DIR / "evaluation" / "asr_commands" / "capture_plan.json"
ATTEMPTS_FILE = (
    PROJECT_DIR
    / "evaluation"
    / "asr_commands"
    / "capture_attempts.jsonl"
)


def show_status() -> None:
    plan = CommandCorpusPlan.load(PLAN_FILE)
    progress = load_capture_progress(plan, ATTEMPTS_FILE)
    completed = len(progress.completed_sample_ids)
    print(f"固定语料计划：{len(plan.prompts)} 条")
    print(f"已经完成：{completed} 条")
    print(f"仍待完成：{len(progress.pending_prompts)} 条")
    if progress.pending_prompts:
        print("\n待完成提示：")
        for prompt in progress.pending_prompts:
            attempt = progress.next_attempt_numbers[prompt.sample_id]
            print(
                f"- {prompt.sample_id}（下次尝试{attempt}）："
                f"{prompt.prompt_text}"
            )


def capture() -> None:
    plan = CommandCorpusPlan.load(PLAN_FILE)
    store = CommandCorpusStore(ATTEMPTS_FILE)
    coordinator = CommandCorpusCaptureCoordinator(
        recorder=VadAudioRecorder(start_timeout_seconds=30.0),
        player=_play_wav,
        store=store,
    )
    session = CommandCorpusCaptureSession(
        plan=plan,
        attempts_path=ATTEMPTS_FILE,
        coordinator=coordinator,
    )

    print("控制命令固定语料采集器")
    print("程序只展示尚未人工接受的提示，旧失败和重录证据不会覆盖。")
    print("回听选择：y接受、t截断、d重复、r立即重录、s暂时跳过。\n")

    summary = session.run(
        before_capture=_before_capture,
        review=_review,
        retry_after_problem=_retry_after_problem,
    )

    print("\n本轮采集结束：")
    print(f"- 计划总数：{summary.total_prompts}")
    print(f"- 开始前已完成：{summary.completed_before}")
    print(f"- 本轮新增完成：{summary.newly_completed}")
    print(f"- 当前累计完成：{summary.completed_after}")
    print(f"- 仍待完成：{summary.remaining_prompts}")
    print(f"- 证据清单：{ATTEMPTS_FILE}")


def _before_capture(
    prompt: CommandCorpusPrompt,
    attempt_number: int,
    position: int,
    pending_total: int,
) -> None:
    print(
        f"\n[{position}/{pending_total}] {prompt.sample_id} "
        f"第{attempt_number}次尝试"
    )
    print(f"请朗读：{prompt.prompt_text}")
    input("准备好后按回车；必须等‘麦克风已准备好’再说话：")


def _play_wav(audio_path: Path) -> None:
    print(f"正在播放：{audio_path}")
    winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)


def _review(
    prompt: CommandCorpusPrompt,
    audio_path: Path,
) -> ReviewDecision:
    choice = input(
        "回听结论 [y接受/t截断/d重复/r重录/s跳过]："
    ).strip().lower()
    return {
        "y": ReviewDecision.ACCEPT,
        "d": ReviewDecision.DUPLICATED,
        "r": ReviewDecision.RETRY,
        "s": ReviewDecision.SKIP,
    }.get(choice, ReviewDecision.TRUNCATED)


def _retry_after_problem(outcome: CaptureOutcome) -> bool:
    if outcome.attempt.error:
        print(f"本次失败：{outcome.attempt.error}")
    elif outcome.attempt.capture_note:
        print(outcome.attempt.capture_note)
    return (
        input("输入 r 立即重试，其余输入继续下一条：")
        .strip()
        .lower()
        == "r"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--status",
        action="store_true",
        help="只查看完成度，不加载模型或打开麦克风。",
    )
    args = parser.parse_args()
    if args.status:
        show_status()
    else:
        capture()


if __name__ == "__main__":
    main()
