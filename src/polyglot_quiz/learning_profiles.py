from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

from .models import ArticleAnalysis, ArticleDocument, TargetLanguage, VocabularyTarget


LEVEL_ORDER = {
    TargetLanguage.ENGLISH: ("A1", "A2", "B1", "B2", "C1", "C2"),
    TargetLanguage.SPANISH: ("A1", "A2", "B1", "B2", "C1", "C2"),
    TargetLanguage.JAPANESE: ("N5", "N4", "N3", "N2", "N1"),
}
WORD_RE = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", re.UNICODE)

STOPWORDS = {
    TargetLanguage.ENGLISH: {
        "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "for",
        "from", "had", "has", "have", "he", "her", "his", "i", "in", "is", "it",
        "its", "not", "of", "on", "or", "she", "that", "the", "their", "they",
        "this", "to", "was", "we", "were", "which", "will", "with", "you",
    },
    TargetLanguage.SPANISH: {
        "a", "al", "como", "con", "de", "del", "el", "ella", "ellos", "en", "es",
        "esta", "este", "ha", "la", "las", "lo", "los", "más", "no", "o", "para",
        "pero", "por", "que", "se", "sin", "son", "su", "sus", "un", "una", "y",
    },
}
JAPANESE_STOPWORDS = {
    "ある", "いる", "こと", "これ", "する", "それ", "ため", "ところ", "なる",
    "もの", "よう", "われ", "あれ",
}


@dataclass(frozen=True, slots=True)
class LearningCandidate:
    surface: str
    level: str
    evidence_sentence_id: str
    source: str
    lemma: str | None = None
    reading: str | None = None
    part_of_speech: str | None = None
    meaning_hint: str | None = None
    level_status: str | None = None


@dataclass(frozen=True, slots=True)
class GrammarCandidate:
    pattern: str
    level: str
    evidence_sentence_id: str
    source: str
    level_status: str | None = None


