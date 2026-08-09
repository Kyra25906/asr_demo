"""使用现有LLMClient实现意图分类接口。"""

from __future__ import annotations

import json
from dataclasses import dataclass

from src.core.intent_classifier import (
    IntentCandidate,
    IntentClassificationInput,
    IntentClassifierError,
)
from src.core.intent_prompts import (
    INTENT_CLASSIFIER_SYSTEM_PROMPT,
    build_intent_classifier_user_prompt,
)
from src.llm.client import LLMClient


@dataclass(frozen=True)
class LLMIntentClassificationResult:
    """意图候选及底层模型调用指标。"""

    candidate: IntentCandidate
    attempts: int
    processing_seconds: float


class LLMIntentClassifier:
    """把LLM字符串响应适配为严格IntentCandidate。"""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def classify(
        self,
        request: IntentClassificationInput,
    ) -> IntentCandidate:
        return self.classify_with_metrics(request).candidate

    def classify_with_metrics(
        self,
        request: IntentClassificationInput,
    ) -> LLMIntentClassificationResult:
        generation = self._client.generate_json(
            system_prompt=INTENT_CLASSIFIER_SYSTEM_PROMPT,
            user_prompt=build_intent_classifier_user_prompt(request),
        )

        try:
            data = json.loads(generation.content)
        except json.JSONDecodeError as error:
            raise IntentClassifierError(
                "意图分类响应不是合法JSON。"
            ) from error

        if not isinstance(data, dict):
            raise IntentClassifierError(
                "意图分类响应顶层必须是JSON对象。"
            )

        candidate = IntentCandidate.from_mapping(data)
        return LLMIntentClassificationResult(
            candidate=candidate,
            attempts=generation.attempts,
            processing_seconds=generation.processing_seconds,
        )
