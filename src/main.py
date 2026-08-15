import time
from datetime import datetime

from src.asr.factory import (
    create_asr_backend,
)
from src.audio.feedback import (
    play_wake_tone,
)
from src.audio.vad_recorder import (
    VadAudioRecorder,
)
from src.config import (
    SESSION_CONTEXT_MAX_EVENTS,
    WAKEWORD_KEYWORDS_FILE,
    WAKEWORD_MODEL_DIR,
)
from src.core.interaction_command import (
    InteractionCommandParser,
    InteractionCommandType,
)
from src.core.pending_clarification import (
    ClarificationStatus,
)
from src.core.reply_coordinator import (
    ReplyCoordinator,
)
from src.core.session_context import (
    SessionContext,
)
from src.core.unified_acceptance_bypass import UnifiedAcceptanceBypass
from src.core.unified_observer import (
    UnifiedObservationStatus,
    UnifiedObserver,
)
from src.core.ordered_task_queue import (
    OrderedTaskQueue,
)
from src.core.unified_segment_processor import (
    SegmentJob,
    UnifiedSegmentProcessor,
)
from src.core.retry import (
    next_backoff_delay,
)
from src.core.state_manager import (
    StateManager,
)
from src.core.states import (
    AssistantState,
)
from src.llm.factory import (
    create_llm_client,
)
from src.storage.event_store import (
    ExperimentEventStore,
)
from src.llm.unified_processor import UnifiedUnderstandingProcessor
from src.llm.unified_router import UnifiedUnderstandingRouter
from src.storage.confirmation_store import (
    ConfirmationStore,
)
from src.storage.result_store import (
    ASRResultStore,
)
from src.wakeword.detector import (
    WakeWordDetector,
)

SESSION_IDLE_TIMEOUT_SECONDS = 5 * 60

def normalize_command(
    text: str,
) -> str:
    """
    清除空格和常见标点，
    便于匹配语音控制指令。
    """

    return InteractionCommandParser.normalize(text)

def is_end_session_command(
    text: str,
) -> bool:
    """
    判断识别文本是否为结束会话指令。
    """

    command = InteractionCommandParser.parse(text)
    return command.command_type == InteractionCommandType.END_SESSION

def is_affirm_command(
    text: str,
) -> bool:
    """
    判断识别文本是否为肯定答复（"是/是的/对…"）。
    """

    command = InteractionCommandParser.parse(text)
    return command.command_type == InteractionCommandType.AFFIRM

def create_unified_observer() -> UnifiedObserver:
    """创建统一理解链观察器；统一链是唯一默认路径。"""

    print("统一理解链已启用（唯一默认路径）。")
    processor = UnifiedUnderstandingProcessor(create_llm_client())
    router = UnifiedUnderstandingRouter(processor)
    return UnifiedObserver(UnifiedAcceptanceBypass(router))

def display_observation(observation) -> None:
    """只显示脱敏摘要，不显示口述或外部错误详情。"""

    if observation.status == UnifiedObservationStatus.FAILED:
        print(
            f"[统一链] 第{observation.segment_id}段观察失败："
            f"{observation.error_type}；ASR 原文已保存。"
        )
        return

    exec_note = ""
    if (
        getattr(observation, 'executed', False)
        and getattr(observation, 'execution_reason', None)
    ):
        exec_note = f"；已执行：{observation.execution_reason}。"
    elif getattr(observation, 'executed', False):
        exec_note = "；已执行。"
    elif observation.clarification_action == "no_action":
        exec_note = "；无需执行。"
    elif getattr(observation, 'execution_reason', None):
        exec_note = f"；{observation.execution_reason}。"
    else:
        exec_note = "；未执行。"

    print(
        f"[统一链] 第{observation.segment_id}段："
        f"目标={observation.destination}，"
        f"权限={observation.permission}，"
        f"采用={observation.acceptance_kind or 'none'}，"
        f"缺失字段={observation.missing_fields or 'none'}，"
        f"需要追问={observation.follow_up_required}，"
        f"待确认动作={observation.clarification_action}"
        + exec_note
    )

    # 降级给用户一句人话：原始记录已保存，只是结构化暂不可用。
    if observation.acceptance_kind == "degraded_evidence_note":
        print("原始记录已保存，结构化处理暂时不可用。")

def recognize_one_segment(
    *,
    recorder,
    recognizer,
    state_manager: StateManager,
):
    """
    录制并识别一段实验口述。

    本函数只负责录音和 ASR，
    不负责保存、LLM 或上下文。
    """

    state_manager.change_to(
        AssistantState.LISTENING
    )

    print(
        "请开始口述实验过程，"
        "说完后自然停顿即可。"
    )

    audio_path = (
        recorder.record_until_silence()
    )

    state_manager.change_to(
        AssistantState.PROCESSING
    )

    return recognizer.recognize(
        audio_path
    )

