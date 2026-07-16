import unittest

from pydantic import ValidationError

from polyglot_quiz.models import QuizRequest


TEXT = (
    "This is a sufficiently long article used to validate the request model. "
    "It contains more than eighty characters and has a second sentence for context."
)


class QuizRequestTests(unittest.TestCase):
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
