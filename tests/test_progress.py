import unittest
from unittest.mock import patch

from polyglot_quiz.progress import ProgressStore


class ProgressStoreTests(unittest.TestCase):
    def test_completed_snapshot_is_retained(self) -> None:
        store = ProgressStore()
        store.start("request-id-123")
        store.update(
            "request-id-123",
            stage="analyzing",
            message="Analyzing",
            percent=38,
        )
        completed = store.complete("request-id-123")
        self.assertTrue(completed.done)
        self.assertEqual(store.get("request-id-123"), completed)

    def test_expired_snapshots_are_removed(self) -> None:
        store = ProgressStore(ttl_seconds=5)
        with patch("polyglot_quiz.progress.time", return_value=10):
            store.start("request-id-123")
        with patch("polyglot_quiz.progress.time", return_value=16):
            self.assertIsNone(store.get("request-id-123"))


if __name__ == "__main__":
    unittest.main()
