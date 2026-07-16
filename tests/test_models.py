import unittest

from pydantic import ValidationError

from polyglot_quiz.models import DEFAULT_QUESTION_TYPES, Question, QuestionType, QuizRequest


TEXT = (
    "This is a sufficiently long article used to validate the request model. "
    "It contains more than eighty characters and has a second sentence for context."
)


class QuizRequestTests(unittest.TestCase):
    def test_default_blueprint_keeps_the_original_nine_types(self) -> None:
        request = QuizRequest(source_text=TEXT, target_language="en", level="B1")
        self.assertEqual(request.requested_total, 9)
        self.assertEqual(
            {item.type: item.count for item in request.question_counts},
            {item: 1 for item in DEFAULT_QUESTION_TYPES},
        )
        self.assertEqual(len(QuestionType), 38)

    def test_self_review_question_requires_a_rubric(self) -> None:
        base = {
            "id": "q1",
            "type": "article_summary",
            "prompt": "Summarize the article in 80 words.",
            "accepted_answers": ["A concise model summary."],
            "evaluation_mode": "self_review",
            "explanation": "Compare coverage, accuracy, and organization.",
            "evidence_sentence_ids": ["s1"],
            "evidence_quote": "This is a sufficiently long article",
            "skill": "summary writing",
            "estimated_level": "B1",
            "word_limit": 80,
        }
        with self.assertRaises(ValidationError):
            Question.model_validate(base)
        value = Question.model_validate({**base, "rubric": ["Covers the main idea", "Uses original wording"]})
        self.assertEqual(value.evaluation_mode.value, "self_review")

    def test_requires_exactly_one_source(self) -> None:
        with self.assertRaises(ValidationError):
            QuizRequest(source_text=TEXT, source_url="https://example.com/a", target_language="en", level="B1")

    def test_rejects_duplicate_question_types(self) -> None:
        with self.assertRaises(ValidationError):
            QuizRequest(
                source_text=TEXT,
                target_language="en",
                level="B1",
                question_counts=[
                    {"type": "detail", "count": 1},
                    {"type": "detail", "count": 1},
                ],
            )


if __name__ == "__main__":
    unittest.main()
