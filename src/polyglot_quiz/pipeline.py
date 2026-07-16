from __future__ import annotations

from time import perf_counter

from .extraction import document_from_text, extract_url
from .models import (
    ArticleAnalysis,
    CandidateQuestions,
    QuizMetadata,
    QuizPackage,
    QuizRequest,
)
from .observability import log_event
from .profiles import get_profile
from .prompts import build_analysis_prompt, build_generation_prompt, build_repair_prompt
from .providers import LLMProvider
from .quality import QualityReport, QualityValidator, ground_evidence_quotes


class QuizQualityError(RuntimeError):
    def __init__(self, report: QualityReport) -> None:
        self.report = report
        details = "\n".join(issue.display() for issue in report.errors)
        super().__init__(f"Generated quiz failed quality checks:\n{details}")


class QuizPipeline:
    def __init__(self, provider: LLMProvider, validator: QualityValidator | None = None) -> None:
        self.provider = provider
        self.validator = validator or QualityValidator()

    def generate(self, request: QuizRequest) -> QuizPackage:
        pipeline_started = perf_counter()
        profile = get_profile(request.target_language, request.level)
        log_event(
            "pipeline_started",
            language=request.target_language.value,
            level=request.level.upper(),
            requested_questions=request.requested_total,
            question_blueprint={item.type.value: item.count for item in request.question_counts},
        )
        extraction_started = perf_counter()
        log_event(
            "extraction_started",
            source_type="text" if request.source_text is not None else "url",
            source_chars=len(request.source_text) if request.source_text is not None else None,
        )
        if request.source_text is not None:
            document = document_from_text(request.source_text, request.target_language)
        else:
            document = extract_url(str(request.source_url), request.target_language)
        log_event(
            "extraction_completed",
            method=document.extraction_method,
            text_chars=len(document.text),
            sentences=len(document.sentences),
            tokens=document.word_or_token_count,
            elapsed_ms=round((perf_counter() - extraction_started) * 1000, 1),
        )

        analysis_started = perf_counter()
        log_event("analysis_started", stage_message="正在选择词汇与语法目标")
        analysis = self.provider.generate(
            build_analysis_prompt(document, request, profile), ArticleAnalysis
        )
        log_event(
            "analysis_completed",
            title=analysis.title,
            topics=len(analysis.topics),
            vocabulary_targets=len(analysis.vocabulary_targets),
            grammar_targets=len(analysis.grammar_targets),
            elapsed_ms=round((perf_counter() - analysis_started) * 1000, 1),
        )
        if analysis.detected_language != request.target_language:
            raise ValueError(
                f"Article language is {analysis.detected_language.value}, "
                f"but request expects {request.target_language.value}"
            )

        generation_prompt = build_generation_prompt(document, analysis, request, profile)
        generation_started = perf_counter()
        log_event("generation_started", stage_message="正在生成阅读练习", prompt_chars=len(generation_prompt))
        candidate = self.provider.generate(generation_prompt, CandidateQuestions)
        log_event(
            "generation_completed",
            candidate_questions=len(candidate.questions),
            elapsed_ms=round((perf_counter() - generation_started) * 1000, 1),
        )
        grounded = ground_evidence_quotes(candidate, document)
        if grounded:
            log_event("evidence_quotes_grounded", repairs=grounded)
        attempts = 1
        report = self.validator.validate(candidate, document, request)
        log_event(
            "quality_checked",
            attempt=attempts,
            passed=report.passed,
            score=report.score,
            error_codes=[issue.code for issue in report.errors],
            warning_codes=[issue.code for issue in report.warnings],
        )
        while not report.passed and attempts <= request.max_repair_attempts:
            repair_prompt = build_repair_prompt(
                generation_prompt,
                candidate,
                [issue.display() for issue in report.errors],
            )
            log_event(
                "repair_started",
                next_attempt=attempts + 1,
                error_codes=[issue.code for issue in report.errors],
            )
            candidate = self.provider.generate(repair_prompt, CandidateQuestions)
            attempts += 1
            grounded = ground_evidence_quotes(candidate, document)
            if grounded:
                log_event("evidence_quotes_grounded", repairs=grounded)
            report = self.validator.validate(candidate, document, request)
            log_event(
                "quality_checked",
                attempt=attempts,
                passed=report.passed,
                score=report.score,
                error_codes=[issue.code for issue in report.errors],
                warning_codes=[issue.code for issue in report.warnings],
            )

        if not report.passed:
            raise QuizQualityError(report)

        package = QuizPackage(
            article=document,
            analysis=analysis,
            questions=candidate.questions,
            metadata=QuizMetadata(
                target_language=request.target_language,
                level=request.level.upper(),
                explanation_language=request.explanation_language,
                model=self.provider.model_name,
                generation_attempts=attempts,
                quality_score=report.score,
            ),
            warnings=[issue.display() for issue in report.warnings],
        )
        log_event(
            "pipeline_completed",
            questions=len(package.questions),
            quality_score=package.metadata.quality_score,
            generation_attempts=attempts,
            total_elapsed_ms=round((perf_counter() - pipeline_started) * 1000, 1),
        )
        return package
