import unittest
from collections import deque
from threading import Lock
from time import sleep

from examples.demo_server import DEMO_SOURCE, DemoProvider
from polyglot_quiz.models import (
    ArticleAnalysis,
    CandidateQuestions,
    ParagraphTeachingBatch,
    QuizRequest,
)
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


class TrackingDemoProvider(DemoProvider):
    def __init__(self) -> None:
        super().__init__()
        self._lock = Lock()
        self.active_questions = 0
        self.max_active_questions = 0
        self.question_prompts: list[str] = []

    def generate(self, prompt: str, response_model: type[object]) -> object:
        if response_model is CandidateQuestions:
            with self._lock:
                self.active_questions += 1
                self.max_active_questions = max(
                    self.max_active_questions, self.active_questions
                )
                self.question_prompts.append(prompt)
            sleep(0.04)
            try:
                return super().generate(prompt, response_model)  # type: ignore[arg-type]
            finally:
                with self._lock:
                    self.active_questions -= 1
        return super().generate(prompt, response_model)  # type: ignore[arg-type]


def analysis() -> ArticleAnalysis:
    return ArticleAnalysis(
        detected_language="en",
        title="Urban trees",
        summary="Trees reduce heat but need care.",
        main_idea="Cities must combine planting with maintenance.",
        topics=["cities", "trees"],
        paragraph_teaching=[
            {
                "paragraph_id": "p1",
                "translation_zh": "树木可以降温，但需要养护。",
                "vocabulary_notes_zh": [],
                "grammar_notes_zh": [],
                "discourse_note_zh": "说明因果关系。",
                "author_intent_zh": "解释城市植树的条件。",
            }
        ],
    )


class PipelineTests(unittest.TestCase):
    def test_fast_incremental_questions_are_compact_parallel_and_ordered(self) -> None:
        provider = TrackingDemoProvider()
        published: list[tuple[str, object]] = []
        request = QuizRequest(
            source_text=DEMO_SOURCE,
            target_language="en",
            level="B1",
            question_counts=[
                {"type": "main_idea", "count": 1},
                {"type": "detail", "count": 1},
                {"type": "inference", "count": 1},
            ],
        )
        result = QuizPipeline(
            provider,
            publish=lambda event, payload: published.append((event, payload)),
            incremental_questions=True,
            fast_mode=True,
        ).generate(request)

        self.assertEqual(provider.max_active_questions, 2)
        self.assertEqual([item.id for item in result.questions], ["q1", "q2", "q3"])
        published_questions = [payload for event, payload in published if event == "question"]
        self.assertEqual([item.id for item in published_questions], ["q1", "q2", "q3"])
        self.assertEqual(len(provider.question_prompts), 3)
        for prompt in provider.question_prompts:
            self.assertNotIn('"paragraph_teaching"', prompt)
            self.assertNotIn('"$defs"', prompt)
            self.assertIn("The API enforces its JSON schema", prompt)
            self.assertLess(len(prompt), 7000)

    def test_long_article_teaching_is_generated_in_bounded_batches(self) -> None:
        paragraphs = [
            f"Paragraph {index} explains one distinct point about a long article clearly."
            for index in range(1, 18)
        ]

        def teaching_batch(start: int, end: int) -> ParagraphTeachingBatch:
            return ParagraphTeachingBatch(
                paragraph_teaching=[
                    {
                        "paragraph_id": f"p{index}",
                        "translation_zh": f"第 {index} 段的中文翻译。",
                        "vocabulary_notes_zh": [f"第 {index} 段词汇说明。"],
                        "grammar_notes_zh": [f"第 {index} 段语法说明。"],
                        "discourse_note_zh": f"第 {index} 段的篇章作用。",
                        "author_intent_zh": f"第 {index} 段的表达意图。",
                    }
                    for index in range(start, end + 1)
                ]
            )

        long_analysis = analysis().model_copy(update={"paragraph_teaching": []})
        long_candidate = CandidateQuestions.model_validate(
            {
                "questions": [
                    {
                        "id": "q1",
                        "type": "detail",
                        "prompt": "What does the first paragraph do?",
                        "options": [
                            {"id": "A", "text": "It explains one distinct point."},
                            {"id": "B", "text": "It lists unrelated prices."},
                            {"id": "C", "text": "It gives no information."},
                            {"id": "D", "text": "It changes the subject completely."},
                        ],
                        "correct_option_id": "A",
                        "explanation": "The first paragraph explicitly explains one distinct point.",
                        "evidence_sentence_ids": ["s1"],
                        "evidence_quote": paragraphs[0],
                        "skill": "locating detail",
                        "estimated_level": "B1",
                    }
                ]
            }
        )
        provider = FakeProvider(
            [
                long_analysis,
                teaching_batch(1, 8),
                teaching_batch(9, 16),
                teaching_batch(17, 17),
                long_candidate,
            ]
        )
        request = QuizRequest(
            source_text="\n\n".join(paragraphs),
            target_language="en",
            level="B1",
            question_counts=[{"type": "detail", "count": 1}],
        )
        result = QuizPipeline(provider).generate(request)
        self.assertEqual(len(result.article.paragraphs), 17)
        self.assertEqual(
            [item.paragraph_id for item in result.analysis.paragraph_teaching],
            [f"p{index}" for index in range(1, 18)],
        )
        teaching_prompts = provider.prompts[1:4]
        self.assertIn("p1, p2, p3, p4, p5, p6, p7, p8", teaching_prompts[0])
        self.assertIn("p9, p10, p11, p12, p13, p14, p15, p16", teaching_prompts[1])
        self.assertIn("p17", teaching_prompts[2])

    def test_repairs_failed_candidate(self) -> None:
        progress: list[tuple[str, str, int]] = []
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
        result = QuizPipeline(provider, progress=lambda *values: progress.append(values)).generate(
            request
        )
        self.assertEqual(result.metadata.generation_attempts, 2)
        self.assertEqual(result.metadata.quality_score, 1.0)
        self.assertIn("invented_quote", provider.prompts[-1])
        stages = [stage for stage, _, _ in progress]
        self.assertEqual(stages[0], "extracting")
        self.assertIn("selecting_targets", stages)
        self.assertIn("analyzing", stages)
        self.assertIn("generating", stages)
        self.assertIn("grounding", stages)
        self.assertIn("quality_check", stages)
        self.assertIn("repairing", stages)
        self.assertEqual(stages[-1], "finalizing")


if __name__ == "__main__":
    unittest.main()
