import unittest
from pathlib import Path


WEB_DIR = Path(__file__).parents[1] / "src" / "polyglot_quiz" / "web"


class FrontendAssetTests(unittest.TestCase):
    def test_frontend_assets_exist_and_are_linked(self) -> None:
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('/assets/styles.css', html)
        self.assertIn('/assets/app.js', html)
        self.assertIn('id="quiz-form"', html)

    def test_frontend_calls_quiz_api(self) -> None:
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        script = (WEB_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn('fetch("/v1/quizzes"', script)
        self.assertIn('fetch("/health"', script)
        self.assertIn('X-Quiz-LLM-API-Key', script)
        self.assertIn('X-Quiz-Allow-Insecure-HTTP', script)
        self.assertIn('X-Quiz-LLM-Compatibility', script)
        self.assertIn('X-Quiz-Request-ID', script)
        self.assertIn('/v1/progress/', script)
        self.assertIn('id="model-compatibility-mode"', html)
        self.assertIn('providerSettings', script)
        self.assertIn('/v1/provider-settings', script)
        self.assertIn('paragraph_teaching', script)
        self.assertIn('中文翻译', script)
        self.assertIn('原文语境', script)
        self.assertIn('补充例句', script)
        self.assertIn('styles.css?v=', html)
        self.assertIn('app.js?v=', html)
        self.assertTrue(all(f'id: "{question_type}"' in script for question_type in (
            "main_idea", "detail", "inference", "author_purpose", "vocabulary_context",
            "cloze", "grammar", "true_false", "short_answer",
        )))


if __name__ == "__main__":
    unittest.main()
