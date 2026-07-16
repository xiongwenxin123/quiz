from __future__ import annotations

from dataclasses import dataclass

from .models import DEFAULT_QUESTION_TYPES, QuestionType, TargetLanguage


@dataclass(frozen=True)
class LanguageProfile:
    language: TargetLanguage
    name: str
    level_system: str
    allowed_levels: tuple[str, ...]
    analysis_rules: tuple[str, ...]
    generation_rules: tuple[str, ...]
    grammar_focus: tuple[str, ...]
    avoid: tuple[str, ...]


PROFILES: dict[TargetLanguage, LanguageProfile] = {
    TargetLanguage.ENGLISH: LanguageProfile(
        language=TargetLanguage.ENGLISH,
        name="English",
        level_system="CEFR",
        allowed_levels=("A1", "A2", "B1", "B2", "C1", "C2"),
        analysis_rules=(
            "Estimate lexical and syntactic difficulty against CEFR descriptors.",
            "Identify phrasal verbs, collocations, discourse markers, and referents.",
            "Treat the meaning in this article as authoritative, not the most common dictionary sense.",
        ),
        generation_rules=(
            "Use natural English in stems and keep all options grammatically parallel.",
            "For vocabulary distractors, use plausible senses or same-part-of-speech words.",
            "For cloze items, preserve collocation and register constraints.",
        ),
        grammar_focus=(
            "tense and aspect",
            "modals",
            "relative clauses",
            "conditionals",
            "articles and prepositions",
            "reference and cohesion",
        ),
        avoid=(
            "testing obscure trivia",
            "options that differ only through awkward grammar",
            "vocabulary definitions unsupported by context",
        ),
    ),
    TargetLanguage.JAPANESE: LanguageProfile(
        language=TargetLanguage.JAPANESE,
        name="Japanese",
        level_system="JLPT",
        allowed_levels=("N5", "N4", "N3", "N2", "N1"),
        analysis_rules=(
            "Estimate difficulty with JLPT as a useful approximation, not a certified label.",
            "Record dictionary form, reading, particles, conjugation, and politeness level.",
            "Resolve omitted subjects and demonstrative/reference expressions only from context.",
        ),
        generation_rules=(
            "Write idiomatic Japanese rather than translated English question patterns.",
            "When requested, put readings in the furigana field; do not alter the source quote.",
            "Reading distractors must match the displayed kanji; particle and conjugation distractors must remain locally plausible.",
            "Accept orthographic variants only when they are genuinely equivalent in this context.",
        ),
        grammar_focus=(
            "particles",
            "verb and adjective conjugation",
            "transitive and intransitive pairs",
            "relative clauses",
            "sentence-final modality",
            "honorific and politeness register",
            "ellipsis and reference",
        ),
        avoid=(
            "claiming a word has one fixed JLPT level across all lists",
            "inventing furigana without checking the contextual reading",
            "mixing plain and polite register accidentally",
            "questions whose answer depends on pitch accent",
        ),
    ),
    TargetLanguage.SPANISH: LanguageProfile(
        language=TargetLanguage.SPANISH,
        name="Spanish",
        level_system="CEFR",
        allowed_levels=("A1", "A2", "B1", "B2", "C1", "C2"),
        analysis_rules=(
            "Estimate lexical and syntactic difficulty against CEFR descriptors.",
            "Identify the regional variety and preserve it unless neutral Spanish is requested.",
            "Record lemma, gender, number, mood, tense, clitics, and fixed expressions when relevant.",
        ),
        generation_rules=(
            "Use idiomatic Spanish with correct accents and inverted question marks.",
            "Keep person, gender, number, tense, and register consistent across options.",
            "For vocabulary distractors, prefer plausible same-part-of-speech alternatives.",
            "Honor the requested regional variant without stereotyping vocabulary.",
        ),
        grammar_focus=(
            "ser and estar",
            "por and para",
            "preterite and imperfect",
            "subjunctive and indicative",
            "object pronouns and clitics",
            "gender and number agreement",
            "personal a and prepositions",
        ),
        avoid=(
            "mixing vosotros and ustedes paradigms without a regional reason",
            "dropping written accent marks",
            "treating all regional vocabulary as interchangeable",
            "using translation equivalence as sole evidence for an answer",
        ),
    ),
}


def get_profile(language: TargetLanguage, level: str) -> LanguageProfile:
    profile = PROFILES[language]
    normalized = level.upper()
    if normalized not in profile.allowed_levels:
        allowed = ", ".join(profile.allowed_levels)
        raise ValueError(f"Invalid {profile.level_system} level {level!r}; use one of: {allowed}")
    return profile


DEFAULT_TYPES: dict[TargetLanguage, tuple[QuestionType, ...]] = {
    language: DEFAULT_QUESTION_TYPES for language in TargetLanguage
}
