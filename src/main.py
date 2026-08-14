import time
from dataclasses import replace
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
from src.core.confirmation_record import (
    ConfirmationRecord,
)
from src.core.clarification_command_handler import (
    ClarificationCommandResult,
    try_handle_clarification_command,
)
from src.core.interaction_command import (
    InteractionCommandParser,
    InteractionCommandType,
)
from src.core.pending_clarification import (
    ClarificationStatus,
)
from src.core.reply_coordinator import (
    ConfirmationResolution,
    ReplyCoordinator,
)
from src.core.session_context import (
    SessionContext,
)
from src.core.targeted_clarification import (
    TargetedAnswerStatus,
    resolve_targeted_answer,
)
from src.core.unified_acceptance_bypass import UnifiedAcceptanceBypass
from src.core.unified_shadow import (
    ShadowObservationStatus,
    UnifiedShadowObserver,
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

def create_unified_shadow_observer() -> UnifiedShadowObserver:
    """创建统一理解链观察器；统一链是唯一默认路径。"""

    print("统一理解链已启用（唯一默认路径）。")
    processor = UnifiedUnderstandingProcessor(create_llm_client())
    router = UnifiedUnderstandingRouter(processor)
    return UnifiedShadowObserver(UnifiedAcceptanceBypass(router))

def display_shadow_observation(observation) -> None:
    """只显示脱敏摘要，不显示口述或外部错误详情。"""

    if observation.status == ShadowObservationStatus.FAILED:
        print(
            f"[新系统影子] 第{observation.segment_id}段观察失败："
            f"{observation.error_type}；旧流程继续。"
        )
        return

    exec_note = ""
    if getattr(observation, 'executed', False):
        exec_note = "；已执行。"
    elif observation.clarification_action == "no_action":
        exec_note = "；无需执行。"
    elif getattr(observation, 'execution_reason', None):
        exec_note = f"；{observation.execution_reason}。"
    else:
        exec_note = "；未执行。"

    print(
        f"[新系统影子] 第{observation.segment_id}段："
        f"目标={observation.destination}，"
        f"权限={observation.permission}，"
        f"采用={observation.acceptance_kind or 'none'}，"
        f"缺失字段={observation.missing_fields or 'none'}，"
        f"需要追问={observation.follow_up_required}，"
        f"待确认动作={observation.clarification_action}"
        + exec_note
    )

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

def try_handle_confirmation_answer(
    *,
    asr_result,
    session_id: str,
    segment_id: int,
    reply_coordinator: ReplyCoordinator,
    asr_store: ASRResultStore,
    confirmation_store: ConfirmationStore,
) -> ConfirmationResolution | None:
    """
    尝试按“准备、保存、提交”处理明确肯定答复。

    返回 None 表示当前文本不是可处理的确认答复。
    """

    prepared = (
        reply_coordinator
        .prepare_confirmation(
            segment_id=segment_id,
        raw_text=asr_result.asr_transcript
        )
    )

    if prepared is None:
        return None

    # 原始 ASR 优先保存。
    # 即使后续确认记录写入失败，
    # 用户实际说过的话仍然可以追溯。
    asr_store.append(
        result=asr_result,
        session_id=session_id,
        segment_id=segment_id
    )

    record = (
        ConfirmationRecord
        .from_prepared_confirmation(
            session_id=session_id,
            answer_audio_path=(
                str(asr_result.audio_path)
            ),
            prepared=prepared
        )
    )

    confirmation_store.append(record)

    # 只有两次持久化都成功后，
    # 才真正关闭内存中的待确认项。
    return (
        reply_coordinator
        .commit_confirmation(prepared)
    )

def display_confirmation_resolution(
    resolution: ConfirmationResolution,
) -> None:
    """显示一次已经保存并提交的确认结果。"""

    print(
        f"\n已保存对第 "
        f"{resolution.source_segment_id} 段的确认答复。"
    )

    if resolution.fully_resolved:
        print("该待确认项已经解决。\n")
    else:
        remaining = "、".join(
            resolution.remaining_fields
        )
        print(
            "错词确认已完成，"
            f"仍需补充：{remaining}。\n"
        )

def display_clarification_command_result(
    result: ClarificationCommandResult,
) -> None:
    """显示暂缓或回看命令的直接结果。"""

    if result.command_type == InteractionCommandType.DEFER_CURRENT:
        if result.deferred is None:
            print("\n当前没有正在询问的问题。\n")
            return

        print(
            f"\n已暂缓问题 {result.deferred.display_number}。"
        )
        print(
            "你可以稍后说“查看待确认问题”"
            "重新查看。\n"
        )
        return

    if not result.unresolved:
        print("\n当前没有待确认问题。\n")
        return

    print(
        f"\n当前共有 {len(result.unresolved)} 个"
        "待确认问题："
    )
    for clarification in result.unresolved:
        status_label = (
            "已暂缓"
            if clarification.status
            == ClarificationStatus.DEFERRED
            else "待回答"
        )
        print(
            f"- 问题 {clarification.display_number}"
            f"（{status_label}）："
            f"{clarification.question}"
        )
    print()

def run_experiment_session(
    *,
    recorder,
    recognizer,
    asr_store: ASRResultStore,
    event_store: ExperimentEventStore,
    confirmation_store: ConfirmationStore,
    state_manager: StateManager,
    shadow_observer: UnifiedShadowObserver,
) -> None:
    """
    运行一次完整实验会话。

    主线程负责：
    - 录音；
    - ASR；
    - 判断结束指令；
    - 统一链观察（理解/分派/执行）；
    - 直接落盘 ASR 与事件证据。
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

    # 新链路执行器——统一链是唯一路径，始终创建
    from src.core.clarification_executor import (
        AnswerEntityExtractor,
        ClarificationExecutor
    )
    extractor = AnswerEntityExtractor(create_llm_client())
    shadow_executor = ClarificationExecutor(
        reply_coordinator,
        entity_extractor=extractor
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
            # 也不发送给 LLM。
            if is_end_session_command(
            asr_result.asr_transcript
            ):
                print(
                    "\n检测到结束指令，"
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

            # 统一链是唯一路径，观察器始终存在。
            # 调用前的上下文快照只包含此前已成功落盘的事件。
            # 当前段尚未加入上下文，避免模型把本轮输入当作历史。
            recent_context = (
                session_context.as_prompt_context()
            )
            observation = shadow_observer.observe(
                request_id=f"shadow-{session_id}-{segment_id}",
                session_id=session_id,
                segment_id=segment_id,
                asr_result=asr_result,
                reply_coordinator=reply_coordinator,
                recent_context=recent_context,
            )
            _new_chain_handled_answer = (
                observation.status.value == "observed"
                and observation.clarification_action == "answer"
            )

            if _new_chain_handled_answer:
                targeted_answer_request = None
            else:
                targeted_answer_request = (
                    resolve_targeted_answer(
                    asr_result.asr_transcript,
                        reply_coordinator=reply_coordinator
                    )
                )

            if (
                targeted_answer_request is not None
                and targeted_answer_request.status
                != TargetedAnswerStatus.READY
            ):
                try:
                    asr_store.append(
                        result=asr_result,
                        session_id=session_id,
                        segment_id=segment_id
                    )
                except Exception as error:
                    print(
                        "\n指定问题答复保存失败："
                        f"{type(error).__name__}: {error}"
                    )
                    print(
                        "问题状态没有改变，"
                        "系统将继续监听。\n"
                    )
                    continue

                if (
                    targeted_answer_request.status
                    == TargetedAnswerStatus.NOT_FOUND
                ):
                    print(
                        "\n没有找到未解决的问题 "
                        f"{targeted_answer_request.display_number}。"
                    )
                    print(
                        "请说“查看待确认问题”"
                        "确认当前编号。\n"
                    )
                else:
                    print(
                        "\n请在同一句中说明问题编号和答案。"
                    )
                    print(
                        "例如：“问题 2，"
                        "水浴温度是 60 摄氏度。”\n"
                    )

                continue

            try:
                clarification_command_result = (
                    try_handle_clarification_command(
                        asr_result=asr_result,
                        session_id=session_id,
                        segment_id=segment_id,
                        reply_coordinator=reply_coordinator,
                        asr_store=asr_store
                    )
                )
            except Exception as error:
                print(
                    "\n待确认命令保存失败："
                    f"{type(error).__name__}: {error}"
                )
                print(
                    "问题状态没有改变，"
                    "系统将继续监听。\n"
                )
                continue

            if clarification_command_result is not None:
                display_clarification_command_result(
                    clarification_command_result
                )
                continue

            try:
                confirmation_resolution = (
                    try_handle_confirmation_answer(
                        asr_result=asr_result,
                        session_id=session_id,
                        segment_id=segment_id,
                        reply_coordinator=(
                            reply_coordinator
                        ),
                        asr_store=asr_store,
                        confirmation_store=(
                            confirmation_store
                        )
                    )
                )
            except Exception as error:
                print(
                    "\n确认答复保存失败："
                    f"{type(error).__name__}: "
                    f"{error}"
                )
                print(
                    "待确认项保持未解决，"
                    "系统将继续监听。\n"
                )
                continue

            if confirmation_resolution is not None:
                display_confirmation_resolution(
                    confirmation_resolution
                )
                continue

            # 统一链是唯一路径：只统计被采用为实验/降级证据的段。
            # 查看、暂缓、弃权、失败观察等不占实验段计数，
            # 否则结束时"提交 N 段实验口述"会虚高。
            if observation.is_experiment_evidence:
                experiment_segment_count += 1
            # ASR 由 main 直接落盘，不再通过旧 SegmentProcessor 调 LLM。
            # 有实验分析时一并保存事件，
            # 非实验段（abstention/查看等）只存 ASR。
            try:
                asr_store.append(
                    result=asr_result,
                    session_id=session_id,
                    segment_id=segment_id,
                )
            except Exception as error:
                print(
                    "\nASR 保存失败："
                    f"{type(error).__name__}: {error}"
                )
                print(
                    "系统将继续监听。\n"
                )
                continue

            if observation.accepted_analysis is not None:
                outcome = (
                    observation
                    .accepted_analysis
                    .to_process_outcome()
                )
                try:
                    event_store.append_analysis(
                        outcome
                    )
                except Exception as error:
                    print(
                        "\n事件保存失败："
                        f"{type(error).__name__}: {error}"
                    )
                    print(
                        "ASR 原文已保存，"
                        "系统将继续监听。\n"
                    )
                else:
                    # 事件落盘成功后，才把分析事件加入内存上下文。
                    # 与旧 SegmentProcessor 第 5 步语义一致：
                    # 上下文不包含“内存有但文件无”的事件。
                    try:
                        session_context.add_analysis(
                            outcome.value
                        )
                    except Exception as error:
                        print(
                            "\n上下文更新失败："
                            f"{type(error).__name__}: {error}"
                        )

            # commit：ASR 与事件证据都落盘成功后，
            # 才执行状态变更。
            executed = False
            execution_reason = None
            if observation.pending_action is not None:
                try:
                    exec_result = shadow_executor.execute(
                        observation.pending_action
                    )
                    executed = exec_result.state_changed
                    execution_reason = exec_result.reason
                except Exception:
                    execution_reason = "执行器内部异常"

            observation = replace(
                observation,
                executed=executed,
                execution_reason=execution_reason,
            )
            display_shadow_observation(observation)

            print(
                f"第 {segment_id} 段"
                "已保存。"
            )
            print(
                "系统将立即继续监听。\n"
            )

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

    shadow_observer = create_unified_shadow_observer()

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
                shadow_observer=shadow_observer
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
