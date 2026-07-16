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

    def test_cloze_blank_reconstructs_quote_and_corrects_evidence_id(self) -> None:
        value = CandidateQuestions.model_validate(
            {
                "questions": [
                    {
                        "id": "q1",
                        "type": "cloze",
                        "prompt": "Complete the sentence: Young trees also require ____ and regular care from local workers.",
                        "options": [
                            {"id": "A", "text": "water"},
                            {"id": "B", "text": "traffic"},
                            {"id": "C", "text": "noise"},
                            {"id": "D", "text": "concrete"},
                        ],
                        "correct_option_id": "A",
                        "explanation": "The source sentence uses water in this context.",
                        "evidence_sentence_ids": ["s1"],
                        "evidence_quote": "Young trees also require ____ and regular care from local workers.",
                        "skill": "contextual cloze",
                        "estimated_level": "B1",
                    }
                ]
            }
        )
        request = QuizRequest(
            source_text=TEXT,
            target_language="en",
            level="B1",
            question_counts=[{"type": "cloze", "count": 1}],
        )
        repairs = ground_evidence_quotes(value, self.document)
        self.assertEqual(repairs[0]["strategy"], "cloze_reconstruction")
        self.assertEqual(value.questions[0].evidence_sentence_ids, ["s2"])
        self.assertEqual(value.questions[0].evidence_quote, self.document.sentences[1].text)
        self.assertTrue(QualityValidator().validate(value, self.document, request).passed)

    def test_true_false_not_given_requires_three_options(self) -> None:
        value = candidate()
        value.questions[0].type = "true_false_not_given"
        value.questions[0].options = value.questions[0].options[:3]
        request = QuizRequest(
            source_text=TEXT,
            target_language="en",
            level="B1",
            question_counts=[{"type": "true_false_not_given", "count": 1}],
        )
        self.assertTrue(QualityValidator().validate(value, self.document, request).passed)

    def test_open_writing_uses_self_review_rubric(self) -> None:
        value = CandidateQuestions.model_validate(
            {
                "questions": [
                    {
                        "id": "q1",
                        "type": "article_summary",
                        "prompt": "Summarize the article in no more than 40 words.",
                        "accepted_answers": ["Cities plant trees for shade, while young trees need water and regular care."],
                        "evaluation_mode": "self_review",
                        "rubric": ["Includes the heat benefit", "Includes the need for ongoing care"],
                        "word_limit": 40,
                        "explanation": "A good summary includes both the benefit and the maintenance need.",
                        "evidence_sentence_ids": ["s1", "s2"],
                        "evidence_quote": "Many cities plant trees because shade can reduce summer heat.",
                        "skill": "summary writing",
                        "estimated_level": "B1",
                    }
                ]
            }
        )
        request = QuizRequest(
            source_text=TEXT,
            target_language="en",
            level="B1",
            question_counts=[{"type": "article_summary", "count": 1}],
        )
        self.assertTrue(QualityValidator().validate(value, self.document, request).passed)


if __name__ == "__main__":
    unittest.main()
