import json
import unittest
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError

from src.llm.client import (
    LLMClientError,
    OpenAICompatibleLLMClient,
)


class FakeHTTPResponse:
    """
    模拟urlopen返回的HTTP响应。

    支持：
        with urlopen(...) as response
    """

    def __init__(
        self,
        payload: dict,
    ) -> None:
        self.payload = payload

    def __enter__(
        self,
    ):
        return self

    def __exit__(
        self,
        exception_type,
        exception,
        traceback,
    ):
        return False

    def read(
        self,
    ) -> bytes:
        return json.dumps(
            self.payload,
            ensure_ascii=False,
        ).encode("utf-8")


def make_response(
    content,
    *,
    reasoning_content=None,
    finish_reason="stop",
) -> FakeHTTPResponse:
    """
    构造一个符合DeepSeek
    Chat Completions格式的假响应。
    """

    return FakeHTTPResponse(
        {
            "choices": [
                {
                    "message": {
                        "content": content,
                        "reasoning_content": (
                            reasoning_content
                        ),
                    },
                    "finish_reason": (
                        finish_reason
                    ),
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
            },
        }
    )


def make_client(
) -> OpenAICompatibleLLMClient:
    """
    创建测试客户端。

    urlopen会被Mock替换，
    所以不会产生真实网络请求。
    """

    return OpenAICompatibleLLMClient(
        base_url="https://example.com",
        api_key="test-api-key",
        model="test-model",
        timeout_seconds=1.0,
        max_tokens=100,
        max_attempts=2,
        retry_delay_seconds=0.01,
    )


class LLMClientRetryTests(
    unittest.TestCase
):
    @patch(
        "src.llm.client.time.sleep"
    )
    @patch(
        "src.llm.client.urlopen"
    )
    def test_empty_response_retries_and_succeeds(
        self,
        mock_urlopen,
        mock_sleep,
    ):
        """
        第一次返回空内容，
        第二次返回有效内容。

        应返回：
        - 第二次响应内容；
        - attempts=2；
        - 总处理耗时。
        """

        mock_urlopen.side_effect = [
            make_response(""),
            make_response(
                '{"events": []}'
            ),
        ]

        client = make_client()

        result = client.generate_json(
            system_prompt="输出 JSON",
            user_prompt="测试输入",
        )

        self.assertEqual(
            result.content,
            '{"events": []}',
        )

        self.assertEqual(
            result.attempts,
            2,
        )

        self.assertGreaterEqual(
            result.processing_seconds,
            0.0,
        )

        self.assertEqual(
            mock_urlopen.call_count,
            2,
        )

        mock_sleep.assert_called_once_with(
            0.01
        )

    @patch(
        "src.llm.client.time.sleep"
    )
    @patch(
        "src.llm.client.urlopen"
    )
    def test_two_empty_responses_raise_error(
        self,
        mock_urlopen,
        mock_sleep,
    ):
        """
        连续两次返回空内容。

        应抛出LLMClientError，并记录：
        - attempts=2；
        - 总处理耗时；
        - 最终空响应原因。
        """

        mock_urlopen.side_effect = [
            make_response(
                "",
                reasoning_content=(
                    "第一次思考"
                ),
                finish_reason="length",
            ),
            make_response(
                "",
                reasoning_content=(
                    "第二次思考"
                ),
                finish_reason="length",
            ),
        ]

        client = make_client()

        with self.assertRaises(
            LLMClientError
        ) as context:
            client.generate_json(
                system_prompt="输出 JSON",
                user_prompt="测试输入",
            )

        error = context.exception
        error_message = str(error)

        self.assertIn(
            "2次尝试",
            error_message,
        )

        self.assertIn(
            "finish_reason='length'",
            error_message,
        )

        self.assertIn(
            "reasoning_length",
            error_message,
        )

        self.assertEqual(
            error.attempts,
            2,
        )

        self.assertGreaterEqual(
            error.processing_seconds,
            0.0,
        )

        self.assertEqual(
            mock_urlopen.call_count,
            2,
        )

        mock_sleep.assert_called_once_with(
            0.01
        )

    @patch(
        "src.llm.client.time.sleep"
    )
    @patch(
        "src.llm.client.urlopen"
    )
    def test_timeout_retries_and_succeeds(
        self,
        mock_urlopen,
        mock_sleep,
    ):
        """
        第一次超时，第二次成功。

        超时属于临时错误，
        应重试一次并返回attempts=2。
        """

        mock_urlopen.side_effect = [
            TimeoutError(
                "模拟请求超时"
            ),
            make_response(
                '{"ok": true}'
            ),
        ]

        client = make_client()

        result = client.generate_json(
            system_prompt="输出 JSON",
            user_prompt="测试输入",
        )

        self.assertEqual(
            result.content,
            '{"ok": true}',
        )

        self.assertEqual(
            result.attempts,
            2,
        )

        self.assertGreaterEqual(
            result.processing_seconds,
            0.0,
        )

        self.assertEqual(
            mock_urlopen.call_count,
            2,
        )

        mock_sleep.assert_called_once_with(
            0.01
        )

    @patch(
        "src.llm.client.time.sleep"
    )
    @patch(
        "src.llm.client.urlopen"
    )
    def test_http_401_does_not_retry(
        self,
        mock_urlopen,
        mock_sleep,
    ):
        """
        HTTP 401属于认证错误。

        不应重试，并应记录：
        - attempts=1；
        - 处理耗时。
        """

        mock_urlopen.side_effect = (
            HTTPError(
                url="https://example.com",
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=BytesIO(
                    b"invalid api key"
                ),
            )
        )

        client = make_client()

        with self.assertRaises(
            LLMClientError
        ) as context:
            client.generate_json(
                system_prompt="输出 JSON",
                user_prompt="测试输入",
            )

        error = context.exception

        self.assertIn(
            "HTTP 401",
            str(error),
        )

        self.assertEqual(
            error.attempts,
            1,
        )

        self.assertGreaterEqual(
            error.processing_seconds,
            0.0,
        )

        self.assertEqual(
            mock_urlopen.call_count,
            1,
        )

        mock_sleep.assert_not_called()

    @patch(
        "src.llm.client.urlopen"
    )
    def test_request_disables_thinking_mode(
        self,
        mock_urlopen,
    ):
        """
        请求必须关闭DeepSeek思考模式。

        同时验证成功结果包含：
        - content；
        - attempts=1；
        - processing_seconds。
        """

        mock_urlopen.return_value = (
            make_response(
                '{"ok": true}'
            )
        )

        client = make_client()

        result = client.generate_json(
            system_prompt="输出 JSON",
            user_prompt="测试输入",
        )

        self.assertEqual(
            result.content,
            '{"ok": true}',
        )

        self.assertEqual(
            result.attempts,
            1,
        )

        self.assertGreaterEqual(
            result.processing_seconds,
            0.0,
        )

        self.assertEqual(
            mock_urlopen.call_count,
            1,
        )

        request = (
            mock_urlopen
            .call_args
            .args[0]
        )

        payload = json.loads(
            request.data.decode(
                "utf-8"
            )
        )

        self.assertEqual(
            payload["thinking"],
            {
                "type": "disabled",
            },
        )

        self.assertEqual(
            payload["response_format"],
            {
                "type": "json_object",
            },
        )

        self.assertEqual(
            payload["temperature"],
            0,
        )

        self.assertEqual(
            payload["max_tokens"],
            100,
        )


if __name__ == "__main__":
    unittest.main()