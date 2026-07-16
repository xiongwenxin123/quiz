from __future__ import annotations

from time import perf_counter
from typing import Callable

from .answer_order import shuffle_answer_options
from .extraction import document_from_text, extract_url
from .learning_profiles import ground_analysis_targets, select_learning_targets
from .models import (
    ArticleAnalysis,
    CandidateQuestions,
    ParagraphTeachingBatch,
    QuizMetadata,
    QuizPackage,
    QuizRequest,
)
from .observability import log_event
from .profiles import get_profile
from .prompts import (
    build_analysis_prompt,
    build_generation_prompt,
    build_paragraph_teaching_prompt,
    build_repair_prompt,
)
from .providers import LLMProvider
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
    ) -> None:
        self.provider = provider
        self.validator = validator or QualityValidator()
        self.progress = progress

    def _progress(self, stage: str, message: str, percent: int) -> None:
        if self.progress:
            self.progress(stage, message, percent)

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
        analysis = self.provider.generate(
            build_analysis_prompt(document, request, profile, local_targets), ArticleAnalysis
        )
        analysis, grounding_stats = ground_analysis_targets(analysis, local_targets, document)
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
            for batch_index, paragraph_batch in enumerate(batches, 1):
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
                teaching_patch = self.provider.generate(
                    build_paragraph_teaching_prompt(document, paragraph_batch),
                    ParagraphTeachingBatch,
                )
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
                log_event(
                    "paragraph_teaching_batch_completed",
                    batch=batch_index,
                    batches=len(batches),
                    paragraphs=len(batch_by_id),
                )
            analysis = analysis.model_copy(
                update={
                    "paragraph_teaching": analysis.paragraph_teaching
                    + [
                        patch_by_id[paragraph_id]
                        for paragraph_id in missing_paragraph_ids
                        if paragraph_id in patch_by_id
                    ]
                }
            )
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
        if analysis.detected_language != request.target_language:
            raise ValueError(
                f"Article language is {analysis.detected_language.value}, "
                f"but request expects {request.target_language.value}"
            )

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
