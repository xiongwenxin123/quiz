import unittest

from polyglot_quiz.extraction import document_from_text
from polyglot_quiz.learning_profiles import (
    LearningCandidate,
    LearningTargetSelection,
    ground_analysis_targets,
    select_learning_targets,
)
from polyglot_quiz.models import (
    ArticleAnalysis,
    TargetLanguage,
    VocabularyTarget,
)


class LearningProfileTests(unittest.TestCase):
    def test_english_profile_selects_near_level_content_words(self) -> None:
        document = document_from_text(
            "I am writing because researchers abandoned the old method. "
            "Many communities are planting native species, which may reduce environmental "
            "damage and improve nearby neighborhoods for residents in the city.",
            TargetLanguage.ENGLISH,
        )
        selection = select_learning_targets(document, "B1")
        surfaces = {item.surface.casefold() for item in selection.vocabulary}
        self.assertIn("environmental", surfaces)
        self.assertIn("reduce", surfaces)
        self.assertTrue(all(item.level in {"A2", "B1", "B2"} for item in selection.vocabulary))
        self.assertNotIn("I am", {item.pattern for item in selection.grammar})
        self.assertIn(
            "modal may/might/could + base verb",
            {item.pattern for item in selection.grammar},
        )

    def test_japanese_profile_matches_long_grammar_literal(self) -> None:
        document = document_from_text(
            "彼の苦労は想像に難くないと専門家が説明しました。"
            "複雑な状況にもかかわらず、関係者は慎重に結論を出すべきだと考えています。"
            "この問題について詳しい調査を続ける必要があります。",
            TargetLanguage.JAPANESE,
        )
        selection = select_learning_targets(document, "N1")
        patterns = {item.pattern for item in selection.grammar}
        self.assertIn("Noun / V dict + に難くない", patterns)
        self.assertTrue(all(len(item.surface) >= 2 for item in selection.vocabulary))

    def test_spanish_profile_combines_frequency_and_safe_grammar_rules(self) -> None:
        document = document_from_text(
            "La comunidad ha organizado un mercado para reducir los residuos. "
            "Los vecinos intercambiaban libros cada sábado porque quieren mejorar "
            "el barrio y aprovechar muchos objetos usados en otras actividades.",
            TargetLanguage.SPANISH,
        )
        selection = select_learning_targets(document, "B1")
        surfaces = {item.surface.casefold() for item in selection.vocabulary}
        patterns = {item.pattern for item in selection.grammar}
        self.assertIn("aprovechar", surfaces)
        self.assertIn("imperfecto", patterns)
        self.assertIn("pretérito perfecto", patterns)

    def test_analysis_targets_are_restricted_and_levels_are_grounded(self) -> None:
        selection = LearningTargetSelection(
            vocabulary=(
                LearningCandidate(
                    surface="environmental",
                    lemma="environmental",
                    level="B1",
                    evidence_sentence_id="s2",
                    source="test profile",
                ),
            ),
            grammar=(),
        )
        analysis = ArticleAnalysis(
            detected_language="en",
            title="Local profiles",
            summary="A summary.",
            main_idea="Local profiles constrain target selection.",
            topics=["language learning"],
            paragraph_teaching=[
                {
                    "paragraph_id": "p1",
                    "translation_zh": "本地资料约束学习目标。",
                    "vocabulary_notes_zh": [],
                    "grammar_notes_zh": [],
                    "discourse_note_zh": "说明方法。",
                    "author_intent_zh": "解释本地资料的作用。",
                }
            ],
            vocabulary_targets=[
                VocabularyTarget(
                    surface="environmental",
                    meaning_in_context="related to the environment",
                    evidence_sentence_id="s2",
                    estimated_level="C2",
                    source_excerpt="placeholder",
                    examples=[
                        {"text": "Environmental planning matters.", "translation_zh": "环境规划很重要。"},
                        {"text": "The environmental impact was measured.", "translation_zh": "环境影响得到了衡量。"},
                    ],
                ),
                VocabularyTarget(
                    surface="invented",
                    meaning_in_context="not in the local candidate list",
                    evidence_sentence_id="s1",
                    estimated_level="B1",
                    source_excerpt="placeholder",
                    examples=[
                        {"text": "This is an invented example.", "translation_zh": "这是一个虚构示例。"},
                        {"text": "The detail was invented.", "translation_zh": "这个细节是编造的。"},
                    ],
                ),
            ],
        )
        document = document_from_text(
            "Local graded profiles constrain target selection in language learning. "
            "Environmental vocabulary is checked against the source sentence before use.",
            TargetLanguage.ENGLISH,
        )
        grounded, stats = ground_analysis_targets(analysis, selection, document)
        self.assertEqual(len(grounded.vocabulary_targets), 1)
        self.assertEqual(grounded.vocabulary_targets[0].estimated_level, "B1")
        self.assertEqual(
            grounded.vocabulary_targets[0].source_excerpt,
            document.sentences[1].text,
        )
        self.assertEqual([item.paragraph_id for item in grounded.paragraph_teaching], ["p1"])
        self.assertEqual(stats["rejected_vocabulary"], 1)
        self.assertEqual(stats["corrected_vocabulary"], 1)


if __name__ == "__main__":
    unittest.main()
