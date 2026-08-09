"""使用现有LLMClient实现意图分类接口。"""

from __future__ import annotations

import json

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


class LLMIntentClassifier:
    """把LLM字符串响应适配为严格IntentCandidate。"""

    def __init__(self, client: LLMClient) -> None:
        self._client = client

    def classify(
        self,
        request: IntentClassificationInput,
    ) -> IntentCandidate:
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

        return IntentCandidate.from_mapping(data)
