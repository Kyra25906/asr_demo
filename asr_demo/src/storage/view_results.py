import json
from collections import defaultdict

from src.config import RESULTS_FILE


def load_sessions():
    """
    读取JSONL，并按session_id分组。
    """

    sessions = defaultdict(list)

    if not RESULTS_FILE.is_file():
        return sessions

    with RESULTS_FILE.open(
        "r",
        encoding="utf-8",
    ) as input_file:
        for line_number, line in enumerate(
            input_file,
            start=1,
        ):
            line = line.strip()

            if not line:
                continue

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                print(
                    f"警告：第{line_number}行"
                    "不是有效JSON，已经跳过。"
                )
                continue

            session_id = record.get(
                "session_id",
                "unknown",
            )

            sessions[session_id].append(
                record
            )

    return sessions


def display_sessions(sessions):
    """
    以易读形式显示所有实验会话。
    """

    if not sessions:
        print("暂时没有识别记录。")
        return

    for session_id, records in sessions.items():
        records.sort(
            key=lambda item: item.get(
                "segment_id",
                0,
            )
        )

        print("=" * 60)
        print(f"实验会话：{session_id}")
        print(f"口述段数：{len(records)}")
        print("=" * 60)

        for record in records:
            segment_id = record.get(
                "segment_id",
                "?",
            )

            text = record.get(
                "text",
                "",
            )

            duration = record.get(
                "audio_duration_seconds",
                0,
            )

            recognition_time = record.get(
                "recognition_seconds",
                0,
            )

            saved_at = record.get(
                "saved_at",
                "",
            )

            print(f"\n第{segment_id}段")
            print(f"内容：{text}")
            print(f"录音时长：{duration:.2f}秒")
            print(
                f"识别耗时："
                f"{recognition_time:.2f}秒"
            )
            print(f"保存时间：{saved_at}")

        print()


def main():
    sessions = load_sessions()
    display_sessions(sessions)


if __name__ == "__main__":
    main()