import unittest
from unittest.mock import patch

import httpx

from polyglot_quiz.extraction import (
    UnsafeUrlError,
    _validate_public_url,
    document_from_text,
    extract_url,
)
from polyglot_quiz.models import TargetLanguage


class ExtractionTests(unittest.TestCase):
    def test_japanese_sentence_ids_are_stable(self) -> None:
        text = "これは十分な長さを持つ日本語の記事です。文を正しく分割できることを確認します！さらに、最後の文も追加して、入力全体が必要な最小文字数を確実に超えるようにします。"
        document = document_from_text(text, TargetLanguage.JAPANESE)
        self.assertEqual([sentence.id for sentence in document.sentences], ["s1", "s2", "s3"])

    def test_private_ip_is_rejected(self) -> None:
        with self.assertRaises(UnsafeUrlError):
            _validate_public_url("http://127.0.0.1/article")

    @patch("polyglot_quiz.extraction.time.sleep")
    @patch("polyglot_quiz.extraction._download_html")
    def test_url_download_retries_transient_transport_errors(self, download: object, sleep: object) -> None:
        html = "<html><body><article><p>" + ("A useful article sentence. " * 8) + "</p></article></body></html>"
        download.side_effect = [
            httpx.RemoteProtocolError("partial body"),
            (html, "https://example.com/article"),
        ]
        document = extract_url("https://example.com/article", TargetLanguage.ENGLISH)
        self.assertEqual(download.call_count, 2)
        self.assertGreater(len(document.text), 80)


if __name__ == "__main__":
    unittest.main()
