from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from .models import ArticleDocument, CandidateQuestions, Question, QuestionType, QuizRequest


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class QualityIssue:
    code: str
    message: str
    severity: Severity
    question_id: str | None = None

    def display(self) -> str:
        location = f" ({self.question_id})" if self.question_id else ""
        return f"[{self.severity.value}:{self.code}]{location} {self.message}"


@dataclass(frozen=True)
class QualityReport:
    issues: tuple[QualityIssue, ...]
    score: float

    @property
    def errors(self) -> tuple[QualityIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == Severity.ERROR)

    @property
    def warnings(self) -> tuple[QualityIssue, ...]:
        return tuple(issue for issue in self.issues if issue.severity == Severity.WARNING)

    @property
    def passed(self) -> bool:
        return not self.errors


def _normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _overlap_score(left: str, right: str) -> float:
    left_tokens = set(re.findall(r"[\w'\u00c0-\u024f-]+", left.casefold()))
    right_tokens = set(re.findall(r"[\w'\u00c0-\u024f-]+", right.casefold()))
    if left_tokens and right_tokens:
        return len(left_tokens & right_tokens) / max(1, min(len(left_tokens), len(right_tokens)))
    left_chars = set(re.sub(r"\s+", "", left))
    right_chars = set(re.sub(r"\s+", "", right))
    return len(left_chars & right_chars) / max(1, min(len(left_chars), len(right_chars)))


def ground_evidence_quotes(
    candidate: CandidateQuestions,
    document: ArticleDocument,
    *,
    minimum_overlap: float = 0.45,
) -> list[dict[str, object]]:
    sentence_map = {sentence.id: sentence.text for sentence in document.sentences}
    grounded: list[dict[str, object]] = []
    for question in candidate.questions:
        quote = _normalized(question.evidence_quote)
        referenced = [
            (sentence_id, sentence_map[sentence_id])
            for sentence_id in question.evidence_sentence_ids
            if sentence_id in sentence_map
        ]
        if any(quote in _normalized(text) for _, text in referenced):
            continue
        ranked = sorted(
            (
                (_overlap_score(question.evidence_quote, text), sentence_id, text)
                for sentence_id, text in referenced
            ),
            reverse=True,
        )
        if not ranked or ranked[0][0] < minimum_overlap:
            continue
        score, sentence_id, sentence_text = ranked[0]
        question.evidence_quote = sentence_text
        grounded.append(
            {
                "question_id": question.id,
                "sentence_id": sentence_id,
                "overlap": round(score, 3),
            }
        )
    return grounded


