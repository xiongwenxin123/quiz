"""No-key UI demo server. Run with: uvicorn examples.demo_server:app --port 8000."""

from __future__ import annotations

from time import sleep
from typing import TypeVar

from pydantic import BaseModel

from polyglot_quiz.api import create_app
from polyglot_quiz.models import ArticleAnalysis, CandidateQuestions, GradeCandidate, QuizRequest


T = TypeVar("T", bound=BaseModel)

DEMO_SOURCE = (
    "Many cities are planting trees to reduce summer heat. Trees shade streets and release water vapor, "
    "which can lower nearby temperatures.\n\nHowever, urban trees need careful planning because roots may "
    "damage sidewalks and young trees require regular watering. Researchers recommend choosing native "
    "species and planting them where residents receive the greatest benefit.\n\nA successful program "
    "therefore combines environmental goals with long-term maintenance."
)
DEMO_COUNTS = {
    "main_idea": 1,
    "detail": 1,
    "inference": 1,
    "author_purpose": 1,
    "vocabulary_context": 1,
    "cloze": 1,
    "grammar": 1,
    "true_false": 1,
    "short_answer": 1,
}
SUMMARY_COUNTS = {"article_summary": 1}


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
                "source_excerpt": "Researchers recommend choosing native species and planting them where residents receive the greatest benefit.",
                "examples": [
                    {"text": "Native species usually adapt well to local conditions.", "translation_zh": "本地物种通常能很好地适应当地环境。"},
                    {"text": "The park protects several native species.", "translation_zh": "这座公园保护了几种本地物种。"},
                ],
            },
            {
                "surface": "maintenance",
                "lemma": "maintenance",
                "part_of_speech": "noun",
                "meaning_in_context": "为使树木长期健康而进行的维护工作",
                "evidence_sentence_id": "s5",
                "estimated_level": "B1",
                "source_excerpt": "A successful program therefore combines environmental goals with long-term maintenance.",
                "examples": [
                    {"text": "Regular maintenance keeps the equipment safe.", "translation_zh": "定期维护能保证设备安全。"},
                    {"text": "The bridge requires expensive maintenance.", "translation_zh": "这座桥需要成本高昂的维护。"},
                ],
            },
        ],
        "grammar_targets": ["relative clause with which"],
        "difficulty_reasons": ["The article uses cause-and-effect relations and planning vocabulary."],
        "paragraph_teaching": [
            {
                "paragraph_id": "p1",
                "translation_zh": "许多城市正在种树以缓解夏季高温。树木为街道遮阴并释放水汽，从而降低附近温度。",
                "vocabulary_notes_zh": ["reduce summer heat：缓解夏季高温", "water vapor：水汽"],
                "grammar_notes_zh": ["which 引导非限制性关系从句，补充说明树木带来的降温作用。"],
                "discourse_note_zh": "开篇介绍城市种树的背景及其主要环境效益。",
                "author_intent_zh": "用具体机制说明树木为何能够帮助城市降温。",
            },
            {
                "paragraph_id": "p2",
                "translation_zh": "然而，城市树木需要周密规划，因为树根可能破坏人行道，幼树也需要定期浇水。研究人员建议选择本地物种，并种植在居民受益最大的位置。",
                "vocabulary_notes_zh": ["native species：本地原生物种", "regular watering：定期浇水"],
                "grammar_notes_zh": ["because 引导原因状语从句。", "where 引导关系从句，说明种植的位置。"],
                "discourse_note_zh": "由环境效益转向实施难点，并给出选种和选址建议。",
                "author_intent_zh": "提醒读者城市植树需要处理基础设施、养护和公平受益等现实条件。",
            },
            {
                "paragraph_id": "p3",
                "translation_zh": "因此，一个成功的项目需要把环境目标与长期维护结合起来。",
                "vocabulary_notes_zh": ["maintenance：持续维护、养护"],
                "grammar_notes_zh": ["therefore 表示结论，承接前文的利弊分析。"],
                "discourse_note_zh": "总结全文并提出城市植树项目成功的核心条件。",
                "author_intent_zh": "强调环境目标与长期养护必须同时纳入项目设计。",
            }
        ],
    }
)

