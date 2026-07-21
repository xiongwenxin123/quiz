from __future__ import annotations

import os
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import copy_context
from time import perf_counter
from typing import Callable

from .answer_order import shuffle_answer_options
from .extraction import document_from_text, extract_url
from .learning_profiles import ground_analysis_targets, select_learning_targets
from .models import (
    ArticleAnalysis,
    ArticleDocument,
    CandidateQuestions,
    ParagraphTeachingBatch,
    Question,
    QuestionCount,
    QuestionType,
    QuizMetadata,
    QuizPackage,
    QuizRequest,
)
from .observability import log_event
from .profiles import LanguageProfile, get_profile
from .prompts import (
    build_analysis_prompt,
    build_generation_prompt,
    build_paragraph_teaching_prompt,
    build_repair_prompt,
)
from .providers import LLMProvider, ProviderError
from .quality import QualityReport, QualityValidator, ground_evidence_quotes


class QuizQualityError(RuntimeError):
    def __init__(self, report: QualityReport) -> None:
        self.report = report
        details = "\n".join(issue.display() for issue in report.errors)
        super().__init__(f"Generated quiz failed quality checks:\n{details}")


class QuizPipeline:
    PARAGRAPH_TEACHING_BATCH_SIZE = 8

    def __init__(
        self,
        provider: LLMProvider,
        validator: QualityValidator | None = None,
        progress: Callable[[str, str, int], None] | None = None,
        publish: Callable[[str, object], None] | None = None,
        incremental_questions: bool = False,
        fast_mode: bool = False,
    ) -> None:
        self.provider = provider
        self.validator = validator or QualityValidator()
        self.progress = progress
        self.publish = publish
        self.incremental_questions = incremental_questions
        self.fast_mode = fast_mode

    def _progress(self, stage: str, message: str, percent: int) -> None:
        if self.progress:
            self.progress(stage, message, percent)

    def _publish(self, event: str, payload: object) -> None:
        if self.publish:
            self.publish(event, payload)

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
        self._progress(
            "extracting",
            "正在解析文章正文..." if request.source_text is not None else "正在下载并提取文章...",
            10,
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
        self._publish("source", document)

        target_selection_started = perf_counter()
        self._progress("selecting_targets", "正在本地匹配分级词汇与语法...", 25)
        local_targets = select_learning_targets(document, request.level)
        log_event(
            "learning_targets_selected",
            vocabulary_candidates=len(local_targets.vocabulary),
            grammar_candidates=len(local_targets.grammar),
            vocabulary_sources=sorted({item.source for item in local_targets.vocabulary}),
            grammar_sources=sorted({item.source for item in local_targets.grammar}),
            elapsed_ms=round((perf_counter() - target_selection_started) * 1000, 1),
        )

        analysis_started = perf_counter()
        self._progress("analyzing", "模型正在生成摘要与语境释义...", 38)
        log_event("analysis_started", stage_message="正在生成摘要与语境释义")
        analysis = self._generate_model(
            build_analysis_prompt(
                document,
                request,
                profile,
                local_targets,
                compact=self.fast_mode,
            ),
            ArticleAnalysis,
            max_tokens=3500,
        )
        analysis, grounding_stats = ground_analysis_targets(analysis, local_targets, document)
        if analysis.detected_language != request.target_language:
            raise ValueError(
                f"Article language is {analysis.detected_language.value}, "
                f"but request expects {request.target_language.value}"
            )

        # Let readers start immediately while any missing paragraph teaching is filled in.
        self._publish(
            "article",
            {
                "article": document,
                "analysis": analysis.model_copy(update={"vocabulary_targets": []}),
            },
        )
        missing_paragraph_ids = [
            paragraph.id
            for paragraph in document.paragraphs
            if paragraph.id not in {item.paragraph_id for item in analysis.paragraph_teaching}
        ]
        if missing_paragraph_ids:
            log_event(
                "paragraph_teaching_repair_started",
                missing_paragraphs=len(missing_paragraph_ids),
                batch_size=self.PARAGRAPH_TEACHING_BATCH_SIZE,
            )
            patch_by_id = {}
            batches = [
                missing_paragraph_ids[index : index + self.PARAGRAPH_TEACHING_BATCH_SIZE]
                for index in range(0, len(missing_paragraph_ids), self.PARAGRAPH_TEACHING_BATCH_SIZE)
            ]
            teaching_futures: list[Future[ParagraphTeachingBatch]] = []
            teaching_workers = min(
                len(batches),
                _worker_count("QUIZ_PROGRESSIVE_TEACHING_WORKERS", 2)
                if self.fast_mode
                else 1,
            )
            teaching_executor = ThreadPoolExecutor(
                max_workers=max(1, teaching_workers),
                thread_name_prefix="paragraph-teaching",
            )
            for paragraph_batch in batches:
                context = copy_context()
                teaching_futures.append(
                    teaching_executor.submit(
                        context.run,
                        self._generate_model,
                        build_paragraph_teaching_prompt(
                            document,
                            paragraph_batch,
                            compact=self.fast_mode,
                        ),
                        ParagraphTeachingBatch,
                        3000,
                    )
                )
            for batch_index, (paragraph_batch, teaching_future) in enumerate(
                zip(batches, teaching_futures, strict=True), 1
            ):
                self._progress(
                    "paragraph_teaching",
                    f"模型正在生成逐段翻译与教学（{batch_index}/{len(batches)}）...",
                    42 + round(16 * batch_index / len(batches)),
                )
                log_event(
                    "paragraph_teaching_batch_started",
                    batch=batch_index,
                    batches=len(batches),
                    paragraph_ids=paragraph_batch,
                )
                teaching_patch = teaching_future.result()
                requested_ids = set(paragraph_batch)
                batch_by_id = {
                    item.paragraph_id: item
                    for item in teaching_patch.paragraph_teaching
                    if item.paragraph_id in requested_ids
                }
                missing_from_batch = requested_ids - set(batch_by_id)
                if missing_from_batch:
                    raise ValueError(
                        "Model did not provide teaching content for paragraphs: "
                        + ", ".join(sorted(missing_from_batch))
                    )
                patch_by_id.update(batch_by_id)
                analysis = analysis.model_copy(
                    update={
                        "paragraph_teaching": [
                            *analysis.paragraph_teaching,
                            *[
                                batch_by_id[paragraph_id]
                                for paragraph_id in paragraph_batch
                                if paragraph_id in batch_by_id
                            ],
                        ]
                    }
                )
                self._publish(
                    "article",
                    {
                        "article": document,
                        "analysis": analysis.model_copy(update={"vocabulary_targets": []}),
                    },
                )
                log_event(
                    "paragraph_teaching_batch_completed",
                    batch=batch_index,
                    batches=len(batches),
                    paragraphs=len(batch_by_id),
                )
            teaching_executor.shutdown(wait=True)
            log_event(
                "paragraph_teaching_repair_completed",
                repaired_paragraphs=len(patch_by_id),
            )
        log_event("analysis_targets_grounded", **grounding_stats)
        log_event(
            "analysis_completed",
            title=analysis.title,
            topics=len(analysis.topics),
            vocabulary_targets=len(analysis.vocabulary_targets),
            grammar_targets=len(analysis.grammar_targets),
            elapsed_ms=round((perf_counter() - analysis_started) * 1000, 1),
        )
        self._publish(
            "article",
            {
                "article": document,
                "analysis": analysis.model_copy(update={"vocabulary_targets": []}),
            },
        )
        for vocabulary in analysis.vocabulary_targets:
            self._publish("vocabulary", vocabulary)

        if self.incremental_questions:
            candidate, report, attempts, incremental_warnings = self._generate_incrementally(
                document, analysis, request, profile
            )
        else:
            candidate, report, attempts = self._generate_batch(
                document, analysis, request, profile
            )
            incremental_warnings = []

        self._progress("finalizing", "正在整理学习内容...", 97)
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
            warnings=incremental_warnings + [issue.display() for issue in report.warnings],
        )
        log_event(
            "pipeline_completed",
            questions=len(package.questions),
            quality_score=package.metadata.quality_score,
            generation_attempts=attempts,
            total_elapsed_ms=round((perf_counter() - pipeline_started) * 1000, 1),
        )
        self._publish("complete", package)
        return package

    def _generate_batch(
        self,
        document: ArticleDocument,
        analysis: ArticleAnalysis,
        request: QuizRequest,
        profile: LanguageProfile,
    ) -> tuple[CandidateQuestions, QualityReport, int]:

        generation_prompt = build_generation_prompt(document, analysis, request, profile)
        generation_started = perf_counter()
        self._progress("generating", "模型正在生成阅读题目...", 62)
        log_event("generation_started", stage_message="正在生成阅读练习", prompt_chars=len(generation_prompt))
        candidate = self.provider.generate(generation_prompt, CandidateQuestions)
        log_event(
            "generation_completed",
            candidate_questions=len(candidate.questions),
            elapsed_ms=round((perf_counter() - generation_started) * 1000, 1),
        )
        self._progress("grounding", "正在核对题目与原文证据...", 82)
        grounded = ground_evidence_quotes(candidate, document)
        if grounded:
            log_event("evidence_quotes_grounded", repairs=grounded)
        attempts = 1
        self._progress("quality_check", "正在执行题目质量检查...", 88)
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
            self._progress(
                "repairing",
                f"质量检查未通过，模型正在返修（第 {attempts + 1} 次）...",
                91,
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

        self._progress("finalizing", "正在随机排列答案选项...", 97)
        candidate, correct_distribution = shuffle_answer_options(candidate)
        log_event(
            "answer_options_shuffled",
            correct_distribution=correct_distribution,
        )
        return candidate, report, attempts

    def _generate_incrementally(
        self,
        document: ArticleDocument,
        analysis: ArticleAnalysis,
        request: QuizRequest,
        profile: LanguageProfile,
    ) -> tuple[CandidateQuestions, QualityReport, int, list[str]]:
        requested_types = [
            item.type
            for item in request.question_counts
            for _ in range(item.count)
        ]
        questions = []
        reports: list[QualityReport] = []
        warnings: list[str] = []
        total_attempts = 0

        question_workers = min(
            len(requested_types),
            _worker_count("QUIZ_PROGRESSIVE_QUESTION_WORKERS", 2),
        )
        executor = ThreadPoolExecutor(
            max_workers=max(1, question_workers),
            thread_name_prefix="quiz-question",
        )
        futures: list[Future[tuple[Question, QualityReport, int]]] = []
        for question_type in requested_types:
            context = copy_context()
            futures.append(
                executor.submit(
                    context.run,
                    self._generate_single_question,
                    question_type,
                    document,
                    analysis,
                    request,
                    profile,
                )
            )

        for index, (question_type, future) in enumerate(
            zip(requested_types, futures, strict=True), 1
        ):
            percent = 60 + round(35 * (index - 1) / max(1, len(requested_types)))
            self._progress(
                "generating_question",
                f"正在生成第 {index}/{len(requested_types)} 题...",
                percent,
            )
            try:
                question, report, attempts = future.result()
                total_attempts += attempts
                question = question.model_copy(update={"id": f"q{len(questions) + 1}"})
                questions.append(question)
                reports.append(report)
                self._publish("question", question)
            except (ProviderError, QuizQualityError, ValueError) as exc:
                warning = f"{question_type.value} 生成失败：{' '.join(str(exc).split())[:500]}"
                warnings.append(warning)
                self._publish(
                    "question_error",
                    {"type": question_type.value, "message": warning},
                )
        executor.shutdown(wait=True)

        if not questions:
            raise ProviderError("所有题目均生成失败，文章教学内容已保留")
        average_score = sum(item.score for item in reports) / len(reports)
        combined_report = QualityReport(
            issues=tuple(warning for report in reports for warning in report.warnings),
            score=round(average_score, 3),
        )
        return (
            CandidateQuestions(questions=questions),
            combined_report,
            max(total_attempts, 1),
            warnings,
        )

    def _generate_single_question(
        self,
        question_type: QuestionType,
        document: ArticleDocument,
        analysis: ArticleAnalysis,
        request: QuizRequest,
        profile: LanguageProfile,
    ) -> tuple[Question, QualityReport, int]:
        single_request = request.model_copy(
            update={
                "question_counts": [QuestionCount(type=question_type, count=1)],
                "max_repair_attempts": min(request.max_repair_attempts, 1),
            }
        )
        prompt = build_generation_prompt(
            document,
            analysis,
            single_request,
            profile,
            compact=self.fast_mode,
        )
        candidate = self._generate_model(
            prompt, CandidateQuestions, max_tokens=1200
        )
        attempts = 1
        candidate = _normalize_question_ids(candidate)
        grounded = ground_evidence_quotes(candidate, document)
        if grounded:
            log_event("evidence_quotes_grounded", repairs=grounded)
        report = self.validator.validate(candidate, document, single_request)
        if not report.passed and single_request.max_repair_attempts:
            repair_prompt = build_repair_prompt(
                prompt,
                candidate,
                [issue.display() for issue in report.errors],
            )
            candidate = self._generate_model(
                repair_prompt, CandidateQuestions, max_tokens=1400
            )
            attempts += 1
            candidate = _normalize_question_ids(candidate)
            ground_evidence_quotes(candidate, document)
            report = self.validator.validate(candidate, document, single_request)
        if not report.passed:
            raise QuizQualityError(report)
        candidate, _ = shuffle_answer_options(candidate)
        return candidate.questions[0], report, attempts

    def _generate_model(
        self,
        prompt: str,
        response_model: type[ArticleAnalysis]
        | type[ParagraphTeachingBatch]
        | type[CandidateQuestions],
        max_tokens: int,
    ) -> ArticleAnalysis | ParagraphTeachingBatch | CandidateQuestions:
        limited_generate = getattr(self.provider, "generate_with_limit", None)
        if self.fast_mode and callable(limited_generate):
            return limited_generate(
                prompt,
                response_model,
                max_tokens=max_tokens,
            )
        return self.provider.generate(prompt, response_model)


def _normalize_question_ids(candidate: CandidateQuestions) -> CandidateQuestions:
    """Use request-local IDs before validating an independently generated batch."""
    return candidate.model_copy(
        update={
            "questions": [
                question.model_copy(update={"id": f"q{index}"})
                for index, question in enumerate(candidate.questions, 1)
            ]
        }
    )


def _worker_count(environment_name: str, default: int) -> int:
    try:
        return max(1, min(int(os.environ.get(environment_name, default)), 4))
    except (TypeError, ValueError):
        return default
