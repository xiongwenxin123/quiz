import json
import unittest
from unittest.mock import patch

import httpx

from polyglot_quiz.models import ArticleAnalysis
from polyglot_quiz.providers import OpenAICompatibleProvider, ProviderError


class FakeResponse:
    status_code = 200

    @property
    def content(self) -> bytes:
        return json.dumps(self.json()).encode()

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        content = json.dumps(
            {
                "detected_language": "es",
                "title": "Mercados",
                "summary": "Un resumen.",
                "main_idea": "La comunidad reutiliza objetos.",
                "topics": ["comunidad"],
                "vocabulary_targets": [],
                "grammar_targets": [],
                "difficulty_reasons": [],
                "paragraph_teaching": [
                    {
                        "paragraph_id": "p1",
                        "translation_zh": "社区重复利用物品。",
                        "vocabulary_notes_zh": [],
                        "grammar_notes_zh": [],
                        "discourse_note_zh": "概述文章主题。",
                        "author_intent_zh": "介绍社区实践。",
                    }
                ],
            }
        )
        return {"choices": [{"message": {"content": content}}]}


class RateLimitResponse:
    text = '{"error":"capacity exhausted"}'
    status_code = 429

    def raise_for_status(self) -> None:
        request = httpx.Request("POST", "http://llm.example/v1/chat/completions")
        response = httpx.Response(429, request=request, text=self.text)
        raise httpx.HTTPStatusError("rate limited", request=request, response=response)


class ReasoningFieldResponse:
    status_code = 200
    content = b'{"choices":[{"message":{"content":null,"reasoning":"{}"}}]}'

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        value = FakeResponse().json()
        generated = value["choices"][0]["message"]["content"]  # type: ignore[index]
        return {"choices": [{"message": {"content": None, "reasoning": generated}}]}


class EmptyOutputResponse:
    status_code = 200
    content = b'{"choices":[{"message":{"role":"assistant"},"finish_reason":"stop"}],"usage":{"completion_tokens":0}}'

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "choices": [{"message": {"role": "assistant"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 0, "total_tokens": 100},
        }


class FakeStreamResponse:
    status_code = 200

    def __init__(self, lines: list[str]) -> None:
        self.lines = lines

    def __enter__(self) -> "FakeStreamResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def raise_for_status(self) -> None:
        return None

    def iter_lines(self) -> list[str]:
        return self.lines


def analysis_json() -> str:
    return FakeResponse().json()["choices"][0]["message"]["content"]  # type: ignore[index,return-value]


class ProviderTests(unittest.TestCase):
    @patch("polyglot_quiz.providers.httpx.post", return_value=FakeResponse())
    def test_parses_json_mode_response(self, post: object) -> None:
        provider = OpenAICompatibleProvider(
            api_key="test-key", model="test-model", base_url="https://llm.example/v1"
        )
        result = provider.generate("analyze", ArticleAnalysis)
        self.assertEqual(result.detected_language.value, "es")
        kwargs = post.call_args.kwargs  # type: ignore[attr-defined]
        response_format = kwargs["json"]["response_format"]
        self.assertEqual(response_format["type"], "json_schema")
        self.assertEqual(response_format["json_schema"]["name"], "articleanalysis")
        self.assertIn("properties", response_format["json_schema"]["schema"])
        self.assertNotIn("test-key", kwargs["json"])

    @patch("polyglot_quiz.providers.httpx.post", return_value=RateLimitResponse())
    def test_preserves_upstream_rate_limit_for_backend_logging(self, post: object) -> None:
        provider = OpenAICompatibleProvider(
            api_key="secret-key",
            model="test-model",
            base_url="http://llm.example/v1",
            max_attempts=1,
        )
        with self.assertRaises(ProviderError) as raised:
            provider.generate("analyze", ArticleAnalysis)
        self.assertEqual(raised.exception.status_code, 429)
        self.assertIn("capacity exhausted", str(raised.exception))
        self.assertNotIn("secret-key", str(raised.exception))

    @patch("polyglot_quiz.providers.httpx.post", return_value=ReasoningFieldResponse())
    def test_accepts_qwen_reasoning_field_when_content_is_null(self, post: object) -> None:
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            model="qwen-model",
            base_url="http://llm.example/v1",
            compatibility_mode="openai",
        )
        with self.assertLogs("uvicorn.error", level="INFO") as logs:
            result = provider.generate("analyze", ArticleAnalysis)
        self.assertEqual(result.detected_language.value, "es")
        self.assertIn('"output_field": "message.reasoning"', "\n".join(logs.output))

    @patch("polyglot_quiz.providers.time.sleep")
    @patch(
        "polyglot_quiz.providers.httpx.post",
        side_effect=[EmptyOutputResponse(), ReasoningFieldResponse()],
    )
    def test_retries_empty_200_response_then_succeeds(self, post: object, sleep: object) -> None:
        provider = OpenAICompatibleProvider(
            api_key="test-key",
            model="qwen-model",
            base_url="http://llm.example/v1",
            compatibility_mode="openai",
        )
        with self.assertLogs("uvicorn.error", level="INFO") as logs:
            result = provider.generate("analyze", ArticleAnalysis)
        self.assertEqual(result.detected_language.value, "es")
        self.assertEqual(post.call_count, 2)  # type: ignore[attr-defined]
        sleep.assert_called_once_with(1.0)  # type: ignore[attr-defined]
        output = "\n".join(logs.output)
        self.assertIn('"event": "llm_empty_output"', output)
        self.assertIn('"completion_tokens": 0', output)
        self.assertIn('"event": "llm_retry_scheduled"', output)

    @patch("polyglot_quiz.providers.httpx.stream")
    def test_qwen_stream_aggregates_sse_content(self, stream: object) -> None:
        generated = analysis_json()
        midpoint = len(generated) // 2
        stream.return_value = FakeStreamResponse(  # type: ignore[attr-defined]
            [
                "data: " + json.dumps({"choices": [{"delta": {"content": generated[:midpoint]}}]}),
                "data: " + json.dumps({"choices": [{"delta": {"content": generated[midpoint:]}, "finish_reason": "stop"}]}),
                "data: [DONE]",
            ]
        )
        provider = OpenAICompatibleProvider(
            api_key="test-key", model="qwen-model", base_url="http://llm.example/v1"
        )
        with self.assertLogs("uvicorn.error", level="INFO") as logs:
            result = provider.generate("analyze", ArticleAnalysis)
        self.assertEqual(result.detected_language.value, "es")
        kwargs = stream.call_args.kwargs  # type: ignore[attr-defined]
        self.assertTrue(kwargs["json"]["stream"])
        self.assertIn('"transport": "sse_stream"', "\n".join(logs.output))
        self.assertIn('"output_field": "delta.content"', "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
