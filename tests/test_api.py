import json
import tempfile
import time
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ImportError:  # API dependencies are optional for core-only installs.
    TestClient = None  # type: ignore[assignment,misc]

from examples.demo_server import DemoProvider
from polyglot_quiz.api import create_app
from polyglot_quiz.extraction import ExtractionError
from polyglot_quiz.models import QuestionType
from polyglot_quiz.providers import ProviderError


class RateLimitedProvider:
    model_name = "limited-model"
    base_url = "http://llm.internal/v1"

    def generate(self, prompt: str, response_model: type[object]) -> object:
        raise ProviderError("Upstream HTTP 429; response=quota exhausted", status_code=429)


@unittest.skipIf(TestClient is None, "FastAPI optional dependencies are not installed")
class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(create_app(DemoProvider()))

    def test_frontend_and_assets_are_served(self) -> None:
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Polyglot Quiz", page.text)
        self.assertEqual(self.client.get("/assets/app.js").status_code, 200)
        self.assertEqual(self.client.get("/assets/styles.css").status_code, 200)

        miniapp = self.client.get("/miniapp")
        self.assertEqual(miniapp.status_code, 200)
        self.assertIn("精读小课", miniapp.text)
        miniapp_js = self.client.get("/miniapp-assets/app.js")
        miniapp_css = self.client.get("/miniapp-assets/styles.css")
        self.assertEqual(miniapp_js.status_code, 200)
        self.assertEqual(miniapp_css.status_code, 200)
        self.assertIn("/v1/progressive-quizzes", miniapp_js.text)
        self.assertIn("safe-area-inset-top", miniapp_css.text)

    def test_progressive_quiz_retains_article_and_builds_questions(self) -> None:
        client = TestClient(create_app(DemoProvider(progressive_delay=0.02)))
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        request.pop("question_counts")
        job_id = "progressivetest1234"
        created = client.post(
            "/v1/progressive-quizzes",
            json=request,
            headers={"X-Quiz-Request-ID": job_id},
        )
        self.assertEqual(created.status_code, 202, created.text)
        self.assertEqual(created.json()["id"], job_id)

        snapshots = []
        for _ in range(100):
            response = client.get(f"/v1/progressive-quizzes/{job_id}")
            self.assertEqual(response.status_code, 200, response.text)
            snapshot = response.json()
            snapshots.append(snapshot)
            if snapshot["done"]:
                break
            time.sleep(0.01)

        final = snapshots[-1]
        self.assertTrue(final["done"], final)
        self.assertFalse(final["failed"], final.get("error"))
        self.assertEqual(final["percent"], 100)
        self.assertEqual(len(final["article"]["paragraphs"]), 3)
        self.assertEqual(len(final["analysis"]["paragraph_teaching"]), 3)
        self.assertGreaterEqual(len(final["vocabulary"]), 1)
        self.assertEqual(len(final["questions"]), 9)
        self.assertEqual(final["question_errors"], [])
        self.assertTrue(
            any(
                item["article"] is not None
                and len(item["questions"]) < item["requested_total"]
                and not item["done"]
                for item in snapshots
            ),
            snapshots,
        )

    def test_progressive_model_failure_keeps_article_and_error_detail(self) -> None:
        client = TestClient(create_app(RateLimitedProvider()))
        request = json.loads(
            (Path(__file__).parents[1] / "examples" / "english-request.json").read_text()
        )
        job_id = "progressivefail1234"
        created = client.post(
            "/v1/progressive-quizzes",
            json=request,
            headers={"X-Quiz-Request-ID": job_id},
        )
        self.assertEqual(created.status_code, 202, created.text)

        for _ in range(100):
            final = client.get(f"/v1/progressive-quizzes/{job_id}").json()
            if final["done"]:
                break
            time.sleep(0.01)

        self.assertTrue(final["failed"], final)
        self.assertIsNotNone(final["article"])
        self.assertIn("quota exhausted", final["error"])

    def test_config_lists_all_languages(self) -> None:
        response = self.client.get("/v1/config")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["runtime_mode"], "demo")
        self.assertEqual({item["code"] for item in response.json()["languages"]}, {"en", "ja", "es"})
        self.assertEqual(response.json()["question_types"], [item.value for item in QuestionType])

    def test_self_review_answer_can_be_graded_with_deterministic_total(self) -> None:
        question = {
            "id": "q1",
            "type": "article_summary",
            "prompt": "Summarize the article in no more than 60 words.",
            "accepted_answers": ["Trees cool cities but require planning and maintenance."],
            "evaluation_mode": "self_review",
            "rubric": ["内容准确", "原文依据", "结构组织", "语言质量"],
            "word_limit": 60,
            "explanation": "Use the rubric to review the response.",
            "evidence_sentence_ids": ["s1"],
            "evidence_quote": "Many cities are planting trees to reduce summer heat.",
            "skill": "summary writing",
            "estimated_level": "B1",
        }
        response = self.client.post(
            "/v1/grade",
            json={
                "question": question,
                "learner_answer": "Trees can cool cities, although successful programs also need planning and long-term care.",
                "evidence_sentences": [
                    {"id": "s1", "text": "Many cities are planting trees to reduce summer heat."}
                ],
                "target_language": "en",
                "explanation_language": "zh-CN",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["total_score"], 80)
        self.assertEqual(body["max_score"], 100)
        self.assertEqual(
            [item["criterion"] for item in body["dimensions"]],
            question["rubric"],
        )

    def test_demo_generation_passes_pipeline(self) -> None:
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        request.pop("question_counts")
        response = self.client.post("/v1/quizzes", json=request)
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(len(body["questions"]), 9)
        self.assertEqual(
            {question["type"] for question in body["questions"]},
            {
                "main_idea", "detail", "inference", "author_purpose",
                "vocabulary_context", "cloze", "grammar", "true_false", "short_answer",
            },
        )
        self.assertEqual(len(body["article"]["paragraphs"]), 3)
        self.assertEqual(len(body["analysis"]["paragraph_teaching"]), 3)
        self.assertEqual(len(body["analysis"]["vocabulary_targets"][0]["examples"]), 2)
        self.assertEqual(body["metadata"]["model"], "demo-fixture")
        four_choice_positions = Counter(
            question["correct_option_id"]
            for question in body["questions"]
            if len(question["options"]) == 4
        )
        self.assertEqual(set(four_choice_positions), {"A", "B", "C", "D"})
        self.assertLessEqual(
            max(four_choice_positions.values()) - min(four_choice_positions.values()),
            1,
        )

    def test_demo_generates_open_summary_with_self_review_fields(self) -> None:
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        request["question_counts"] = [{"type": "article_summary", "count": 1}]
        response = self.client.post("/v1/quizzes", json=request)
        self.assertEqual(response.status_code, 200, response.text)
        question = response.json()["questions"][0]
        self.assertEqual(question["type"], "article_summary")
        self.assertEqual(question["evaluation_mode"], "self_review")
        self.assertEqual(len(question["rubric"]), 4)
        self.assertEqual(question["options"], [])

    def test_generation_progress_uses_client_request_id(self) -> None:
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        request.pop("question_counts")
        request_id = "frontendtest1234"
        response = self.client.post(
            "/v1/quizzes",
            json=request,
            headers={"X-Quiz-Request-ID": request_id},
        )
        self.assertEqual(response.status_code, 200, response.text)
        progress = self.client.get(f"/v1/progress/{request_id}")
        self.assertEqual(progress.status_code, 200, progress.text)
        self.assertEqual(progress.json()["stage"], "complete")
        self.assertEqual(progress.json()["percent"], 100)
        self.assertTrue(progress.json()["done"])
        self.assertFalse(progress.json()["failed"])

    def test_invalid_progress_request_id_is_rejected(self) -> None:
        self.assertEqual(self.client.get("/v1/progress/short").status_code, 404)

    def test_demo_rejects_custom_articles_with_clear_message(self) -> None:
        response = self.client.post(
            "/v1/quizzes",
            json={
                "source_text": "This custom article is deliberately different from the built-in demonstration article. "
                "It is long enough to pass request validation but must not receive fixed fixture questions.",
                "target_language": "en",
                "level": "B1",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("无密钥演示服务", response.json()["detail"])
        self.assertNotIn("invented_quote", response.text)

    def test_request_provider_headers_override_demo_provider(self) -> None:
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        request.pop("question_counts")
        with patch("polyglot_quiz.api.OpenAICompatibleProvider") as provider_class:
            provider_class.return_value = DemoProvider()
            response = self.client.post(
                "/v1/quizzes",
                json=request,
                headers={
                    "X-Quiz-LLM-API-Key": "browser-key",
                    "X-Quiz-LLM-Model": "browser-model",
                    "X-Quiz-LLM-Base-URL": "https://llm.example/v1",
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        provider_class.assert_called_once_with(
            api_key="browser-key",
            model="browser-model",
            base_url="https://llm.example/v1",
            compatibility_mode="auto",
        )

    def test_partial_request_provider_is_rejected(self) -> None:
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        response = self.client.post(
            "/v1/quizzes",
            json=request,
            headers={"X-Quiz-LLM-API-Key": "browser-key"},
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("必须同时包含", response.json()["detail"])

    def test_http_request_provider_requires_explicit_confirmation(self) -> None:
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        response = self.client.post(
            "/v1/quizzes",
            json=request,
            headers={
                "X-Quiz-LLM-API-Key": "browser-key",
                "X-Quiz-LLM-Model": "browser-model",
                "X-Quiz-LLM-Base-URL": "http://127.0.0.1:9000/v1",
            },
        )
        self.assertEqual(response.status_code, 422)
        self.assertIn("确认允许明文 HTTP", response.json()["detail"])

    def test_confirmed_http_request_provider_is_allowed_in_demo_mode(self) -> None:
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        request.pop("question_counts")
        with patch("polyglot_quiz.api.OpenAICompatibleProvider") as provider_class:
            provider_class.return_value = DemoProvider()
            response = self.client.post(
                "/v1/quizzes",
                json=request,
                headers={
                    "X-Quiz-LLM-API-Key": "browser-key",
                    "X-Quiz-LLM-Model": "local-model",
                    "X-Quiz-LLM-Base-URL": "http://127.0.0.1:9000/v1",
                    "X-Quiz-Allow-Insecure-HTTP": "true",
                    "X-Quiz-LLM-Compatibility": "qwen_stream",
                },
            )
        self.assertEqual(response.status_code, 200, response.text)
        provider_class.assert_called_once_with(
            api_key="browser-key",
            model="local-model",
            base_url="http://127.0.0.1:9000/v1",
            compatibility_mode="qwen_stream",
        )

    def test_rate_limit_detail_is_returned_to_frontend(self) -> None:
        client = TestClient(create_app(RateLimitedProvider()))
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        with self.assertLogs("uvicorn.error", level="ERROR") as logs:
            response = client.post("/v1/quizzes", json=request)
        self.assertEqual(response.status_code, 503)
        self.assertIn("限流或额度不足", response.json()["detail"])
        self.assertIn("quota exhausted", response.text)
        self.assertNotIn("llm.internal", response.text)
        self.assertTrue(response.headers["X-Request-ID"])
        self.assertIn("upstream_status=429", logs.output[0])
        self.assertIn("quota exhausted", logs.output[0])

    def test_extraction_error_detail_is_returned_to_frontend(self) -> None:
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        with patch(
            "polyglot_quiz.api.QuizPipeline.generate",
            side_effect=ExtractionError("URL resolves to a non-public address: 2001::1"),
        ):
            response = self.client.post("/v1/quizzes", json=request)
        self.assertEqual(response.status_code, 502)
        self.assertIn("URL resolves to a non-public address: 2001::1", response.text)
        self.assertTrue(response.headers["X-Request-ID"])

    def test_default_provider_can_be_saved_and_deleted_without_exposing_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings_path = Path(directory) / "provider.json"
            with patch("polyglot_quiz.providers.DEFAULT_PROVIDER_PATH", settings_path):
                saved = self.client.put(
                    "/v1/provider-settings",
                    json={
                        "api_key": "stored-secret",
                        "model": "stored-model",
                        "base_url": "http://127.0.0.1:9000/v1",
                        "allow_insecure_http": True,
                    },
                )
                self.assertEqual(saved.status_code, 200, saved.text)
                self.assertTrue(saved.json()["configured"])
                self.assertNotIn("stored-secret", saved.text)
                self.assertEqual(settings_path.stat().st_mode & 0o777, 0o600)

                loaded = self.client.get("/v1/provider-settings")
                self.assertEqual(loaded.json()["model"], "stored-model")
                self.assertNotIn("stored-secret", loaded.text)

                deleted = self.client.delete("/v1/provider-settings")
                self.assertFalse(deleted.json()["configured"])
                self.assertFalse(settings_path.exists())

    def test_successful_request_logs_pipeline_stages_without_article_text(self) -> None:
        request_path = Path(__file__).parents[1] / "examples" / "english-request.json"
        request = json.loads(request_path.read_text())
        request.pop("question_counts")
        with self.assertLogs("uvicorn.error", level="INFO") as logs:
            response = self.client.post("/v1/quizzes", json=request)
        self.assertEqual(response.status_code, 200)
        output = "\n".join(logs.output)
        for event in (
            "request_received",
            "pipeline_started",
            "extraction_completed",
            "learning_targets_selected",
            "analysis_started",
            "analysis_completed",
            "generation_started",
            "quality_checked",
            "answer_options_shuffled",
            "pipeline_completed",
            "request_completed",
        ):
            self.assertIn(f'"event": "{event}"', output)
        self.assertNotIn(request["source_text"], output)


if __name__ == "__main__":
    unittest.main()
