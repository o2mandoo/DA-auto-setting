from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
if str(BUILDER_SRC) not in sys.path:
    sys.path.insert(0, str(BUILDER_SRC))

from semantic_builder.profiler import SafeProfilerConfig, profile_column, profile_rows  # noqa: E402


class SafeDBProfilerTests(unittest.TestCase):
    def test_safe_profiler_config_exposes_timeout_budget(self) -> None:
        config = SafeProfilerConfig(timeout_ms=1500, top_n=3, low_cardinality_limit=12)

        self.assertEqual(1500, config.timeout_ms)
        self.assertEqual(3, config.top_n)
        self.assertEqual(12, config.low_cardinality_limit)
        self.assertEqual(
            {"timeout_ms": 1500, "top_n": 3, "low_cardinality_limit": 12},
            config.to_dict(),
        )

    def test_timeout_budget_is_enforced_for_column_profiling(self) -> None:
        with self.assertRaises(TimeoutError):
            profile_column("country", ["KR", "US"], config=SafeProfilerConfig(timeout_ms=0))

    def test_safe_profiler_config_is_threaded_through_row_profiling(self) -> None:
        rows = [{"status": "open"}, {"status": "closed"}, {"status": "open"}]
        profile = profile_rows("orders", rows, config=SafeProfilerConfig(timeout_ms=1000, top_n=2))
        columns = {column["name"]: column for column in profile["columns"]}

        self.assertEqual("orders", profile["table_name"])
        self.assertEqual({"value": "open", "count": 2}, columns["status"]["top_values"][0])

    def test_email_columns_do_not_expose_raw_sample_values(self) -> None:
        profile = profile_column("email", ["alice@example.com", "bob@example.com"]).to_dict()

        self.assertTrue(profile["pii"]["is_pii"])
        self.assertEqual("raw_values_suppressed_for_pii", profile["pattern_summary"]["redaction"])
        self.assertEqual([], profile["top_values"])
        self.assertNotIn("alice@example.com", repr(profile))
        self.assertNotIn("bob@example.com", repr(profile))

    def test_high_cardinality_columns_do_not_collect_full_distinct_values(self) -> None:
        values = [f"order-{index}" for index in range(25)]
        profile = profile_column("order_number", values).to_dict()

        self.assertEqual([], profile["top_values"])
        self.assertEqual("raw_values_suppressed_for_high_cardinality", profile["pattern_summary"]["redaction"])
        self.assertNotIn("order-24", repr(profile["top_values"]))

    def test_low_cardinality_columns_still_allow_safe_top_n(self) -> None:
        profile = profile_column(
            "status",
            ["open", "closed", "open", "pending", "open"],
            config=SafeProfilerConfig(top_n=2, low_cardinality_limit=10),
        ).to_dict()

        self.assertFalse(profile["pii"]["is_pii"])
        self.assertEqual(
            [
                {"value": "open", "count": 3},
                {"value": "closed", "count": 1},
            ],
            profile["top_values"],
        )
        self.assertNotIn("redaction", profile["pattern_summary"])


if __name__ == "__main__":
    unittest.main()
