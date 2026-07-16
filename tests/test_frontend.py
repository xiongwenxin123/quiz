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
        self.assertIn('id="model-compatibility-mode"', html)
        self.assertIn('providerSettings', script)
        self.assertIn('/v1/provider-settings', script)


if __name__ == "__main__":
    unittest.main()
