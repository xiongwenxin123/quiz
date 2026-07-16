from __future__ import annotations

import logging
from pathlib import Path
from time import perf_counter
from typing import Any, Literal
from urllib.parse import urlparse
from uuid import uuid4

from .extraction import ExtractionError, _validate_public_url
from .models import (
    GradeCandidate,
    GradeRequest,
    GradeResponse,
    QuestionType,
    QuizPackage,
    QuizRequest,
)
from .observability import log_event, reset_request_id, set_request_id
from .pipeline import QuizPipeline, QuizQualityError
from .progress import ProgressStore
from .profiles import PROFILES
from .prompts import build_grading_prompt
from .providers import (
    LLMProvider,
    OpenAICompatibleProvider,
    ProviderError,
    StoredProviderSettings,
    delete_stored_provider_settings,
    provider_settings_summary,
    save_stored_provider_settings,
)


logger = logging.getLogger("uvicorn.error")


def create_app(provider: LLMProvider | None = None) -> Any:
    try:
        from fastapi import FastAPI, Header, HTTPException
        from fastapi.responses import FileResponse
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError("Install API dependencies with: pip install -e '.[api]'") from exc

    app = FastAPI(
        title="Polyglot Quiz API",
        version="0.1.0",
        description="Grounded quiz generation for English, Japanese, and Spanish articles.",
    )
    web_dir = Path(__file__).parent / "web"
    progress_store = ProgressStore()

    @app.get("/", include_in_schema=False)
    def frontend() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    app.mount("/assets", StaticFiles(directory=web_dir), name="assets")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/config")
    def config() -> dict[str, object]:
        return {
            "runtime_mode": getattr(provider, "runtime_mode", "production"),
            "supports_request_provider": True,
            "default_provider": provider_settings_summary(),
            "languages": [
                {
                    "code": profile.language.value,
                    "name": profile.name,
                    "level_system": profile.level_system,
                    "levels": list(profile.allowed_levels),
                }
                for profile in PROFILES.values()
            ],
            "question_types": [item.value for item in QuestionType],
        }

    @app.get("/v1/provider-settings")
    def get_provider_settings() -> dict[str, object]:
        return provider_settings_summary()

    @app.get("/v1/progress/{request_id}")
    def generation_progress(request_id: str) -> dict[str, object]:
        if not _valid_request_id(request_id):
            raise HTTPException(status_code=404, detail="Progress request not found")
        snapshot = progress_store.get(request_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="Progress request not found")
        return snapshot.as_dict()

    @app.put("/v1/provider-settings")
    def put_provider_settings(settings: StoredProviderSettings) -> dict[str, object]:
        try:
            _provider_from_request_headers(
                settings.api_key,
                settings.model,
                settings.base_url,
                allow_insecure_http=settings.allow_insecure_http,
                compatibility_mode=settings.compatibility_mode,
            )
            save_stored_provider_settings(settings)
            log_event(
                "default_provider_saved",
                model=settings.model,
                base_url=settings.base_url,
                allow_insecure_http=settings.allow_insecure_http,
                compatibility_mode=settings.compatibility_mode,
            )
            return provider_settings_summary()
        except (OSError, ValueError, ProviderError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.delete("/v1/provider-settings")
    def remove_provider_settings() -> dict[str, object]:
        removed = delete_stored_provider_settings()
        log_event("default_provider_deleted", removed=removed)
        return provider_settings_summary()

    @app.post("/v1/grade", response_model=GradeResponse)
    def grade_open_response(
        request: GradeRequest,
        api_key: str | None = Header(default=None, alias="X-Quiz-LLM-API-Key"),
        model: str | None = Header(default=None, alias="X-Quiz-LLM-Model"),
        base_url: str | None = Header(default=None, alias="X-Quiz-LLM-Base-URL"),
        allow_insecure_http: str | None = Header(
            default=None, alias="X-Quiz-Allow-Insecure-HTTP"
        ),
        compatibility_mode: Literal["auto", "openai", "qwen_stream"] = Header(
            default="auto", alias="X-Quiz-LLM-Compatibility"
        ),
        client_request_id: str | None = Header(default=None, alias="X-Quiz-Request-ID"),
    ) -> GradeResponse:
        if client_request_id is not None and not _valid_request_id(client_request_id):
            raise HTTPException(status_code=422, detail="Invalid request ID")
        request_id = client_request_id or uuid4().hex[:12]
        request_token = set_request_id(request_id)
        started = perf_counter()
        active_provider: LLMProvider | None = None
        log_event(
            "grading_request_received",
            question_id=request.question.id,
            question_type=request.question.type.value,
            answer_chars=len(request.learner_answer),
            rubric_dimensions=len(request.question.rubric),
            evidence_sentences=len(request.evidence_sentences),
        )
        try:
            request_provider = _provider_from_request_headers(
                api_key,
                model,
                base_url,
                allow_insecure_http=allow_insecure_http == "true",
                compatibility_mode=compatibility_mode,
            )
            active_provider = request_provider or provider or OpenAICompatibleProvider.from_env()
            candidate = active_provider.generate(
                build_grading_prompt(request), GradeCandidate
            )
            expected_criteria = request.question.rubric
            if len(candidate.dimensions) != len(expected_criteria):
                raise ProviderError(
                    "LLM grader returned an incomplete rubric",
                    retryable=False,
                )
            dimensions = [
                dimension.model_copy(update={"criterion": criterion})
                for dimension, criterion in zip(
                    candidate.dimensions, expected_criteria, strict=True
                )
            ]
            total_score = round(
                sum(dimension.score for dimension in dimensions)
                / (5 * len(dimensions))
                * 100
            )
            result = GradeResponse(
                **candidate.model_dump(exclude={"dimensions"}),
                dimensions=dimensions,
                total_score=total_score,
            )
            log_event(
                "grading_request_completed",
                question_id=request.question.id,
                question_type=request.question.type.value,
                score=result.total_score,
                dimension_scores=[item.score for item in result.dimensions],
                elapsed_ms=round((perf_counter() - started) * 1000, 1),
            )
            return result
        except ProviderError as exc:
            logger.error(
                "llm_grading_error request_id=%s model=%s base_url=%s upstream_status=%s error=%s",
                request_id,
                getattr(active_provider, "model_name", "unknown"),
                getattr(active_provider, "base_url", "unknown"),
                exc.status_code or "unknown",
                exc,
            )
            if exc.status_code == 429:
                detail = f"模型服务当前限流或额度不足，请稍后重试。请求 ID：{request_id}"
                status_code = 503
            else:
                detail = f"AI 评分失败，请查看后端日志。请求 ID：{request_id}"
                status_code = 502
            raise HTTPException(
                status_code=status_code,
                detail=detail,
                headers={"X-Request-ID": request_id},
            ) from exc
        finally:
            reset_request_id(request_token)

    @app.post("/v1/quizzes", response_model=QuizPackage)
    def generate_quiz(
        request: QuizRequest,
        api_key: str | None = Header(default=None, alias="X-Quiz-LLM-API-Key"),
        model: str | None = Header(default=None, alias="X-Quiz-LLM-Model"),
        base_url: str | None = Header(default=None, alias="X-Quiz-LLM-Base-URL"),
        allow_insecure_http: str | None = Header(
            default=None, alias="X-Quiz-Allow-Insecure-HTTP"
        ),
        compatibility_mode: Literal["auto", "openai", "qwen_stream"] = Header(
            default="auto", alias="X-Quiz-LLM-Compatibility"
        ),
        client_request_id: str | None = Header(default=None, alias="X-Quiz-Request-ID"),
    ) -> QuizPackage:
        if client_request_id is not None and not _valid_request_id(client_request_id):
            raise HTTPException(status_code=422, detail="Invalid request ID")
        request_id = client_request_id or uuid4().hex[:12]
        progress_store.start(request_id)
        request_token = set_request_id(request_id)
        request_started = perf_counter()
        active_provider: LLMProvider | None = None
        log_event(
            "request_received",
            source_type="text" if request.source_text is not None else "url",
            language=request.target_language.value,
            level=request.level.upper(),
            requested_questions=request.requested_total,
        )
        try:
            request_provider = _provider_from_request_headers(
                api_key,
                model,
                base_url,
                allow_insecure_http=allow_insecure_http == "true",
                compatibility_mode=compatibility_mode,
            )
            active_provider = request_provider or provider or OpenAICompatibleProvider.from_env()
            log_event(
                "provider_selected",
                source="request" if request_provider else ("injected" if provider else "default"),
                model=getattr(active_provider, "model_name", "unknown"),
                base_url=getattr(active_provider, "base_url", "fixture"),
                compatibility_mode=getattr(active_provider, "compatibility_mode", "fixture"),
            )
            request_validator = getattr(active_provider, "validate_request", None)
            if callable(request_validator):
                request_validator(request)
            progress_store.update(
                request_id,
                stage="provider_ready",
                message="模型服务已就绪，正在处理文章...",
                percent=5,
            )
            result = QuizPipeline(
                active_provider,
                progress=lambda stage, message, percent: progress_store.update(
                    request_id,
                    stage=stage,
                    message=message,
                    percent=percent,
                ),
            ).generate(request)
            log_event(
                "request_completed",
                status_code=200,
                questions=len(result.questions),
                quality_score=result.metadata.quality_score,
                elapsed_ms=round((perf_counter() - request_started) * 1000, 1),
            )
            progress_store.complete(request_id)
            return result
        except QuizQualityError as exc:
            log_event(
                "request_failed_quality",
                log_level=logging.ERROR,
                status_code=422,
                score=exc.report.score,
                error_codes=[issue.code for issue in exc.report.errors],
                elapsed_ms=round((perf_counter() - request_started) * 1000, 1),
            )
            raise HTTPException(
                status_code=422,
                detail={"message": str(exc), "score": exc.report.score},
            ) from exc
        except ProviderError as exc:
            logger.error(
                "llm_provider_error request_id=%s model=%s base_url=%s upstream_status=%s error=%s",
                request_id,
                getattr(active_provider, "model_name", "unknown"),
                getattr(active_provider, "base_url", "unknown"),
                exc.status_code or "unknown",
                exc,
            )
            if exc.status_code == 429:
                detail = f"模型服务当前限流或额度不足，请稍后重试。请求 ID：{request_id}"
                status_code = 503
            else:
                detail = f"模型服务请求失败，请查看后端日志。请求 ID：{request_id}"
                status_code = 502
            raise HTTPException(
                status_code=status_code,
                detail=detail,
                headers={"X-Request-ID": request_id},
            ) from exc
        except ExtractionError as exc:
            log_event(
                "request_failed_extraction",
                log_level=logging.ERROR,
                status_code=502,
                error_type=type(exc).__name__,
                error=str(exc),
                elapsed_ms=round((perf_counter() - request_started) * 1000, 1),
            )
            raise HTTPException(
                status_code=502,
                detail=f"文章下载或正文提取失败，请查看后端日志。请求 ID：{request_id}",
                headers={"X-Request-ID": request_id},
            ) from exc
        except ValueError as exc:
            log_event(
                "request_rejected",
                log_level=logging.WARNING,
                status_code=422,
                error=str(exc),
                elapsed_ms=round((perf_counter() - request_started) * 1000, 1),
            )
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        finally:
            snapshot = progress_store.get(request_id)
            if snapshot is not None and not snapshot.done:
                progress_store.fail(request_id)
            reset_request_id(request_token)

    return app


def _provider_from_request_headers(
    api_key: str | None,
    model: str | None,
    base_url: str | None,
    *,
    allow_insecure_http: bool = False,
    compatibility_mode: Literal["auto", "openai", "qwen_stream"] = "auto",
) -> OpenAICompatibleProvider | None:
    if not any((api_key, model, base_url)):
        return None
    if not api_key or not model:
        raise ValueError("前端模型配置必须同时包含 API Key 和模型名称")
    if len(api_key) > 4096 or len(model) > 200:
        raise ValueError("前端模型配置字段过长")
    endpoint = (base_url or "https://api.openai.com/v1").rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("模型 Base URL 必须是有效的 HTTP(S) 地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("模型 Base URL 不能包含凭据、查询参数或片段")
    if parsed.scheme == "http":
        if not allow_insecure_http:
            raise ValueError("使用 HTTP 模型地址前，必须在前端确认允许明文 HTTP")
    else:
        try:
            _validate_public_url(endpoint)
        except ExtractionError as exc:
            raise ValueError(f"模型 Base URL 不安全或无法解析：{exc}") from exc
    return OpenAICompatibleProvider(
        api_key=api_key,
        model=model,
        base_url=endpoint,
        compatibility_mode=compatibility_mode,
    )


app = create_app()


def _valid_request_id(value: str) -> bool:
    return 12 <= len(value) <= 64 and all(
        character.isascii() and (character.isalnum() or character in "_-")
        for character in value
    )
