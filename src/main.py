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
    SESSION_MAX_PENDING_TASKS,
    WAKEWORD_KEYWORDS_FILE,
    WAKEWORD_MODEL_DIR,
)
from src.core.segment_processor import (
    SegmentProcessor,
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
    CoordinatedReply,
    ConfirmationResolution,
    ReplyCoordinator,
)
from src.core.session_processing_queue import (
    CompletedSegment,
    SessionProcessingQueue,
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
from src.llm.client import (
    UnavailableLLMClient,
)
from src.llm.factory import (
    create_llm_client,
)
from src.llm.processor import (
    ExperimentLLMProcessor,
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

def create_experiment_llm_processor(
) -> ExperimentLLMProcessor:
    """
    创建实验记录 LLM 处理器。

    如果真实客户端初始化失败，
    使用不可用客户端继续启动程序。
    后续每段口述会走统一降级路径。
    """

    try:
        llm_client = (
            create_llm_client()
        )

        print(
            "LLM 客户端初始化成功。"
        )

    except Exception as error:
        reason = (
            f"{type(error).__name__}: "
            f"{error}"
        )

        print(
            "\n警告：LLM 客户端"
            "初始化失败。"
        )
        print(reason)
        print(
            "系统将继续运行，"
            "结构化事件会降级保存为 NOTE。\n"
        )

        llm_client = (
            UnavailableLLMClient(
                reason=reason
            )
        )

    return ExperimentLLMProcessor(
        client=llm_client
    )

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

def display_segment_result(
    *,
    asr_result,
    segment_id: int,
    outcome,
) -> None:
    """显示一段口述的 ASR、LLM 结果和运行指标。"""

    print(f"\n第 {segment_id} 段识别结果：")
    print(asr_result.asr_transcript)

    print(
        f"音频时长："
        f"{asr_result.audio_duration_seconds:.2f} 秒"
    )
    print(
        f"识别耗时："
        f"{asr_result.recognition_seconds:.2f} 秒"
    )
    print(
        f"结构化事件数量："
        f"{len(outcome.value.events)}"
    )
    print(
        f"LLM 尝试次数："
        f"{outcome.llm_attempts}"
    )
    print(
        f"LLM 处理耗时："
        f"{outcome.llm_processing_seconds:.3f} 秒"
    )

    if outcome.degraded:
        print("结构化状态：已降级。")
        print("ASR 原文和 NOTE 事件仍已保存。")

        if outcome.error:
            print(f"降级原因：{outcome.error}")
    else:
        print("结构化状态：成功。")

    if (
        not outcome.value.should_ask_follow_up
        and outcome.value.assistant_reply
    ):
        print(outcome.value.assistant_reply)

    print("ASR 和结构化事件已保存。\n")

def display_completed_segment(
    completed: CompletedSegment,
) -> None:
    """
    显示一个后台任务的最终结果。

    后台异常已经被队列转换为
    CompletedSegment.error，
    因此这里不会重新抛出异常。
    """

    if completed.error:
        print(
            "\n" + "=" * 60
        )
        print(
            f"第 {completed.segment_id} 段"
            "后台处理失败。"
        )
        print(
            f"原始识别文本："
                f"{completed.asr_result.asr_transcript}"
        )
        print(
            f"失败原因："
            f"{completed.error}"
        )
        print(
            "实验会话继续运行，"
            "请稍后检查事件存储。\n"
        )
        return

    if completed.outcome is None:
        print(
            f"\n第 {completed.segment_id} 段"
            "没有返回处理结果。\n"
        )
        return

    display_segment_result(
        asr_result=(
            completed.asr_result
        ),
        segment_id=(
            completed.segment_id
        ),
        outcome=completed.outcome
    )

def display_completed_segments(
    completed_segments: list[
        CompletedSegment
    ],
    *,
    reply_coordinator: ReplyCoordinator,
    skip_ingest: bool = False,
) -> None:
    """
    按提交顺序显示并登记一批后台结果。

    整批结果处理完后最多取出一条回复，
    防止同一个安全间隙连续输出多个问题。

    skip_ingest 为 True 时，旧 LLM 分析结果
    不会进入 ReplyCoordinator（新统一链路已
    接管协调器交互）。
    """

    for completed in completed_segments:
        display_completed_segment(
            completed
        )

        if (
            completed.error is None
            and completed.outcome is not None
            and not skip_ingest
        ):
            reply_coordinator.ingest_analysis(
                segment_id=completed.segment_id,
                raw_text=(
                    completed.asr_result.asr_transcript
                ),
                analysis=completed.outcome.value,
                target_clarification_id=(
                    completed.target_clarification_id
                ),
                confirms_target_suggestion=(
                    completed.confirms_target_suggestion
                )
            )

    reply = reply_coordinator.pop_next_reply()

    if reply is not None:
        display_coordinated_reply(reply)

def display_coordinated_reply(
    reply: CoordinatedReply,
) -> None:
    """显示一条已经带有来源信息的协调回复。"""

    print(f"\n待确认（问题{reply.display_number}）：")
    print(reply.text)
    print()

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
    segment_processor: SegmentProcessor,
    asr_store: ASRResultStore,
    confirmation_store: ConfirmationStore,
    state_manager: StateManager,
    shadow_observer: UnifiedShadowObserver | None = None,
) -> None:
    """
    运行一次完整实验会话。

    主线程负责：
    - 录音；
    - ASR；
    - 判断结束指令；
    - 提交后台任务；
    - 展示已完成结果。

    后台单线程负责：
    - 保存 ASR；
    - 调用 LLM；
    - 保存结构化事件；
    - 更新会话上下文。
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

    processing_queue = (
        SessionProcessingQueue(
            segment_processor=(
                segment_processor
            ),
            context=session_context,
            max_pending_tasks=(
                SESSION_MAX_PENDING_TASKS
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

    def _display(segments):
        """显示已完成段；统一链已接管协调器交互，跳过旧ingest。"""
        display_completed_segments(
            segments,
            reply_coordinator=reply_coordinator,
            skip_ingest=True,
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

    try:
        while True:
            # 每次开始下一轮录音前，
            # 非阻塞地领取已经完成的任务。
            completed_before_recording = (
                processing_queue
                .collect_ready()
            )

            _display(
                completed_before_recording
            )

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

                # ASR 期间后台任务可能已经完成。
                # 这里再次进行非阻塞收集。
                completed_after_asr = (
                    processing_queue
                    .collect_ready()
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
                    _display(
                        completed_after_asr
                        
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
                        _display(
                            completed_after_asr
                            
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

                    _display(
                        completed_after_asr
                        
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
                    _display(
                        completed_after_asr
                        
                    )
                    continue

                if clarification_command_result is not None:
                    display_clarification_command_result(
                        clarification_command_result
                    )
                    _display(
                        completed_after_asr
                        
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
                    _display(
                        completed_after_asr
                        
                    )
                    continue

                if confirmation_resolution is not None:
                    display_confirmation_resolution(
                        confirmation_resolution
                    )
                    _display(
                        completed_after_asr
                        
                    )
                    continue

                _display(
                    completed_after_asr

                )

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
                        segment_processor.event_store.append_analysis(
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
                    f"当前待处理任务数："
                    f"{processing_queue.pending_count()}"
                )
                print(
                    "系统将立即继续监听。\n"
                )

            except TimeoutError:
                idle_seconds = (
                    time.monotonic()
                    - last_activity_time
                )

                # 等待用户开口期间，
                # 后台任务可能已经完成。
                completed_after_timeout = (
                    processing_queue
                    .collect_ready()
                )

                _display(
                    completed_after_timeout
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

    finally:
        # 无论正常结束、空闲超时，
        # 还是用户按下 Ctrl+C，
        # 都等待已经提交的任务完成。
        pending_count = (
            processing_queue
            .pending_count()
        )

        if pending_count:
            print(
                "\n正在等待剩余 "
                f"{pending_count} 个"
                "后台任务完成……"
            )

        remaining_completed = (
            processing_queue.finish()
        )

        _display(
            remaining_completed
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

    llm_processor = (
        create_experiment_llm_processor()
    )

    segment_processor = (
        SegmentProcessor(
            asr_store=asr_store,
            event_store=event_store,
            llm_processor=llm_processor
        )
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
                segment_processor=(
                    segment_processor
                ),
                asr_store=asr_store,
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
