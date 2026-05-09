from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
if str(BUILDER_SRC) not in sys.path:
    sys.path.insert(0, str(BUILDER_SRC))

from semantic_builder.profiler import profile_column, profile_rows  # noqa: E402


class ColumnProfilerTests(unittest.TestCase):
    def test_low_cardinality_non_pii_includes_safe_top_values(self) -> None:
        profile = profile_column("country", ["KR", "US", "KR", None, "JP"]).to_dict()

        self.assertEqual("string", profile["type_guess"])
        self.assertEqual(5, profile["row_count"])
        self.assertEqual(1, profile["null_count"])
        self.assertEqual(0.2, profile["null_ratio"])
        self.assertFalse(profile["pii"]["is_pii"])
        self.assertEqual({"value": "KR", "count": 2}, profile["top_values"][0])

    def test_email_column_is_pii_and_does_not_emit_raw_values(self) -> None:
        profile = profile_column(
            "email",
            ["alice@example.com", "bob@example.com", "carol@example.com"],
        ).to_dict()

        self.assertTrue(profile["pii"]["is_pii"])
        self.assertIn("email", profile["pii"]["categories"])
        self.assertEqual([], profile["top_values"])
        self.assertEqual("raw_values_suppressed_for_pii", profile["pattern_summary"]["redaction"])
        serialized = repr(profile)
        self.assertNotIn("alice@example.com", serialized)
        self.assertNotIn("bob@example.com", serialized)

    def test_name_and_phone_columns_are_pii_without_raw_value_leakage(self) -> None:
        name_profile = profile_column("customer_name", ["Alice Kim", "Bob Lee"]).to_dict()
        phone_profile = profile_column("mobile", ["+82-10-1234-5678", "010-2222-3333"]).to_dict()
        manager_profile = profile_column("Regional Manager", ["Sadie Pawthorne", "Chuck Magee"]).to_dict()

        self.assertIn("person_name", name_profile["pii"]["categories"])
        self.assertIn("phone", phone_profile["pii"]["categories"])
        self.assertIn("person_name", manager_profile["pii"]["categories"])
        self.assertEqual([], name_profile["top_values"])
        self.assertEqual([], phone_profile["top_values"])
        self.assertEqual([], manager_profile["top_values"])
        self.assertNotIn("Alice Kim", repr(name_profile))
        self.assertNotIn("010-2222-3333", repr(phone_profile))
        self.assertNotIn("Sadie Pawthorne", repr(manager_profile))

    def test_numeric_date_and_join_key_summary(self) -> None:
        rows = [
            {"user_id": "u1", "amount": "10.50", "signup_date": "2026-01-01"},
            {"user_id": "u2", "amount": "20", "signup_date": "2026-01-02"},
        ]

        profiles = {column["name"]: column for column in profile_rows("users", rows)["columns"]}

        self.assertTrue(profiles["user_id"]["join_key_candidate"])
        self.assertEqual("number", profiles["amount"]["type_guess"])
        self.assertEqual(10.5, profiles["amount"]["numeric_min"])
        self.assertEqual(20.0, profiles["amount"]["numeric_max"])
        self.assertEqual("date", profiles["signup_date"]["type_guess"])
        self.assertEqual("2026-01-01", profiles["signup_date"]["date_min"])
        self.assertEqual("2026-01-02", profiles["signup_date"]["date_max"])

    def test_pii_columns_suppress_numeric_and_date_extrema(self) -> None:
        postal_code = profile_column("postal_code", ["10001", "90210"]).to_dict()
        national_id_date = profile_column("national_id", ["2026-01-01", "2026-02-02"]).to_dict()

        self.assertTrue(postal_code["pii"]["is_pii"])
        self.assertEqual("number", postal_code["type_guess"])
        self.assertNotIn("numeric_min", postal_code)
        self.assertNotIn("numeric_max", postal_code)
        self.assertTrue(national_id_date["pii"]["is_pii"])
        self.assertEqual("date", national_id_date["type_guess"])
        self.assertNotIn("date_min", national_id_date)
        self.assertNotIn("date_max", national_id_date)

    def test_non_pii_columns_preserve_numeric_and_date_extrema(self) -> None:
        amount = profile_column("amount", ["10.50", "20"]).to_dict()
        signup_date = profile_column("signup_date", ["2026-01-01", "2026-01-02"]).to_dict()

        self.assertFalse(amount["pii"]["is_pii"])
        self.assertEqual(10.5, amount["numeric_min"])
        self.assertEqual(20.0, amount["numeric_max"])
        self.assertFalse(signup_date["pii"]["is_pii"])
        self.assertEqual("2026-01-01", signup_date["date_min"])
        self.assertEqual("2026-01-02", signup_date["date_max"])


    def test_iso_dates_are_not_misclassified_as_phone_pii(self) -> None:
        profile = profile_column("signup_date", ["2026-01-03", "2026-02-14"]).to_dict()

        self.assertEqual("date", profile["type_guess"])
        self.assertFalse(profile["pii"]["is_pii"])
        self.assertEqual("2026-01-03", profile["date_min"])
        self.assertEqual("2026-02-14", profile["date_max"])

    def test_business_ids_and_product_names_are_not_person_pii(self) -> None:
        order_id = profile_column("Order ID", ["US-2022-103800", "CA-2024-152156"]).to_dict()
        product_name = profile_column("Product Name", ["Message Book", "Office Chair"]).to_dict()

        self.assertFalse(order_id["pii"]["is_pii"])
        self.assertFalse(product_name["pii"]["is_pii"])

    def test_high_cardinality_values_are_summarized_not_dictionary_values(self) -> None:
        values = [f"order-{index}" for index in range(25)]
        profile = profile_column("order_number", values).to_dict()

        self.assertEqual([], profile["top_values"])
        self.assertEqual("raw_values_suppressed_for_high_cardinality", profile["pattern_summary"]["redaction"])
        self.assertNotIn("order-24", repr(profile["top_values"]))


if __name__ == "__main__":
    unittest.main()
