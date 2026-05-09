from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from semantic_registry import FeedbackStore


class FeedbackStoreTests(unittest.TestCase):
    def test_save_feedback_appends_jsonl_receipt_and_readback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FeedbackStore(Path(tmp) / "feedback")
            receipt = store.save_feedback({
                "space_id": "revenue",
                "feedback": "net revenue definition is useful",
                "rating": 1,
            })

            self.assertTrue(receipt.stored)
            self.assertEqual(receipt.path, str(Path(tmp) / "feedback" / "revenue.jsonl"))
            rows = store.read_feedback("revenue")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["rating"], 1)
            self.assertEqual(rows[0]["space_id"], "revenue")
            self.assertEqual(rows[0]["feedback_id"], receipt.feedback_id)

    def test_save_feedback_rejects_obvious_raw_pii_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FeedbackStore(Path(tmp) / "feedback")
            with self.assertRaises(ValueError):
                store.save_feedback({"space_id": "revenue", "feedback": "contact user@example.com"})
            with self.assertRaises(ValueError):
                store.save_feedback({"space_id": "revenue", "message": "call 010-1234-5678"})
            self.assertEqual(store.read_feedback("revenue"), [])

    def test_save_feedback_rejects_unsafe_space_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = FeedbackStore(Path(tmp) / "feedback")
            with self.assertRaises(ValueError):
                store.save_feedback({"space_id": "../revenue", "feedback": "ok"})


if __name__ == "__main__":
    unittest.main()
