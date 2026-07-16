import random
import unittest

from polyglot_quiz.answer_order import shuffle_answer_options
from polyglot_quiz.models import CandidateQuestions
from tests.test_quality import candidate


class AnswerOrderTests(unittest.TestCase):
    def test_four_choice_answers_are_balanced_and_ids_are_updated(self) -> None:
        template = candidate().questions[0].model_dump()
        questions = []
        for index in range(1, 5):
            value = dict(template)
            value["id"] = f"q{index}"
            value["prompt"] = f"Question number {index}?"
            value["explanation"] = "选项A正确，因为它符合原文。Option B is unsupported."
            questions.append(value)
        original = CandidateQuestions.model_validate({"questions": questions})

        shuffled, distribution = shuffle_answer_options(
            original, rng=random.Random(7)
        )

        self.assertEqual(distribution, {"A": 1, "B": 1, "C": 1, "D": 1})
        for question in shuffled.questions:
            self.assertEqual([option.id for option in question.options], ["A", "B", "C", "D"])
            correct = next(
                option.text
                for option in question.options
                if option.id == question.correct_option_id
            )
            self.assertEqual(correct, "To reduce heat")
            self.assertIn(f"选项{question.correct_option_id}正确", question.explanation)

    def test_open_question_is_unchanged(self) -> None:
        value = candidate().questions[0].model_dump()
        value.update(
            {
                "type": "short_answer",
                "options": [],
                "correct_option_id": None,
                "accepted_answers": ["To reduce heat"],
            }
        )
        original = CandidateQuestions.model_validate({"questions": [value]})
        shuffled, distribution = shuffle_answer_options(
            original, rng=random.Random(7)
        )
        self.assertEqual(distribution, {})
        self.assertEqual(shuffled, original)


if __name__ == "__main__":
    unittest.main()
