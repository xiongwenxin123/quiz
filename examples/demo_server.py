"""No-key UI demo server. Run with: uvicorn examples.demo_server:app --port 8000."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel

from polyglot_quiz.api import create_app
from polyglot_quiz.models import ArticleAnalysis, CandidateQuestions, QuizRequest


T = TypeVar("T", bound=BaseModel)

DEMO_SOURCE = (
    "Many cities are planting trees to reduce summer heat. Trees shade streets and release water vapor, "
    "which can lower nearby temperatures. However, urban trees need careful planning because roots may "
    "damage sidewalks and young trees require regular watering. Researchers recommend choosing native "
    "species and planting them where residents receive the greatest benefit. A successful program "
    "therefore combines environmental goals with long-term maintenance."
)
DEMO_COUNTS = {"detail": 2, "inference": 1, "vocabulary_context": 2, "grammar": 1}


ANALYSIS = ArticleAnalysis.model_validate(
    {
        "detected_language": "en",
        "title": "Greener Streets, Cooler Cities",
        "summary": "城市种树可以缓解高温，但项目要同时考虑树种、位置和长期维护。",
        "main_idea": "Urban tree programs work when environmental benefits are paired with careful planning.",
        "topics": ["城市气候", "树木", "公共规划"],
        "vocabulary_targets": [
            {
                "surface": "native species",
                "lemma": "native species",
                "part_of_speech": "noun phrase",
                "meaning_in_context": "当地自然生长、适应本地环境的物种",
                "evidence_sentence_id": "s4",
                "estimated_level": "B1",
            },
            {
                "surface": "maintenance",
                "lemma": "maintenance",
                "part_of_speech": "noun",
                "meaning_in_context": "为使树木长期健康而进行的维护工作",
                "evidence_sentence_id": "s5",
                "estimated_level": "B1",
            },
        ],
        "grammar_targets": ["relative clause with which"],
        "difficulty_reasons": ["The article uses cause-and-effect relations and planning vocabulary."],
    }
)

QUESTIONS = CandidateQuestions.model_validate(
    {
        "questions": [
            {
                "id": "q1",
                "type": "detail",
                "prompt": "How can trees lower temperatures in cities?",
                "options": [
                    {"id": "A", "text": "By shading streets and releasing water vapor"},
                    {"id": "B", "text": "By making sidewalks wider"},
                    {"id": "C", "text": "By reducing the number of residents"},
                    {"id": "D", "text": "By moving buildings farther apart"},
                ],
                "correct_option_id": "A",
                "explanation": "第二句直接说明树木通过遮阴和释放水汽降低附近温度。",
                "evidence_sentence_ids": ["s2"],
                "evidence_quote": "Trees shade streets and release water vapor, which can lower nearby temperatures.",
                "skill": "locating detail",
                "estimated_level": "B1",
            },
            {
                "id": "q2",
                "type": "detail",
                "prompt": "What do researchers recommend when planning an urban tree program?",
                "options": [
                    {"id": "A", "text": "Planting every available species"},
                    {"id": "B", "text": "Choosing native species and useful locations"},
                    {"id": "C", "text": "Avoiding neighborhoods with residents"},
                    {"id": "D", "text": "Replacing sidewalks before planting"},
                ],
                "correct_option_id": "B",
                "explanation": "研究者建议选择本地物种，并种在居民最能受益的位置。",
                "evidence_sentence_ids": ["s4"],
                "evidence_quote": "Researchers recommend choosing native species and planting them where residents receive the greatest benefit.",
                "skill": "locating detail",
                "estimated_level": "B1",
            },
            {
                "id": "q3",
                "type": "inference",
                "prompt": "What can be inferred about a successful tree-planting program?",
                "options": [
                    {"id": "A", "text": "Planting is the only important stage"},
                    {"id": "B", "text": "Young trees can survive without water"},
                    {"id": "C", "text": "Ongoing care must be included in the plan"},
                    {"id": "D", "text": "Native trees never affect sidewalks"},
                ],
                "correct_option_id": "C",
                "explanation": "末句把环境目标与长期维护并列为成功条件，因此项目不能在种植后立即结束。",
                "evidence_sentence_ids": ["s5"],
                "evidence_quote": "A successful program therefore combines environmental goals with long-term maintenance.",
                "skill": "supported inference",
                "estimated_level": "B1",
            },
            {
                "id": "q4",
                "type": "vocabulary_context",
                "prompt": "What does “native species” most likely mean in this article?",
                "options": [
                    {"id": "A", "text": "Plants naturally suited to the local area"},
                    {"id": "B", "text": "The tallest trees available for sale"},
                    {"id": "C", "text": "Plants imported from distant climates"},
                    {"id": "D", "text": "Trees grown only inside buildings"},
                ],
                "correct_option_id": "A",
                "explanation": "这里的 native species 指本地原生、适应当地环境的物种。",
                "evidence_sentence_ids": ["s4"],
                "evidence_quote": "choosing native species",
                "skill": "meaning in context",
                "estimated_level": "B1",
                "target_expression": "native species",
            },
            {
                "id": "q5",
                "type": "vocabulary_context",
                "prompt": "In the final sentence, what does “maintenance” refer to?",
                "options": [
                    {"id": "A", "text": "Selling trees to residents"},
                    {"id": "B", "text": "Measuring daily traffic"},
                    {"id": "C", "text": "Removing every mature tree"},
                    {"id": "D", "text": "Continuing care after trees are planted"},
                ],
                "correct_option_id": "D",
                "explanation": "结合上文幼树需要定期浇水，maintenance 表示种植后的持续养护。",
                "evidence_sentence_ids": ["s3", "s5"],
                "evidence_quote": "long-term maintenance",
                "skill": "meaning in context",
                "estimated_level": "B1",
                "target_expression": "maintenance",
            },
            {
                "id": "q6",
                "type": "grammar",
                "prompt": "What does “which” refer to in the second sentence?",
                "options": [
                    {"id": "A", "text": "The combined effect of shade and water vapor"},
                    {"id": "B", "text": "Only the city sidewalks"},
                    {"id": "C", "text": "The regular watering schedule"},
                    {"id": "D", "text": "The choice of native species"},
                ],
                "correct_option_id": "A",
                "explanation": "which 引导非限制性关系从句，指代前面的遮阴和释放水汽这一作用。",
                "evidence_sentence_ids": ["s2"],
                "evidence_quote": "Trees shade streets and release water vapor, which can lower nearby temperatures.",
                "skill": "reference and cohesion",
                "estimated_level": "B1",
                "target_expression": "which",
            },
        ]
    }
)


class DemoProvider:
    model_name = "demo-fixture"
    runtime_mode = "demo"

    def validate_request(self, request: QuizRequest) -> None:
        counts = {item.type.value: item.count for item in request.question_counts if item.count}
        valid = (
            request.source_text == DEMO_SOURCE
            and request.target_language.value == "en"
            and request.level.upper() == "B1"
            and counts == DEMO_COUNTS
        )
        if not valid:
            raise ValueError(
                "当前运行的是无密钥演示服务，只支持点击“载入示例”后的英文 B1 默认 6 题。"
                "使用自己的文章需要配置 QUIZ_LLM_API_KEY 和 QUIZ_LLM_MODEL，"
                "然后启动 polyglot_quiz.api:app。"
            )

    def generate(self, prompt: str, response_model: type[T]) -> T:
        if response_model is ArticleAnalysis:
            return ANALYSIS.model_copy(deep=True)  # type: ignore[return-value]
        if response_model is CandidateQuestions:
            return QUESTIONS.model_copy(deep=True)  # type: ignore[return-value]
        raise TypeError(f"Unsupported response model: {response_model}")


app = create_app(DemoProvider())
