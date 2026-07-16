import unittest
from collections import deque

from polyglot_quiz.models import ArticleAnalysis, CandidateQuestions, QuizRequest
from polyglot_quiz.pipeline import QuizPipeline
from tests.test_quality import TEXT, candidate


class FakeProvider:
    model_name = "fake-json-model"

    def __init__(self, values: list[object]) -> None:
        self.values = deque(values)
        self.prompts: list[str] = []

    def generate(self, prompt: str, response_model: type[object]) -> object:
        self.prompts.append(prompt)
        value = self.values.popleft()
        if not isinstance(value, response_model):
            raise AssertionError(f"Expected {response_model}, got {type(value)}")
        return value


def analysis() -> ArticleAnalysis:
    return ArticleAnalysis(
        detected_language="en",
        title="Urban trees",
        summary="Trees reduce heat but need care.",
        main_idea="Cities must combine planting with maintenance.",
        topics=["cities", "trees"],
    )


class PipelineTests(unittest.TestCase):
    def test_repairs_failed_candidate(self) -> None:
        provider = FakeProvider(
            [analysis(), candidate("an invented quote"), candidate()]
        )
        request = QuizRequest(
            source_text=TEXT,
            target_language="en",
            level="B1",
            question_counts=[{"type": "detail", "count": 1}],
            max_repair_attempts=1,
        )
        result = QuizPipeline(provider).generate(request)
        self.assertEqual(result.metadata.generation_attempts, 2)
        self.assertEqual(result.metadata.quality_score, 1.0)
        self.assertIn("invented_quote", provider.prompts[-1])


if __name__ == "__main__":
    unittest.main()