@dataclass(frozen=True, slots=True)
class LearningTargetSelection:
    vocabulary: tuple[LearningCandidate, ...]
    grammar: tuple[GrammarCandidate, ...]

    def prompt_json(self) -> str:
        vocabulary = []
        for item in self.vocabulary:
            candidate: dict[str, object] = {
                "surface": item.surface,
                "level": item.level,
                "sentence_id": item.evidence_sentence_id,
            }
            if item.lemma and item.lemma.casefold() != item.surface.casefold():
                candidate["lemma"] = item.lemma
            if item.reading:
                candidate["reading"] = item.reading
            if item.part_of_speech:
                candidate["pos"] = item.part_of_speech
            if item.meaning_hint:
                candidate["meaning_hint"] = item.meaning_hint
            vocabulary.append(candidate)
        return json.dumps(
            {
                "vocabulary_candidates": vocabulary,
                "grammar_candidates": [
                    {
                        "pattern": item.pattern,
                        "level": item.level,
                        "sentence_id": item.evidence_sentence_id,
                    }
                    for item in self.grammar
                ],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


@lru_cache(maxsize=3)
def _load_profile(language: TargetLanguage) -> dict[str, object]:
    data_path = resources.files("polyglot_quiz").joinpath(
        "data", f"learning-profile-{language.value}.json.gz"
    )
    with data_path.open("rb") as raw:
        with gzip.GzipFile(fileobj=raw) as compressed:
            return json.load(compressed)


def _candidate_score(language: TargetLanguage, target: str, level: str, length: int) -> tuple[int, int, int]:
    levels = LEVEL_ORDER[language]
    target_index = levels.index(target.upper())
    level_index = levels.index(level.upper())
    distance = abs(level_index - target_index)
    below_target_penalty = 1 if level_index < target_index else 0
    return distance, below_target_penalty, -length


def _near_target(language: TargetLanguage, target: str, level: str) -> bool:
    levels = LEVEL_ORDER[language]
    return abs(levels.index(level.upper()) - levels.index(target.upper())) <= 1


def _english_lemmas(token: str) -> tuple[str, ...]:
    values = [token]
    if token.endswith("ies") and len(token) > 4:
        values.append(token[:-3] + "y")
    if token.endswith("ing") and len(token) > 5:
        stem = token[:-3]
        values.extend((stem, stem + "e"))
        if len(stem) > 2 and stem[-1] == stem[-2]:
            values.append(stem[:-1])
    if token.endswith("ed") and len(token) > 4:
        stem = token[:-2]
        values.extend((stem, stem + "e"))
        if len(stem) > 2 and stem[-1] == stem[-2]:
            values.append(stem[:-1])
    if token.endswith("es") and len(token) > 4:
        values.extend((token[:-2], token[:-1]))
    elif token.endswith("s") and len(token) > 3:
        values.append(token[:-1])
    return tuple(dict.fromkeys(values))


def _select_vocabulary(
    document: ArticleDocument,
    profile: dict[str, object],
    target_level: str,
    limit: int,
) -> tuple[LearningCandidate, ...]:
    vocabulary: dict[str, dict[str, object]] = profile["vocabulary"]  # type: ignore[assignment]
    metadata: dict[str, object] = profile["metadata"]  # type: ignore[assignment]
    source = str(metadata["source"])
    level_status = str(metadata.get("level_status") or "estimate")
    found: dict[str, LearningCandidate] = {}

    if document.language == TargetLanguage.JAPANESE:
        terms = sorted(vocabulary, key=len, reverse=True)
        for sentence in document.sentences:
            for term in terms:
                if term in found or term not in sentence.text:
                    continue
                if len(term) < 2 or term in JAPANESE_STOPWORDS:
                    continue
                entry = vocabulary[term]
                found[term] = LearningCandidate(
                    surface=term,
                    lemma=term,
                    reading=str(entry.get("reading") or "") or None,
                    meaning_hint=str(entry.get("meaning_en") or "") or None,
                    level=str(entry["level"]),
                    evidence_sentence_id=sentence.id,
                    source=source,
                    level_status=level_status,
                )
    else:
        stopwords = STOPWORDS[document.language]
        for sentence in document.sentences:
            for match in WORD_RE.finditer(sentence.text):
                surface = match.group(0)
                normalized = surface.casefold()
                if normalized in stopwords or len(normalized) < 3:
                    continue
                lemmas = (
                    _english_lemmas(normalized)
                    if document.language == TargetLanguage.ENGLISH
                    else (normalized,)
                )
                lemma = next((item for item in lemmas if item in vocabulary), None)
                if lemma is None or lemma in found:
                    continue
                entry = vocabulary[lemma]
                found[lemma] = LearningCandidate(
                    surface=surface,
                    lemma=lemma,
                    part_of_speech=str(entry.get("pos") or "") or None,
                    level=str(entry["level"]),
                    evidence_sentence_id=sentence.id,
                    source=source,
                    level_status=level_status,
                )

        if document.language == TargetLanguage.ENGLISH:
            phrases = [term for term in vocabulary if " " in term and len(term) >= 4]
            for sentence in document.sentences:
                lowered = sentence.text.casefold()
                for phrase in phrases:
                    if phrase in found or not re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", lowered):
                        continue
                    entry = vocabulary[phrase]
                    found[phrase] = LearningCandidate(
                        surface=phrase,
                        lemma=phrase,
                        part_of_speech=str(entry.get("pos") or "") or None,
                        level=str(entry["level"]),
                        evidence_sentence_id=sentence.id,
                        source=source,
                        level_status=level_status,
                    )

    ranked = sorted(
        (item for item in found.values() if _near_target(document.language, target_level, item.level)),
        key=lambda item: _candidate_score(
            document.language, target_level, item.level, len(item.surface)
        ),
    )
    return tuple(ranked[:limit])


SPANISH_GRAMMAR_RULES = (
    ("A1", "hay + noun phrase", re.compile(r"\bhay\b", re.IGNORECASE)),
    ("A1", "tener que + infinitive", re.compile(r"\b(?:tengo|tiene|tienen|tenemos) que\s+\w+(?:ar|er|ir)\b", re.IGNORECASE)),
    ("A2", "ir a + infinitive", re.compile(r"\b(?:voy|va|van|vamos) a\s+\w+(?:ar|er|ir)\b", re.IGNORECASE)),
    ("A2", "pretérito perfecto", re.compile(r"\b(?:he|has|ha|hemos|han)\s+\w+(?:ado|ido)\b", re.IGNORECASE)),
    ("B1", "imperfecto", re.compile(r"\b\w+(?:aba|aban|ía|ían)\b", re.IGNORECASE)),
    ("B2", "condicional", re.compile(r"\b\w+(?:aría|ería|iría|arían|erían|irían)\b", re.IGNORECASE)),
    ("B2", "pluscuamperfecto de subjuntivo", re.compile(r"\b(?:hubiera|hubiese|hubieran|hubiesen)\s+\w+(?:ado|ido)\b", re.IGNORECASE)),
    ("C1", "de ahí que + subjuntivo", re.compile(r"\bde ahí que\b", re.IGNORECASE)),
    ("C1", "por más que", re.compile(r"\bpor más que\b", re.IGNORECASE)),
    ("C1", "a medida que", re.compile(r"\ba medida que\b", re.IGNORECASE)),
    ("C2", "huelga decir que", re.compile(r"\bhuelga decir que\b", re.IGNORECASE)),
)

ENGLISH_GRAMMAR_RULES = (
    ("A1", "be + present participle", re.compile(r"\b(?:am|is|are)\s+\w+ing\b", re.IGNORECASE)),
    ("A2", "will + base verb", re.compile(r"\bwill\s+[a-z]+\b", re.IGNORECASE)),
    ("A2", "have to + base verb", re.compile(r"\b(?:have|has) to\s+[a-z]+\b", re.IGNORECASE)),
    ("B1", "modal may/might/could + base verb", re.compile(r"\b(?:may|might|could)\s+[a-z]+\b", re.IGNORECASE)),
    ("B1", "relative clause with who/which/that/where", re.compile(r"\b(?:who|which|that|where)\s+[a-z]+\b", re.IGNORECASE)),
    ("B1", "present perfect", re.compile(r"\b(?:have|has)\s+(?:\w+ed|been|done|gone|seen|made|taken|given|known|written)\b", re.IGNORECASE)),
    ("B1", "first conditional", re.compile(r"\bif\b[^.?!]{0,100}\bwill\b", re.IGNORECASE)),
    ("B2", "modal passive", re.compile(r"\b(?:may|might|can|could|must|should) be\s+\w+(?:ed|en)\b", re.IGNORECASE)),
    ("B2", "third conditional", re.compile(r"\bif\b[^.?!]{0,100}\bhad\s+\w+(?:ed|en)\b[^.?!]{0,100}\bwould have\b", re.IGNORECASE)),
    ("C1", "negative adverbial inversion", re.compile(r"\b(?:never|rarely|seldom|hardly)\s+(?:have|has|had|do|does|did)\b", re.IGNORECASE)),
    ("C1", "not only inversion", re.compile(r"\bnot only\s+(?:does|do|did|is|are|was|were|has|have)\b", re.IGNORECASE)),
)


def _select_grammar(
    document: ArticleDocument,
    profile: dict[str, object],
    target_level: str,
    limit: int,
) -> tuple[GrammarCandidate, ...]:
    metadata: dict[str, object] = profile["metadata"]  # type: ignore[assignment]
    source = str(metadata["source"])
    level_status = str(metadata.get("level_status") or "estimate")
    found: dict[str, GrammarCandidate] = {}

    if document.language in {TargetLanguage.ENGLISH, TargetLanguage.SPANISH}:
        rules = (
            ENGLISH_GRAMMAR_RULES
            if document.language == TargetLanguage.ENGLISH
            else SPANISH_GRAMMAR_RULES
        )
        for sentence in document.sentences:
            for level, pattern, matcher in rules:
                if pattern not in found and matcher.search(sentence.text):
                    found[pattern] = GrammarCandidate(
                        pattern=pattern,
                        level=level,
                        evidence_sentence_id=sentence.id,
                        source=f"Polyglot Quiz deterministic {document.language.value} grammar catalog",
                        level_status="cefr_profile_rule",
                    )
    if document.language != TargetLanguage.SPANISH:
        grammar: list[dict[str, object]] = profile["grammar"]  # type: ignore[assignment]
        for sentence in document.sentences:
            text = sentence.text.casefold() if document.language == TargetLanguage.ENGLISH else sentence.text
            for entry in grammar:
                pattern = str(entry["pattern"])
                if pattern in found:
                    continue
                literal = str(entry["match"])
                matched = (
                    re.search(rf"(?<!\w){re.escape(literal.casefold())}(?!\w)", text)
                    if document.language == TargetLanguage.ENGLISH
                    else literal in text
                )
                if matched:
                    found[pattern] = GrammarCandidate(
                        pattern=pattern,
                        level=str(entry["level"]),
                        evidence_sentence_id=sentence.id,
                        source=source,
                        level_status=level_status,
                    )

    ranked = sorted(
        (item for item in found.values() if _near_target(document.language, target_level, item.level)),
        key=lambda item: _candidate_score(
            document.language, target_level, item.level, len(item.pattern)
        ),
    )
    return tuple(ranked[:limit])


def select_learning_targets(
    document: ArticleDocument,
    level: str,
    *,
    vocabulary_limit: int = 10,
    grammar_limit: int = 6,
) -> LearningTargetSelection:
    profile = _load_profile(document.language)
    return LearningTargetSelection(
        vocabulary=_select_vocabulary(document, profile, level, vocabulary_limit),
        grammar=_select_grammar(document, profile, level, grammar_limit),
    )


def ground_analysis_targets(
    analysis: ArticleAnalysis,
    selection: LearningTargetSelection,
    document: ArticleDocument,
) -> tuple[ArticleAnalysis, dict[str, int]]:
    vocabulary = analysis.vocabulary_targets
    rejected_vocabulary = 0
    corrected_vocabulary = 0
    if selection.vocabulary:
        allowed = {
            (item.surface.casefold(), item.evidence_sentence_id): item
            for item in selection.vocabulary
        }
        grounded: list[VocabularyTarget] = []
        for target in vocabulary:
            candidate = allowed.get(
                (target.surface.casefold(), target.evidence_sentence_id)
            )
            if candidate is None:
                rejected_vocabulary += 1
                continue
            sentence_map = {sentence.id: sentence.text for sentence in document.sentences}
            updates: dict[str, object] = {
                "estimated_level": candidate.level,
                "source_excerpt": sentence_map[target.evidence_sentence_id],
            }
            if candidate.lemma:
                updates["lemma"] = candidate.lemma
            if candidate.reading:
                updates["reading"] = candidate.reading
            if candidate.part_of_speech:
                updates["part_of_speech"] = candidate.part_of_speech
            if any(getattr(target, field) != value for field, value in updates.items()):
                corrected_vocabulary += 1
            grounded.append(target.model_copy(update=updates))
        vocabulary = grounded[:8]

    grammar = analysis.grammar_targets
    rejected_grammar = 0
    if selection.grammar:
        allowed_grammar = {item.pattern for item in selection.grammar}
        filtered_grammar = [item for item in grammar if item in allowed_grammar]
        rejected_grammar = len(grammar) - len(filtered_grammar)
        grammar = filtered_grammar[:5]

    teaching_by_id = {
        item.paragraph_id: item
        for item in analysis.paragraph_teaching
        if item.paragraph_id in {paragraph.id for paragraph in document.paragraphs}
    }
    paragraph_teaching = [
        teaching_by_id[paragraph.id]
        for paragraph in document.paragraphs
        if paragraph.id in teaching_by_id
    ]
    grounded_analysis = analysis.model_copy(
        update={
            "vocabulary_targets": vocabulary,
            "grammar_targets": grammar,
            "paragraph_teaching": paragraph_teaching,
        }
    )
    return grounded_analysis, {
        "rejected_vocabulary": rejected_vocabulary,
        "corrected_vocabulary": corrected_vocabulary,
        "rejected_grammar": rejected_grammar,
        "missing_paragraph_teaching": len(document.paragraphs) - len(paragraph_teaching),
        "rejected_paragraph_teaching": len(analysis.paragraph_teaching) - len(teaching_by_id),
    }
