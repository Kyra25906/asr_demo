"""按会话汇总 ASR 与事件证据，供真实验收核验使用。

用法：
    .\\.venv\\Scripts\\python.exe -B -m scripts.verify_session_context <session_id>

输出该会话的 ASR 段数、事件数、各段事件分布和转写列表。
"最终上下文包含 N 条事件" 的 N 应等于 event_count
（每个已落盘事件在内存上下文中占一条，非空文本才计入）。
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ASR_STORE = Path("results/asr_segments.jsonl")
EVENT_STORE = Path("results/experiment_events.jsonl")


def load_records(path: Path) -> list[dict]:
    """读取 JSONL 存储；损坏行跳过并记录，不影响其余记录。"""

    records = []
    if not path.is_file():
        return records

    with path.open("r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                print(
                    f"警告：{path} 第{line_number}行"
                    "不是有效JSON，已跳过。"
                )
    return records


def session_summary(
    session_id: str,
    asr_records: list[dict],
    event_records: list[dict],
) -> dict:
    """纯函数：提取指定会话的证据摘要，不读文件、无副作用。"""

    asr = [
        record
        for record in asr_records
        if record.get("session_id") == session_id
    ]
    events = [
        record
        for record in event_records
        if record.get("source_session_id") == session_id
    ]
    events.sort(
        key=lambda record: (
            record.get("source_segment_id", 0),
            record.get("event_index", 0),
        )
    )

    per_segment: dict[int, int] = defaultdict(int)
    for event in events:
        per_segment[event.get("source_segment_id", 0)] += 1

    return {
        "session_id": session_id,
        "asr_segments": len(asr),
        "event_count": len(events),
        "expected_context_count": len(events),
        "segments_with_events": dict(per_segment),
        "asr_transcripts": [
            record.get("asr_transcript")
            for record in asr
        ],
    }


def display(summary: dict) -> None:
    """以易读形式打印证据摘要。"""

    print("=" * 60)
    print(f"实验会话：{summary['session_id']}")
    print(f"ASR 段数：{summary['asr_segments']}")
    print(f"事件数：{summary['event_count']}")
    print(f"预期结束上下文计数：{summary['expected_context_count']}")
    print(f"各段事件分布：{summary['segments_with_events']}")
    print("ASR 转写：")
    for index, transcript in enumerate(
        summary["asr_transcripts"],
        start=1,
    ):
        print(f"  {index}. {transcript}")
    print("=" * 60)


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "用法：python -m scripts.verify_session_context "
            "<session_id>"
        )
        return 2

    session_id = sys.argv[1]
    summary = session_summary(
        session_id,
        load_records(ASR_STORE),
        load_records(EVENT_STORE),
    )

    if summary["asr_segments"] == 0 and summary["event_count"] == 0:
        print(f"未找到会话 {session_id} 的 ASR 或事件记录。")
        return 1

    display(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
