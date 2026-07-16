from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from time import perf_counter
from typing import Literal, Protocol, TypeVar

import httpx
from pydantic import BaseModel, Field, ValidationError

from .observability import log_event


T = TypeVar("T", bound=BaseModel)
DEFAULT_PROVIDER_PATH = Path(
    os.environ.get("QUIZ_PROVIDER_CONFIG_PATH", ".quiz-provider.json")
)


class StoredProviderSettings(BaseModel):
    api_key: str = Field(min_length=1, max_length=4096)
    model: str = Field(min_length=1, max_length=200)
    base_url: str = Field(min_length=8, max_length=2000)
    allow_insecure_http: bool = False
    compatibility_mode: Literal["auto", "openai", "qwen_stream"] = "auto"


def load_stored_provider_settings() -> StoredProviderSettings | None:
    if not DEFAULT_PROVIDER_PATH.exists():
        return None
    try:
        return StoredProviderSettings.model_validate_json(
            DEFAULT_PROVIDER_PATH.read_text(encoding="utf-8")
        )
    except (OSError, ValidationError) as exc:
        raise ProviderError(f"Cannot load local provider settings: {exc}") from exc


def save_stored_provider_settings(settings: StoredProviderSettings) -> None:
    temporary = DEFAULT_PROVIDER_PATH.with_suffix(DEFAULT_PROVIDER_PATH.suffix + ".tmp")
    temporary.write_text(settings.model_dump_json(indent=2) + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(DEFAULT_PROVIDER_PATH)
    DEFAULT_PROVIDER_PATH.chmod(0o600)


def delete_stored_provider_settings() -> bool:
    if not DEFAULT_PROVIDER_PATH.exists():
        return False
    DEFAULT_PROVIDER_PATH.unlink()
    return True


def provider_settings_summary() -> dict[str, object]:
    env_key = os.environ.get("QUIZ_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    env_model = os.environ.get("QUIZ_LLM_MODEL")
    if env_key and env_model:
        return {
            "configured": True,
            "source": "environment",
            "model": env_model,
            "base_url": os.environ.get("QUIZ_LLM_BASE_URL", "https://api.openai.com/v1"),
            "allow_insecure_http": False,
            "compatibility_mode": os.environ.get(
                "QUIZ_LLM_COMPATIBILITY_MODE", "auto"
            ),
        }
    stored = load_stored_provider_settings()
    if stored:
        return {
            "configured": True,
            "source": "local_file",
            "model": stored.model,
            "base_url": stored.base_url,
            "allow_insecure_http": stored.allow_insecure_http,
            "compatibility_mode": stored.compatibility_mode,
        }
    return {"configured": False, "source": "none"}


class ProviderError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class LLMProvider(Protocol):
    model_name: str

    def generate(self, prompt: str, response_model: type[T]) -> T: ...


class OpenAICompatibleProvider:
    """Small JSON-mode client for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 90,
        max_attempts: int = 3,
        compatibility_mode: Literal["auto", "openai", "qwen_stream"] = "auto",
    ) -> None:
        self.api_key = api_key
        self.model_name = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_attempts = max(1, min(max_attempts, 5))
        self.compatibility_mode = compatibility_mode

    @classmethod
    def from_env(cls) -> OpenAICompatibleProvider:
        api_key = os.environ.get("QUIZ_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        model = os.environ.get("QUIZ_LLM_MODEL")
        if api_key and model:
            return cls(
                api_key=api_key,
                model=model,
                base_url=os.environ.get("QUIZ_LLM_BASE_URL", "https://api.openai.com/v1"),
                compatibility_mode=os.environ.get("QUIZ_LLM_COMPATIBILITY_MODE", "auto"),  # type: ignore[arg-type]
            )
        stored = load_stored_provider_settings()
        if stored:
            return cls(
                api_key=stored.api_key,
                model=stored.model,
                base_url=stored.base_url,
                compatibility_mode=stored.compatibility_mode,
            )
        raise ProviderError("No default model is configured")

    def generate(self, prompt: str, response_model: type[T]) -> T:
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": "Return one valid JSON object only. Follow the supplied JSON schema exactly.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__.lower(),
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
            "max_tokens": 8192,
        }
        endpoint = f"{self.base_url}/chat/completions"
        use_streaming = self.compatibility_mode == "qwen_stream" or (
            self.compatibility_mode == "auto" and self.model_name.casefold().startswith("qwen")
        )
        if use_streaming:
            payload["stream"] = True
        total_started = perf_counter()
        last_error: ProviderError | None = None
        for attempt in range(1, self.max_attempts + 1):
            log_event(
                "llm_request_started",
                model=self.model_name,
                endpoint=endpoint,
                response_schema=response_model.__name__,
                response_format="json_schema",
                prompt_chars=len(prompt),
                attempt=attempt,
                max_attempts=self.max_attempts,
                transport="sse_stream" if use_streaming else "json_response",
            )
            try:
                content = (
                    self._request_stream_once(payload, endpoint, attempt)
                    if use_streaming
                    else self._request_text_once(payload, endpoint, attempt)
                )
                cleaned = re.sub(
                    r"^\s*```(?:json)?\s*|\s*```\s*$", "", content, flags=re.IGNORECASE
                )
                try:
                    result = response_model.model_validate_json(cleaned)
                except ValidationError as exc:
                    log_event(
                        "llm_schema_validation_failed",
                        log_level=30,
                        model=self.model_name,
                        response_schema=response_model.__name__,
                        validation_errors=len(exc.errors()),
                        attempt=attempt,
                    )
                    raise ProviderError(
                        f"LLM response did not match {response_model.__name__}: {exc}",
                        retryable=True,
                    ) from exc
                log_event(
                    "llm_response_validated",
                    model=self.model_name,
                    response_schema=response_model.__name__,
                    content_chars=len(cleaned),
                    attempt=attempt,
                    total_elapsed_ms=round((perf_counter() - total_started) * 1000, 1),
                )
                return result
            except ProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self.max_attempts:
                    raise
                delay_seconds = float(attempt)
                log_event(
                    "llm_retry_scheduled",
                    log_level=30,
                    model=self.model_name,
                    attempt=attempt,
                    next_attempt=attempt + 1,
                    delay_seconds=delay_seconds,
                    reason=str(exc)[:500],
                )
                time.sleep(delay_seconds)
        raise last_error or ProviderError("LLM request failed without a result")

    def _request_stream_once(
        self,
        payload: dict[str, object],
        endpoint: str,
        attempt: int,
    ) -> str:
        started = perf_counter()
        chunks: dict[str, list[str]] = {
            "content": [],
            "reasoning": [],
            "reasoning_content": [],
        }
        event_count = 0
        response_bytes = 0
        usage: object = None
        finish_reason: object = None
        try:
            with httpx.stream(
                "POST",
                endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=self.timeout_seconds,
            ) as response:
                response.raise_for_status()
                status_code = response.status_code
                for line in response.iter_lines():
                    response_bytes += len(line.encode("utf-8"))
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        event = json.loads(data)
                    except json.JSONDecodeError:
                        log_event(
                            "llm_stream_event_invalid",
                            log_level=30,
                            model=self.model_name,
                            attempt=attempt,
                            event_preview=data[:200],
                        )
                        continue
                    event_count += 1
                    if event.get("usage") is not None:
                        usage = event["usage"]
                    choices = event.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    finish_reason = choice.get("finish_reason") or finish_reason
                    delta = choice.get("delta") or {}
                    for field in chunks:
                        value = self._coerce_text(delta.get(field))
                        if value:
                            chunks[field].append(value)
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            retryable = status_code == 429 or 500 <= status_code <= 599
            raise ProviderError(
                f"Upstream HTTP {status_code} during stream",
                status_code=status_code,
                retryable=retryable,
            ) from exc
        except httpx.HTTPError as exc:
            log_event(
                "llm_stream_connection_error",
                log_level=40,
                model=self.model_name,
                attempt=attempt,
                elapsed_ms=round((perf_counter() - started) * 1000, 1),
                error_type=type(exc).__name__,
                error=str(exc),
            )
            raise ProviderError(f"Upstream stream failed: {exc}", retryable=True) from exc

        log_event(
            "llm_stream_completed",
            model=self.model_name,
            endpoint=endpoint,
            status_code=status_code,
            elapsed_ms=round((perf_counter() - started) * 1000, 1),
            response_bytes=response_bytes,
            events=event_count,
            finish_reason=finish_reason,
            usage=usage,
            attempt=attempt,
        )
        for field in ("content", "reasoning", "reasoning_content"):
            content = "".join(chunks[field])
            if content.strip():
                log_event(
                    "llm_output_selected",
                    model=self.model_name,
                    output_field=f"delta.{field}",
                    content_chars=len(content),
                    attempt=attempt,
                )
                return content
        response_shape = {
            "events": event_count,
            "finish_reason": finish_reason,
            "usage": usage,
            "nonempty_fields": [field for field, values in chunks.items() if values],
        }
        log_event(
            "llm_empty_stream",
            log_level=30,
            model=self.model_name,
            attempt=attempt,
            response_shape=response_shape,
        )
        raise ProviderError(
            f"LLM stream returned no text output; response_shape={response_shape}", retryable=True
        )

    def _request_text_once(
        self,
        payload: dict[str, object],
        endpoint: str,
        attempt: int,
    ) -> str:
        started = perf_counter()
        try:
            response = httpx.post(
                endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            response_text = exc.response.text[:1000].replace("\n", " ").replace("\r", " ")
            if self.api_key:
                response_text = response_text.replace(self.api_key, "[REDACTED]")
            status_code = exc.response.status_code
            retryable = status_code == 429 or 500 <= status_code <= 599
            log_event(
                "llm_http_error",
                log_level=40,
                model=self.model_name,
                endpoint=endpoint,
                status_code=status_code,
                elapsed_ms=round((perf_counter() - started) * 1000, 1),
                response_excerpt=response_text or "[empty]",
                attempt=attempt,
                retryable=retryable,
            )
            raise ProviderError(
                f"Upstream HTTP {status_code}; response={response_text or '[empty]'}",
                status_code=status_code,
                retryable=retryable,
            ) from exc
        except httpx.HTTPError as exc:
            log_event(
                "llm_connection_error",
                log_level=40,
                model=self.model_name,
                endpoint=endpoint,
                elapsed_ms=round((perf_counter() - started) * 1000, 1),
                error_type=type(exc).__name__,
                error=str(exc),
                attempt=attempt,
            )
            raise ProviderError(f"Upstream connection failed: {exc}", retryable=True) from exc
        log_event(
            "llm_response_received",
            model=self.model_name,
            endpoint=endpoint,
            status_code=response.status_code,
            elapsed_ms=round((perf_counter() - started) * 1000, 1),
            response_bytes=len(response.content),
            attempt=attempt,
        )
        try:
            body = response.json()
            choice = body["choices"][0]
            message = choice.get("message") or {}
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise ProviderError(f"Upstream response shape is invalid: {exc}", retryable=True) from exc

        candidates = (
            ("message.content", message.get("content")),
            ("message.reasoning", message.get("reasoning")),
            ("message.reasoning_content", message.get("reasoning_content")),
            ("choice.text", choice.get("text")),
            ("choice.reasoning", choice.get("reasoning")),
            ("choice.content", choice.get("content")),
            ("output_text", body.get("output_text")),
        )
        for output_field, value in candidates:
            content = self._coerce_text(value)
            if content:
                log_event(
                    "llm_output_selected",
                    model=self.model_name,
                    output_field=output_field,
                    content_chars=len(content),
                    attempt=attempt,
                )
                return content

        response_shape = {
            "top_keys": sorted(str(key) for key in body),
            "choice_keys": sorted(str(key) for key in choice),
            "message_keys": sorted(str(key) for key in message),
            "finish_reason": choice.get("finish_reason"),
            "usage": body.get("usage"),
        }
        log_event(
            "llm_empty_output",
            log_level=30,
            model=self.model_name,
            attempt=attempt,
            response_shape=response_shape,
        )
        raise ProviderError(
            f"LLM returned no text output; response_shape={response_shape}", retryable=True
        )

    @staticmethod
    def _coerce_text(value: object) -> str | None:
        if isinstance(value, str) and value.strip():
            return value
        if isinstance(value, list):
            joined = "".join(
                str(part.get("text", ""))
                for part in value
                if isinstance(part, dict) and part.get("type") in {"text", "output_text"}
            )
            return joined if joined.strip() else None
        return None