class QualityValidator:
    def validate(
        self,
        candidate: CandidateQuestions,
        document: ArticleDocument,
        request: QuizRequest,
    ) -> QualityReport:
        issues: list[QualityIssue] = []
        questions = candidate.questions
        expected_counts = {item.type: item.count for item in request.question_counts}
        actual_counts = Counter(question.type for question in questions)

        if len(questions) != request.requested_total:
            issues.append(
                QualityIssue(
                    "total_count",
                    f"Expected {request.requested_total} questions, got {len(questions)}",
                    Severity.ERROR,
                )
            )
        for question_type, expected in expected_counts.items():
            actual = actual_counts[question_type]
            if actual != expected:
                issues.append(
                    QualityIssue(
                        "type_count",
                        f"Expected {expected} {question_type.value} questions, got {actual}",
                        Severity.ERROR,
                    )
                )
        for unexpected in set(actual_counts) - set(expected_counts):
            issues.append(
                QualityIssue(
                    "unexpected_type",
                    f"Question type {unexpected.value} was not requested",
                    Severity.ERROR,
                )
            )

        expected_ids = [f"q{index}" for index in range(1, len(questions) + 1)]
        actual_ids = [question.id for question in questions]
        if actual_ids != expected_ids:
            issues.append(
                QualityIssue("question_ids", "Question IDs must be ordered q1..qN", Severity.ERROR)
            )

        sentence_map = {sentence.id: sentence.text for sentence in document.sentences}
        article_text = _normalized(document.text)
        for question in questions:
            issues.extend(self._validate_question(question, sentence_map, article_text, request))

        for index, left in enumerate(questions):
            for right in questions[index + 1 :]:
                similarity = SequenceMatcher(None, _normalized(left.prompt), _normalized(right.prompt)).ratio()
                if similarity >= 0.9:
                    issues.append(
                        QualityIssue(
                            "duplicate_prompt",
                            f"Prompt is too similar to {left.id} ({similarity:.0%})",
                            Severity.ERROR,
                            right.id,
                        )
                    )

        error_weight = sum(0.18 for issue in issues if issue.severity == Severity.ERROR)
        warning_weight = sum(0.04 for issue in issues if issue.severity == Severity.WARNING)
        score = max(0.0, min(1.0, 1.0 - error_weight - warning_weight))
        return QualityReport(tuple(issues), round(score, 3))

    def _validate_question(
        self,
        question: Question,
        sentence_map: dict[str, str],
        article_text: str,
        request: QuizRequest,
    ) -> list[QualityIssue]:
        issues: list[QualityIssue] = []
        if len(question.evidence_sentence_ids) != len(set(question.evidence_sentence_ids)):
            issues.append(
                QualityIssue("duplicate_evidence", "Evidence sentence IDs repeat", Severity.ERROR, question.id)
            )
        unknown = [sid for sid in question.evidence_sentence_ids if sid not in sentence_map]
        if unknown:
            issues.append(
                QualityIssue(
                    "unknown_evidence",
                    f"Unknown evidence IDs: {', '.join(unknown)}",
                    Severity.ERROR,
                    question.id,
                )
            )
        prompt_sentence_ids = set(
            re.findall(r"\bs\d+\b", question.prompt, flags=re.IGNORECASE)
        )
        mismatched_prompt_ids = sorted(
            prompt_sentence_ids - set(question.evidence_sentence_ids)
        )
        if mismatched_prompt_ids:
            issues.append(
                QualityIssue(
                    "prompt_evidence_mismatch",
                    "Prompt references sentence IDs not included in evidence: "
                    + ", ".join(mismatched_prompt_ids),
                    Severity.ERROR,
                    question.id,
                )
            )
        normalized_quote = _normalized(question.evidence_quote)
        if normalized_quote not in article_text:
            issues.append(
                QualityIssue(
                    "invented_quote",
                    "Evidence quote is not an exact article substring",
                    Severity.ERROR,
                    question.id,
                )
            )
        if not unknown:
            referenced_text = _normalized(" ".join(sentence_map[sid] for sid in question.evidence_sentence_ids))
            if normalized_quote not in referenced_text:
                issues.append(
                    QualityIssue(
                        "wrong_evidence_id",
                        "Evidence quote is not found in the referenced sentence(s)",
                        Severity.ERROR,
                        question.id,
                    )
                )

        if question.type == QuestionType.SHORT_ANSWER:
            if question.options:
                issues.append(
                    QualityIssue("short_answer_options", "Short answer must not have options", Severity.ERROR, question.id)
                )
        else:
            expected_options = 2 if question.type == QuestionType.TRUE_FALSE else 4
            if len(question.options) != expected_options:
                issues.append(
                    QualityIssue(
                        "option_count",
                        f"Expected {expected_options} options, got {len(question.options)}",
                        Severity.ERROR,
                        question.id,
                    )
                )
            option_texts = [_normalized(option.text) for option in question.options]
            if len(option_texts) != len(set(option_texts)):
                issues.append(
                    QualityIssue("duplicate_option", "Option texts must be unique", Severity.ERROR, question.id)
                )
            lengths = [len(option.text) for option in question.options]
            if len(lengths) >= 3 and max(lengths) > max(20, min(lengths) * 2.5):
                issues.append(
                    QualityIssue(
                        "option_length_bias",
                        "One option is much longer than another and may reveal the answer",
                        Severity.WARNING,
                        question.id,
                    )
                )

        if question.estimated_level.upper() != request.level.upper():
            issues.append(
                QualityIssue(
                    "level_drift",
                    f"Item level {question.estimated_level} differs from requested {request.level}",
                    Severity.WARNING,
                    question.id,
                )
            )
        if (
            request.target_language.value == "ja"
            and request.include_furigana
            and question.target_expression
            and not question.furigana
        ):
            issues.append(
                QualityIssue(
                    "missing_furigana",
                    "Target expression has no furigana",
                    Severity.WARNING,
                    question.id,
                )
            )
        if request.target_language.value == "es" and "?" in question.prompt:
            stripped = question.prompt.lstrip()
            if not stripped.startswith("\u00bf"):
                issues.append(
                    QualityIssue(
                        "spanish_question_mark",
                        "Spanish question is missing the opening question mark",
                        Severity.WARNING,
                        question.id,
                    )
                )
        return issues
