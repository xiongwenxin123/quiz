from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class TargetLanguage(StrEnum):
    ENGLISH = "en"
    JAPANESE = "ja"
    SPANISH = "es"


class QuestionType(StrEnum):
    MAIN_IDEA = "main_idea"
    DETAIL = "detail"
    INFERENCE = "inference"
    AUTHOR_PURPOSE = "author_purpose"
    VOCABULARY_CONTEXT = "vocabulary_context"
    CLOZE = "cloze"
    GRAMMAR = "grammar"
    TRUE_FALSE = "true_false"
    SHORT_ANSWER = "short_answer"


class QuestionCount(BaseModel):
    type: QuestionType
    count: Annotated[int, Field(ge=0, le=10)]


class QuizRequest(BaseModel):
    source_text: str | None = Field(default=None, min_length=80, max_length=100_000)
    source_url: HttpUrl | None = None
    target_language: TargetLanguage
    level: str
    explanation_language: str = Field(default="zh-CN", min_length=2, max_length=16)
    question_counts: list[QuestionCount] = Field(
        default_factory=lambda: [
            QuestionCount(type=QuestionType.DETAIL, count=2),
            QuestionCount(type=QuestionType.INFERENCE, count=1),
            QuestionCount(type=QuestionType.VOCABULARY_CONTEXT, count=2),
            QuestionCount(type=QuestionType.GRAMMAR, count=1),
        ]
    )
    learner_locale: str | None = Field(default=None, max_length=16)
    spanish_variant: Literal["neutral", "es-ES", "es-MX", "es-AR"] = "neutral"
    include_furigana: bool = True
    max_repair_attempts: Annotated[int, Field(ge=0, le=3)] = 1

    @model_validator(mode="after")
    def exactly_one_source(self) -> QuizRequest:
        if (self.source_text is None) == (self.source_url is None):
            raise ValueError("Provide exactly one of source_text or source_url")
        if not any(item.count for item in self.question_counts):
            raise ValueError("At least one question must be requested")
        seen: set[QuestionType] = set()
        for item in self.question_counts:
            if item.type in seen:
                raise ValueError(f"Duplicate question type: {item.type}")
            seen.add(item.type)
        return self

    @property
    def requested_total(self) -> int:
        return sum(item.count for item in self.question_counts)


class Sentence(BaseModel):
    id: str = Field(pattern=r"^s\d+$")
    text: str = Field(min_length=1)


class ArticleDocument(BaseModel):
    title: str | None = None
    source_url: str | None = None
    language: TargetLanguage
    text: str = Field(min_length=80)
    sentences: list[Sentence] = Field(min_length=1)
    word_or_token_count: int = Field(ge=1)
    extraction_method: str


class VocabularyTarget(BaseModel):
    surface: str
    lemma: str | None = None
    reading: str | None = None
    part_of_speech: str | None = None
    meaning_in_context: str
    evidence_sentence_id: str = Field(pattern=r"^s\d+$")
    estimated_level: str


class ArticleAnalysis(BaseModel):
    detected_language: TargetLanguage
    title: str
    summary: str
    main_idea: str
    topics: list[str] = Field(min_length=1, max_length=8)
    vocabulary_targets: list[VocabularyTarget] = Field(default_factory=list)
    grammar_targets: list[str] = Field(default_factory=list)
    difficulty_reasons: list[str] = Field(default_factory=list)


class AnswerOption(BaseModel):
    id: str = Field(pattern=r"^[A-F]$")
    text: str = Field(min_length=1, max_length=500)


class Question(BaseModel):
    id: str = Field(pattern=r"^q\d+$")
    type: QuestionType
    prompt: str = Field(min_length=3, max_length=1000)
    options: list[AnswerOption] = Field(default_factory=list, max_length=6)
    correct_option_id: str | None = Field(default=None, pattern=r"^[A-F]$")
    accepted_answers: list[str] = Field(default_factory=list, max_length=8)
    explanation: str = Field(min_length=3, max_length=2000)
    evidence_sentence_ids: list[str] = Field(min_length=1, max_length=5)
    evidence_quote: str = Field(min_length=1, max_length=1500)
    skill: str = Field(min_length=2, max_length=100)
    estimated_level: str = Field(min_length=1, max_length=16)
    target_expression: str | None = Field(default=None, max_length=200)
    furigana: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def answer_shape_matches_question(self) -> Question:
        if self.options:
            if len(self.options) < 2:
                raise ValueError("Choice questions need at least two options")
            option_ids = [option.id for option in self.options]
            if len(option_ids) != len(set(option_ids)):
                raise ValueError("Option IDs must be unique")
            if self.correct_option_id not in option_ids:
                raise ValueError("correct_option_id must reference an option")
        elif not self.accepted_answers:
            raise ValueError("Open questions need at least one accepted answer")
        elif self.correct_option_id is not None:
            raise ValueError("Open questions cannot have correct_option_id")
        return self


class QuizMetadata(BaseModel):
    target_language: TargetLanguage
    level: str
    explanation_language: str
    model: str
    generation_attempts: int = Field(ge=1)
    quality_score: float = Field(ge=0, le=1)


class CandidateQuestions(BaseModel):
    questions: list[Question] = Field(min_length=1)


class QuizPackage(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    article: ArticleDocument
    analysis: ArticleAnalysis
    questions: list[Question] = Field(min_length=1)
    metadata: QuizMetadata
    warnings: list[str] = Field(default_factory=list)