def display_unresolved_clarifications(
    reply_coordinator: ReplyCoordinator,
) -> None:
    """在会话结束时列出仍未解决的问题。"""

    active = (
        reply_coordinator
        .active_clarifications()
    )

    if not active:
        print(
            "本次会话没有未解决的"
            "确认项。\n"
        )
        return

    print(
        f"本次会话仍有 {len(active)} 个"
        "确认项未解决："
    )

    for clarification in active:
        status_label = (
            "已暂缓"
            if clarification.status
            == ClarificationStatus.DEFERRED
            else "待回答"
        )
        print(
            f"- 问题 {clarification.display_number}"
            f"（{status_label}），"
            f"来源第 {clarification.source_segment_id} 段："
            f"{clarification.source_raw_text}"
        )
        print(
            f"  问题：{clarification.question}"
        )

    print()

def display_review_summary(
    summary,
) -> None:
    """统一链 review 动作的查看结果显示（基于处理时刻的快照）。"""

    if not summary:
        print("\n当前没有待确认问题。\n")
        return

    print(
        f"\n当前共有 {len(summary)} 个"
        "待确认问题："
    )
    for item in summary:
        status_label = (
            "已暂缓" if item.is_deferred else "待回答"
        )
        print(
            f"- 问题 {item.display_number}"
            f"（{status_label}）："
            f"{item.question}"
        )
    print()


def account_completed_task(task) -> bool:
    """统计一个已完成的后台任务；失败时报错，返回它是否算实验段。"""

    if task.error is not None:
        print(
            f"[统一链] 第{task.item.segment_id}段处理失败："
            f"{task.error}"
        )
        return False
    return task.result.observation.is_experiment_evidence

