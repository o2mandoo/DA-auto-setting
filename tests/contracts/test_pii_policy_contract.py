from __future__ import annotations

import unittest

from contract_helpers import load_demo_semantic_pack


class PiiAndPolicyContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack = load_demo_semantic_pack()

    def test_name_like_columns_are_pii_candidates_and_raw_values_blocked(self) -> None:
        columns = {f"{col['table']}.{col['name']}": col for col in self.pack["columns"]}
        for column_ref in ("users.email", "users.phone", "users.name"):
            with self.subTest(column_ref=column_ref):
                pii = columns[column_ref]["pii"]
                self.assertTrue(pii["is_candidate"])
                self.assertEqual(pii["raw_value_storage"], "blocked")

    def test_pii_columns_do_not_have_value_dictionaries(self) -> None:
        value_dict_refs = {f"{vd['table']}.{vd['column']}" for vd in self.pack["value_dictionaries"]}
        self.assertNotIn("users.email", value_dict_refs)
        self.assertNotIn("users.phone", value_dict_refs)
        self.assertNotIn("users.name", value_dict_refs)

    def test_policy_represents_blocked_columns(self) -> None:
        blocked_columns = {
            column
            for policy in self.pack["policies"]
            for column in policy.get("blocked_columns", [])
        }
        self.assertGreaterEqual(
            blocked_columns,
            {"users.email", "users.phone", "users.name"},
        )
