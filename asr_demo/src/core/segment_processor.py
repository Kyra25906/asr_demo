from src.asr.schemas import (
    ASRResult,
)
from src.core.session_context import (
    SessionContext,
)
from src.llm.processor import (
    ExperimentLLMProcessor,
    ProcessOutcome,
)
from src.llm.schemas import (
    LLMAnalysisResult,
)
from src.storage.event_store import (
    ExperimentEventStore,
)
from src.storage.result_store import (
    ASRResultStore,
)


class SegmentProcessor:
    """
    编排一段有效实验口述的处理流程。

    固定处理顺序：

    1. 保存原始 ASR 记录；
    2. 使用最近上下文调用 LLM；
    3. 保存正常或降级事件；
    4. 事件保存成功后更新上下文。
    """

    def __init__(
        self,
        *,
        asr_store: ASRResultStore,
        event_store: ExperimentEventStore,
        llm_processor: (
            ExperimentLLMProcessor
        ),
    ) -> None:
        self.asr_store = asr_store
        self.event_store = event_store
        self.llm_processor = (
            llm_processor
        )

    def process(
        self,
        *,
        asr_result: ASRResult,
        session_id: str,
        segment_id: int,
        context: SessionContext,
    ) -> ProcessOutcome[
        LLMAnalysisResult
    ]:
        """
        处理一段已经通过结束指令检查的口述。

        如果 ASR 保存失败，不继续调用 LLM。

        如果 LLM 失败，ExperimentLLMProcessor
        会返回降级 NOTE，仍然继续保存。

        如果事件保存失败，不更新上下文，
        并让异常交给会话层处理。
        """

        self._validate_input(
            asr_result=asr_result,
            session_id=session_id,
            segment_id=segment_id,
        )

        # 第一步：先保存事实来源。
        #
        # 后续即使 LLM 或事件存储失败，
        # 原始 ASR 记录仍然存在。
        self.asr_store.append(
            result=asr_result,
            session_id=session_id,
            segment_id=segment_id,
        )

        # 第二步：获取调用前的上下文快照。
        #
        # 当前语音段还没有加入上下文，
        # 避免模型把本轮输入当作历史事件。
        prompt_context = (
            context.as_prompt_context()
        )

        # 第三步：调用 LLM。
        #
        # 正常情况下返回结构化结果。
        # 模型超时、网络异常或格式错误时，
        # Processor 返回降级 NOTE。
        outcome = (
            self.llm_processor
            .analyze_segment(
                raw_text=asr_result.text,
                session_id=session_id,
                segment_id=segment_id,
                context=prompt_context,
            )
        )

        # 第四步：保存正常或降级事件。
        #
        # 如果这里失败，异常会向上传递，
        # 上层会话负责显示错误并继续监听。
        self.event_store.append_analysis(
            outcome
        )

        # 第五步：只有事件成功保存后，
        # 才更新内存上下文。
        #
        # 这样上下文不会包含
        # “内存里存在但文件中不存在”的事件。
        context.add_analysis(
            outcome.value
        )

        return outcome

    @staticmethod
    def _validate_input(
        *,
        asr_result: ASRResult,
        session_id: str,
        segment_id: int,
    ) -> None:
        """
        在任何写入发生前检查基础输入。
        """

        if not session_id.strip():
            raise ValueError(
                "session_id 不能为空。"
            )

        if segment_id <= 0:
            raise ValueError(
                "segment_id 必须大于 0。"
            )

        if not asr_result.text.strip():
            raise ValueError(
                "ASR 识别文本不能为空。"
            )