def run_experiment_session(
    *,
    recorder,
    recognizer,
    asr_store: ASRResultStore,
    event_store: ExperimentEventStore,
    confirmation_store: ConfirmationStore,
    state_manager: StateManager,
    observer: UnifiedObserver,
    executor=None,
) -> None:
    """
    运行一次完整实验会话。

    主线程只负责：录音、ASR、判断结束指令、提交后台任务、显示结果。
    观察/落盘/兜底/执行/确认等业务逻辑在后台单线程按序执行，
    因此录音不必等待 LLM 处理完成。
    """

    session_id = (
        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    session_context = (
        SessionContext(
            max_events=(
                SESSION_CONTEXT_MAX_EVENTS
            )
        )
    )

    # ReplyCoordinator 是会话级状态。
    # 新实验会创建新实例，避免问题跨会话残留。
    reply_coordinator = (
        ReplyCoordinator()
    )

    # 执行器是会话级对象；默认创建真实执行器，
    # 测试时可注入 Fake 以避免真实 LLM 提取器。
    if executor is None:
        from src.core.clarification_executor import (
            AnswerEntityExtractor,
            ClarificationExecutor
        )
        executor = ClarificationExecutor(
            reply_coordinator,
            entity_extractor=AnswerEntityExtractor(create_llm_client())
        )

    # 会话级"待确认结束"标志：后台识别到结束意图时置真，主循环读它。
    pending_end_confirmation = {"value": False}

    def display_segment_outcome(outcome) -> None:
        """后台线程算完时立即显示结果；结束确认时另置标志。"""

        display_observation(outcome.observation)
        if outcome.review_summary is not None:
            display_review_summary(outcome.review_summary)
        print(f"第 {outcome.observation.segment_id} 段已保存。")
        if outcome.observation.end_confirmation_requested:
            print("是否结束本次实验记录？（请说“是的”或“不是”）")
            pending_end_confirmation["value"] = True

    worker = UnifiedSegmentProcessor(
        session_id=session_id,
        observer=observer,
        executor=executor,
        asr_store=asr_store,
        event_store=event_store,
        confirmation_store=confirmation_store,
        reply_coordinator=reply_coordinator,
        session_context=session_context,
        display=display_segment_outcome,
    )

    queue = OrderedTaskQueue(
        worker=worker.process,
        max_pending_tasks=4,
    )

    utterance_count = 0
    experiment_segment_count = 0

    last_activity_time = (
        time.monotonic()
    )

    state_manager.change_to(
        AssistantState.SESSION_ACTIVE
    )

    print(
        "\n实验记录会话已开始。"
    )
    print(
        f"会话编号：{session_id}"
    )
    print(
        "现在可以连续口述，"
        "无需等待 LLM 处理完成。"
    )
    print(
        "说“结束实验记录”"
        "可以结束本次会话。\n"
    )

    while True:
        try:
            asr_result = (
                recognize_one_segment(
                    recorder=recorder,
                    recognizer=recognizer,
                    state_manager=(
                        state_manager
                    )
                )
            )

            last_activity_time = (
                time.monotonic()
            )

            print(
                "\n本段 ASR 识别完成："
            )
            print(
            asr_result.asr_transcript
            )

            # 结束命令不写入 ASR 文件，
            # 也不发送给后台。
            if is_end_session_command(
            asr_result.asr_transcript
            ):
                print(
                    "\n检测到结束指令，"
                    "停止接收新的实验口述。"
                )
                break

            if (
                pending_end_confirmation["value"]
                and is_affirm_command(asr_result.asr_transcript)
            ):
                print(
                    "\n确认结束，"
                    "停止接收新的实验口述。"
                )
                break

            # 提前分配编号。
            #
            # 即使后台保存失败，
            # 下一段也不会重复使用此编号。
            utterance_count += 1
            segment_id = (
                utterance_count
            )

            # 提交后台处理；返回本次提交前已完成的结果。
            completed = queue.submit(
                item=SegmentJob(
                    segment_id=segment_id,
                    asr_result=asr_result,
                )
            )
            for task in completed:
                if account_completed_task(task):
                    experiment_segment_count += 1
            print("系统将立即继续监听。\n")

        except TimeoutError:
            idle_seconds = (
                time.monotonic()
                - last_activity_time
            )

            if (
                idle_seconds
                >= (
                    SESSION_IDLE_TIMEOUT_SECONDS
                )
            ):
                print(
                    "\n实验会话"
                    "长时间无口述，"
                    "停止接收新输入。"
                )
                break

            remaining_seconds = (
                SESSION_IDLE_TIMEOUT_SECONDS
                - idle_seconds
            )

            print(
                "\n暂时没有检测到口述，"
                "实验会话继续等待。"
            )
            print(
                f"距离自动结束约还有 "
                f"{remaining_seconds:.0f} 秒。\n"
            )

        except Exception as error:
            print(
                "\n本段录音或识别失败："
                f"{type(error).__name__}: "
                f"{error}"
            )
            print(
                "当前实验会话仍然有效，"
                "系统将继续监听。\n"
            )

        finally:
            state_manager.change_to(
                AssistantState.SESSION_ACTIVE
            )

    # 排空后台：等待所有已提交任务完成并统计。
    for task in queue.finish():
        if account_completed_task(task):
            experiment_segment_count += 1

    print(
        f"\n实验会话结束，"
        f"共处理 {utterance_count} "
        "段会话口述，"
        f"其中提交 {experiment_segment_count} "
        "段实验口述。"
    )
    print(
        f"最终上下文包含 "
        f"{len(session_context)} "
        "条事件。\n"
    )

    display_unresolved_clarifications(
        reply_coordinator
    )

def main() -> None:
    """
    程序组合根。

    在这里创建程序级对象，
    并明确它们之间的依赖关系。
    """

    state_manager = StateManager()

    recorder = VadAudioRecorder(
        start_timeout_seconds=30.0
    )

    asr_store = ASRResultStore()

    confirmation_store = (
        ConfirmationStore()
    )

    event_store = (
        ExperimentEventStore()
    )

    observer = create_unified_observer()

    # ASR 模型只在程序启动时
    # 加载一次。
    recognizer = create_asr_backend()

    # 唤醒模型也只在程序启动时
    # 加载一次。
    wakeword_detector = (
        WakeWordDetector(
            model_dir=(
                WAKEWORD_MODEL_DIR
            ),
            keywords_file=(
                WAKEWORD_KEYWORDS_FILE
            )
        )
    )

    print(
        "\n实验语音智能体已启动。"
    )
    print(
        "按 Ctrl+C 关闭程序。\n"
    )

    # 唤醒连续失败次数：每次失败按指数退避等待，
    # 成功后重置为 0，避免音频设备异常时疯狂转圈。
    consecutive_failures = 0

    while True:
        state_manager.change_to(
            AssistantState.IDLE
        )

        try:
            detected_keyword = (
                wakeword_detector
                .wait_for_wake_word()
            )
            consecutive_failures = 0

            print(
                f"\n唤醒成功："
                f"{detected_keyword}"
            )

            play_wake_tone()

            run_experiment_session(
                recorder=recorder,
                recognizer=recognizer,
                asr_store=asr_store,
                event_store=event_store,
                confirmation_store=(
                    confirmation_store
                ),
                state_manager=(
                    state_manager
                ),
                observer=observer
            )

        except Exception as error:
            consecutive_failures += 1
            retry_delay = next_backoff_delay(
                consecutive_failures
            )
            print(
                "\n唤醒或会话异常："
                f"{type(error).__name__}: "
                f"{error}"
            )
            print(
                "系统将重新进入待机状态，"
                f"{retry_delay:.1f} 秒后重试"
                f"（连续第 {consecutive_failures} 次）。\n"
            )
            time.sleep(retry_delay)

        finally:
            state_manager.change_to(
                AssistantState.IDLE
            )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(
            "\n用户关闭程序。"
        )