QUESTIONS = CandidateQuestions.model_validate(
    {
        "questions": [
            {
                "id": "q1",
                "type": "main_idea",
                "prompt": "What is the main idea of the article?",
                "options": [
                    {"id": "A", "text": "Urban tree programs need both environmental planning and long-term care"},
                    {"id": "B", "text": "Cities should remove sidewalks before planting any trees"},
                    {"id": "C", "text": "Only imported trees can reduce summer temperatures"},
                    {"id": "D", "text": "Residents should water every tree by themselves"},
                ],
                "correct_option_id": "A",
                "explanation": "全文先介绍树木的降温作用，再说明规划和维护要求，核心是环境效益必须与长期管理结合。",
                "evidence_sentence_ids": ["s1", "s3", "s5"],
                "evidence_quote": "A successful program therefore combines environmental goals with long-term maintenance.",
                "skill": "identifying main idea",
                "estimated_level": "B1",
            },
            {
                "id": "q2",
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
                "type": "author_purpose",
                "prompt": "Why does the author mention damaged sidewalks and regular watering?",
                "options": [
                    {"id": "A", "text": "To show why urban trees require careful planning"},
                    {"id": "B", "text": "To argue that cities should stop planting trees"},
                    {"id": "C", "text": "To compare tree prices in different cities"},
                    {"id": "D", "text": "To explain how sidewalks are manufactured"},
                ],
                "correct_option_id": "A",
                "explanation": "这两个例子具体说明了城市种树并非只需种下去，还要考虑基础设施和持续养护。",
                "evidence_sentence_ids": ["s3"],
                "evidence_quote": "However, urban trees need careful planning because roots may damage sidewalks and young trees require regular watering.",
                "skill": "author purpose",
                "estimated_level": "B1",
            },
            {
                "id": "q5",
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
                "id": "q6",
                "type": "cloze",
                "prompt": "Choose the best word to complete the sentence: Young trees require regular _____.",
                "options": [
                    {"id": "A", "text": "watering"},
                    {"id": "B", "text": "traffic"},
                    {"id": "C", "text": "concrete"},
                    {"id": "D", "text": "advertising"},
                ],
                "correct_option_id": "A",
                "explanation": "原文明确说幼树需要定期浇水，regular watering 是自然搭配。",
                "evidence_sentence_ids": ["s3"],
                "evidence_quote": "young trees require regular watering",
                "skill": "collocation in context",
                "estimated_level": "B1",
                "target_expression": "regular watering",
            },
            {
                "id": "q7",
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
            {
                "id": "q8",
                "type": "true_false",
                "prompt": "Researchers recommend using only non-native tree species.",
                "options": [
                    {"id": "A", "text": "True"},
                    {"id": "B", "text": "False"},
                ],
                "correct_option_id": "B",
                "explanation": "原文建议选择 native species，所以该陈述与原文相反。",
                "evidence_sentence_ids": ["s4"],
                "evidence_quote": "Researchers recommend choosing native species and planting them where residents receive the greatest benefit.",
                "skill": "verifying a statement",
                "estimated_level": "B1",
            },
            {
                "id": "q9",
                "type": "short_answer",
                "prompt": "What two goals does a successful urban tree program combine?",
                "options": [],
                "correct_option_id": None,
                "accepted_answers": ["environmental goals and long-term maintenance", "environmental goals with long-term maintenance"],
                "explanation": "末句直接给出成功项目需要结合的两个方面。",
                "evidence_sentence_ids": ["s5"],
                "evidence_quote": "environmental goals with long-term maintenance",
                "skill": "short answer extraction",
                "estimated_level": "B1",
            },
        ]
    }
)

SUMMARY_QUESTION = CandidateQuestions.model_validate(
    {
        "questions": [
            {
                "id": "q1",
                "type": "article_summary",
                "prompt": "Summarize the article in 40-60 words.",
                "options": [],
                "accepted_answers": [
                    "Urban trees reduce summer heat through shade and water vapor, but successful planting requires careful species selection, suitable locations, regular watering, and long-term maintenance. Cities must balance environmental goals with practical planning so residents receive lasting benefits."
                ],
                "evaluation_mode": "self_review",
                "rubric": [
                    "准确说明树木的降温作用",
                    "包含规划或养护方面的挑战",
                    "概括成功项目的关键条件",
                    "语言连贯并符合 40-60 词要求",
                ],
                "word_limit": 60,
                "explanation": "摘要应同时覆盖环境效益、实施挑战和长期维护，不能只复述单个细节。",
                "evidence_sentence_ids": ["s1", "s2", "s3", "s4", "s5"],
                "evidence_quote": "A successful program therefore combines environmental goals with long-term maintenance.",
                "skill": "article summary writing",
                "estimated_level": "B1",
            }
        ]
    }
)

GRADE = GradeCandidate.model_validate(
    {
        "dimensions": [
            {"criterion": "criterion 1", "score": 5, "feedback": "内容准确且切题。"},
            {"criterion": "criterion 2", "score": 4, "feedback": "原文依据较充分。"},
            {"criterion": "criterion 3", "score": 4, "feedback": "结构清楚，可加强衔接。"},
            {"criterion": "criterion 4", "score": 3, "feedback": "语言可理解，但仍有少量错误。"},
        ],
        "strengths": ["覆盖了文章核心观点", "能够引用文章信息"],
        "improvements": ["补充更具体的论据", "检查句子之间的衔接"],
        "overall_feedback": "回答与题目相关，内容和结构较完整，语言仍有提升空间。",
        "revised_example": "A stronger response would state the main claim, support it with a specific detail, and end with a clear conclusion.",
    }
)


class DemoProvider:
    model_name = "demo-fixture"
    runtime_mode = "demo"

    def __init__(self, progressive_delay: float = 0) -> None:
        self.progressive_delay = progressive_delay

    def validate_request(self, request: QuizRequest) -> None:
        counts = {item.type.value: item.count for item in request.question_counts if item.count}
        valid = (
            request.source_text == DEMO_SOURCE
            and request.target_language.value == "en"
            and request.level.upper() == "B1"
            and counts in (DEMO_COUNTS, SUMMARY_COUNTS)
        )
        if not valid:
            raise ValueError(
                "当前运行的是无密钥演示服务，只支持内置英文 B1 示例的默认 9 题或单道全文摘要。"
                "使用自己的文章需要配置 QUIZ_LLM_API_KEY 和 QUIZ_LLM_MODEL，"
                "然后启动 polyglot_quiz.api:app。"
            )

    def generate(self, prompt: str, response_model: type[T]) -> T:
        if response_model is ArticleAnalysis:
            return ANALYSIS.model_copy(deep=True)  # type: ignore[return-value]
        if response_model is CandidateQuestions:
            if self.progressive_delay:
                sleep(self.progressive_delay)
            if "- article_summary: 1" in prompt:
                return SUMMARY_QUESTION.model_copy(deep=True)  # type: ignore[return-value]
            requested_types = [
                question.type
                for question in QUESTIONS.questions
                if f"- {question.type.value}: 1" in prompt
            ]
            if len(requested_types) == 1:
                requested_type = requested_types[0]
                question = next(
                    question
                    for question in QUESTIONS.questions
                    if question.type == requested_type
                )
                return CandidateQuestions(
                    questions=[question.model_copy(deep=True)]
                )  # type: ignore[return-value]
            return QUESTIONS.model_copy(deep=True)  # type: ignore[return-value]
        if response_model is GradeCandidate:
            return GRADE.model_copy(deep=True)  # type: ignore[return-value]
        raise TypeError(f"Unsupported response model: {response_model}")


app = create_app(DemoProvider(progressive_delay=0.25))
