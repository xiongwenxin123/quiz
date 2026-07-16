from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class TargetLanguage(StrEnum):
    ENGLISH = "en"
    JAPANESE = "ja"
    SPANISH = "es"


class QuestionType(StrEnum):
    DETAIL = "detail"
    TRUE_FALSE = "true_false"
    TRUE_FALSE_NOT_GIVEN = "true_false_not_given"
    REFERENCE = "reference"
    INFORMATION_MATCHING = "information_matching"
    SUMMARY_COMPLETION = "summary_completion"
    SHORT_ANSWER = "short_answer"
    CHART_COMPLETION = "chart_completion"
    EVENT_ORDERING = "event_ordering"

    MAIN_IDEA = "main_idea"
    PARAGRAPH_MAIN_IDEA = "paragraph_main_idea"
    TEXT_STRUCTURE = "text_structure"
    PARAGRAPH_FUNCTION = "paragraph_function"
    INFERENCE = "inference"
    AUTHOR_ATTITUDE = "author_attitude"
    AUTHOR_PURPOSE = "author_purpose"
    LOGICAL_RELATIONSHIP = "logical_relationship"

    VOCABULARY_CONTEXT = "vocabulary_context"
    CLOZE = "cloze"
    GRAMMAR = "grammar"
    SENTENCE_TRANSLATION = "sentence_translation"
    SENTENCE_REWRITE = "sentence_rewrite"
    COLLOCATION_EXTRACTION = "collocation_extraction"
    TRANSLATION_TO_TARGET = "translation_to_target"
    PARAGRAPH_TRANSLATION = "paragraph_translation"
    QUESTION_FORMATION = "question_formation"

    PARAGRAPH_SUMMARY = "paragraph_summary"
    ARTICLE_SUMMARY = "article_summary"
    PARAPHRASE = "paraphrase"
    REFLECTION_WRITING = "reflection_writing"
    ARGUMENT_WRITING = "argument_writing"
    LETTER_WRITING = "letter_writing"
    RETELLING = "retelling"
    COMPARISON_WRITING = "comparison_writing"

    CRITICAL_RESPONSE = "critical_response"
    REAL_WORLD_CONNECTION = "real_world_connection"
    RESEARCH_EXTENSION = "research_extension"
    SOLUTION_PROPOSAL = "solution_proposal"


DEFAULT_QUESTION_TYPES = (
    QuestionType.MAIN_IDEA,
    QuestionType.DETAIL,
    QuestionType.INFERENCE,
    QuestionType.AUTHOR_PURPOSE,
    QuestionType.VOCABULARY_CONTEXT,
    QuestionType.CLOZE,
    QuestionType.GRAMMAR,
    QuestionType.TRUE_FALSE,
    QuestionType.SHORT_ANSWER,
)

OPEN_RESPONSE_TYPES = frozenset(
    {
        QuestionType.SUMMARY_COMPLETION,
        QuestionType.SHORT_ANSWER,
        QuestionType.CHART_COMPLETION,
        QuestionType.SENTENCE_TRANSLATION,
        QuestionType.SENTENCE_REWRITE,
        QuestionType.COLLOCATION_EXTRACTION,
        QuestionType.TRANSLATION_TO_TARGET,
        QuestionType.PARAGRAPH_TRANSLATION,
        QuestionType.QUESTION_FORMATION,
        QuestionType.PARAGRAPH_SUMMARY,
        QuestionType.ARTICLE_SUMMARY,
        QuestionType.PARAPHRASE,
        QuestionType.REFLECTION_WRITING,
        QuestionType.ARGUMENT_WRITING,
        QuestionType.LETTER_WRITING,
        QuestionType.RETELLING,
        QuestionType.COMPARISON_WRITING,
        QuestionType.CRITICAL_RESPONSE,
        QuestionType.REAL_WORLD_CONNECTION,
        QuestionType.RESEARCH_EXTENSION,
        QuestionType.SOLUTION_PROPOSAL,
    }
)

SELF_REVIEW_TYPES = frozenset(
    OPEN_RESPONSE_TYPES
    - {
        QuestionType.SUMMARY_COMPLETION,
        QuestionType.SHORT_ANSWER,
        QuestionType.CHART_COMPLETION,
    }
)


class EvaluationMode(StrEnum):
    AUTO = "auto"
    SELF_REVIEW = "self_review"


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
            QuestionCount(type=item, count=1) for item in DEFAULT_QUESTION_TYPES
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
        if sum(item.count for item in self.question_counts) > 50:
            raise ValueError("At most 50 questions may be requested")
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


