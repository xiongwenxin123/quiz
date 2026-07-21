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

    def test_normalizes_choice_ids_and_answer_text_before_validation(self) -> None:
        value = Question.model_validate(
            {
                "id": "q1",
                "type": "detail",
                "prompt": "Which answer is supported by the article?",
                "options": [
                    {"id": "1", "text": "Unsupported"},
                    {"id": "2", "text": "Supported answer"},
                ],
                "correct_answer": "Supported answer",
                "explanation": "The second option matches the source.",
                "evidence_sentence_ids": ["s1"],
                "evidence_quote": "The source supports the second option.",
                "skill": "detail reading",
                "estimated_level": "B1",
            }
        )
        self.assertEqual([item.id for item in value.options], ["A", "B"])
        self.assertEqual(value.correct_option_id, "B")

    def test_normalizes_open_answer_alias_before_validation(self) -> None:
        value = Question.model_validate(
            {
                "id": "q1",
                "type": "short_answer",
                "prompt": "What is the supported answer?",
                "answer": "The supported answer.",
                "explanation": "It is stated directly in the article.",
                "evidence_sentence_ids": ["s1"],
                "evidence_quote": "The supported answer is stated here.",
                "skill": "short answer",
                "estimated_level": "B1",
            }
        )
        self.assertEqual(value.accepted_answers, ["The supported answer."])


if __name__ == "__main__":
    unittest.main()
