import unittest

from polyglot_quiz.extraction import document_from_text
from polyglot_quiz.models import CandidateQuestions, QuizRequest, TargetLanguage
from polyglot_quiz.quality import QualityValidator, ground_evidence_quotes


TEXT = (
    "Many cities plant trees because shade can reduce summer heat. "
    "Young trees also require water and regular care from local workers."
)


def candidate(quote: str = "shade can reduce summer heat") -> CandidateQuestions:
    return CandidateQuestions.model_validate(
        {
            "questions": [
                {
                    "id": "q1",
                    "type": "detail",
                    "prompt": "Why do many cities plant trees?",
                    "options": [
                        {"id": "A", "text": "To reduce heat"},
                        {"id": "B", "text": "To increase traffic"},
                        {"id": "C", "text": "To close parks"},
                        {"id": "D", "text": "To use more water"}
                    ],
                    "correct_option_id": "A",
                    "explanation": "The first sentence states that shade can reduce summer heat.",
                    "evidence_sentence_ids": ["s1"],
                    "evidence_quote": quote,
                    "skill": "locating detail",
                    "estimated_level": "B1"
                }
            ]
        }
    )


class QualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = QuizRequest(
            source_text=TEXT,
            target_language="en",
            level="B1",
            question_counts=[{"type": "detail", "count": 1}],
        )
        self.document = document_from_text(TEXT, TargetLanguage.ENGLISH)

    def test_valid_candidate_passes(self) -> None:
        report = QualityValidator().validate(candidate(), self.document, self.request)
        self.assertTrue(report.passed, [issue.display() for issue in report.issues])

    def test_invented_quote_fails(self) -> None:
        report = QualityValidator().validate(candidate("trees make every city silent"), self.document, self.request)
        self.assertFalse(report.passed)
        self.assertIn("invented_quote", {issue.code for issue in report.errors})

    def test_close_paraphrase_is_grounded_to_referenced_sentence(self) -> None:
        value = candidate("Many cities plant trees because their shade reduces the summer heat")
        repairs = ground_evidence_quotes(value, self.document)
        self.assertEqual(repairs[0]["question_id"], "q1")
        self.assertEqual(value.questions[0].evidence_quote, self.document.sentences[0].text)
        report = QualityValidator().validate(value, self.document, self.request)
        self.assertTrue(report.passed)

    def test_unrelated_quote_is_not_silently_grounded(self) -> None:
        value = candidate("oceans contain several unknown species")
        repairs = ground_evidence_quotes(value, self.document)
        self.assertEqual(repairs, [])
        self.assertFalse(QualityValidator().validate(value, self.document, self.request).passed)

    def test_prompt_sentence_id_must_be_declared_as_evidence(self) -> None:
        value = candidate()
        value.questions[0].prompt = "According to s2, why do many cities plant trees?"
        report = QualityValidator().validate(value, self.document, self.request)
        self.assertIn("prompt_evidence_mismatch", {issue.code for issue in report.errors})


if __name__ == "__main__":
    unittest.main()