class ArticleParagraph(BaseModel):
    id: str = Field(pattern=r"^p\d+$")
    text: str = Field(min_length=1)
    sentence_ids: list[str] = Field(min_length=1)


class ArticleDocument(BaseModel):
    title: str | None = None
    source_url: str | None = None
    language: TargetLanguage
    text: str = Field(min_length=80)
    sentences: list[Sentence] = Field(min_length=1)
    paragraphs: list[ArticleParagraph] = Field(min_length=1)
    word_or_token_count: int = Field(ge=1)
    extraction_method: str


class VocabularyExample(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    translation_zh: str = Field(min_length=1, max_length=500)


class VocabularyTarget(BaseModel):
    surface: str
    lemma: str | None = None
    reading: str | None = None
    part_of_speech: str | None = None
    meaning_in_context: str
    evidence_sentence_id: str = Field(pattern=r"^s\d+$")
    estimated_level: str
    source_excerpt: str = Field(min_length=1, max_length=1500)
    examples: list[VocabularyExample] = Field(min_length=2, max_length=3)


class ParagraphTeaching(BaseModel):
    paragraph_id: str = Field(pattern=r"^p\d+$")
    translation_zh: str = Field(min_length=1, max_length=3000)
    vocabulary_notes_zh: list[str] = Field(default_factory=list, max_length=6)
    grammar_notes_zh: list[str] = Field(default_factory=list, max_length=6)
    discourse_note_zh: str = Field(min_length=1, max_length=1000)
    author_intent_zh: str = Field(min_length=1, max_length=1000)


class ParagraphTeachingBatch(BaseModel):
    paragraph_teaching: list[ParagraphTeaching] = Field(min_length=1)


class ArticleAnalysis(BaseModel):
    detected_language: TargetLanguage
    title: str
    summary: str
    main_idea: str
    topics: list[str] = Field(min_length=1, max_length=8)
    vocabulary_targets: list[VocabularyTarget] = Field(default_factory=list)
    grammar_targets: list[str] = Field(default_factory=list)
    difficulty_reasons: list[str] = Field(default_factory=list)
    paragraph_teaching: list[ParagraphTeaching] = Field(default_factory=list)


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
    evaluation_mode: EvaluationMode = EvaluationMode.AUTO
    rubric: list[str] = Field(default_factory=list, max_length=8)
    word_limit: int | None = Field(default=None, ge=1, le=2000)
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
        if self.evaluation_mode == EvaluationMode.SELF_REVIEW:
            if self.options:
                raise ValueError("Self-review questions cannot have options")
            if not self.rubric:
                raise ValueError("Self-review questions need rubric criteria")
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


class GradeRequest(BaseModel):
    question: Question
    learner_answer: str = Field(min_length=1, max_length=20_000)
    evidence_sentences: list[Sentence] = Field(min_length=1, max_length=5)
    target_language: TargetLanguage
    explanation_language: str = Field(default="zh-CN", min_length=2, max_length=16)

    @model_validator(mode="after")
    def gradeable_self_review_question(self) -> GradeRequest:
        if self.question.evaluation_mode != EvaluationMode.SELF_REVIEW:
            raise ValueError("Only self-review questions use AI grading")
        supplied_ids = {sentence.id for sentence in self.evidence_sentences}
        missing = set(self.question.evidence_sentence_ids) - supplied_ids
        if missing:
            raise ValueError(
                "Missing evidence sentences for grading: " + ", ".join(sorted(missing))
            )
        return self


class GradeDimension(BaseModel):
    criterion: str = Field(min_length=2, max_length=300)
    score: int = Field(ge=0, le=5)
    feedback: str = Field(min_length=2, max_length=1000)


class GradeCandidate(BaseModel):
    dimensions: list[GradeDimension] = Field(min_length=1, max_length=8)
    strengths: list[str] = Field(min_length=1, max_length=6)
    improvements: list[str] = Field(min_length=1, max_length=6)
    overall_feedback: str = Field(min_length=2, max_length=2000)
    revised_example: str = Field(min_length=2, max_length=8000)


class GradeResponse(GradeCandidate):
    total_score: int = Field(ge=0, le=100)
    max_score: Literal[100] = 100


class QuizPackage(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    article: ArticleDocument
    analysis: ArticleAnalysis
    questions: list[Question] = Field(min_length=1)
    metadata: QuizMetadata
    warnings: list[str] = Field(default_factory=list)
