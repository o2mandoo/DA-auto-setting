from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))

from semantic_contracts import SemanticPack, load_pack_yaml, validate_semantic_pack  # noqa: E402


class DemoPackLoadingValidationTest(unittest.TestCase):
    def test_demo_pack_loads_through_contract_loader_and_validates(self) -> None:
        pack = load_pack_yaml(ROOT / "semantic_packs" / "demo_company" / "revenue.v0_1.yaml")
        result = validate_semantic_pack(pack)

        self.assertIsInstance(pack, SemanticPack)
        self.assertEqual(pack.id, "demo_company.revenue")
        self.assertEqual(pack.version, "0.1.0")
        self.assertTrue(result.valid, [error.message for error in result.errors])

    def test_demo_pack_has_required_phase0_card_families(self) -> None:
        pack = load_pack_yaml(ROOT / "semantic_packs" / "demo_company" / "revenue.v0_1.yaml")

        self.assertGreaterEqual(len(pack.tables), 1)
        self.assertGreaterEqual(len(pack.columns), 1)
        self.assertGreaterEqual(len(pack.value_dictionaries), 1)
        self.assertGreaterEqual(len(pack.metrics), 1)
        self.assertGreaterEqual(len(pack.business_terms), 1)
        self.assertGreaterEqual(len(pack.join_recipes), 1)
        self.assertGreaterEqual(len(pack.policies), 1)
        self.assertGreaterEqual(len(pack.verified_queries), 1)
        self.assertGreaterEqual(len(pack.reverse_questions), 1)

    def test_demo_pack_keeps_pii_candidates_out_of_value_dictionaries(self) -> None:
        pack = load_pack_yaml(ROOT / "semantic_packs" / "demo_company" / "revenue.v0_1.yaml")
        pii_columns = {f"{column.table}.{column.name}" for column in pack.columns if column.pii.is_candidate}
        dictionary_columns = {f"{dictionary.table}.{dictionary.column}" for dictionary in pack.value_dictionaries}

        self.assertFalse(pii_columns & dictionary_columns)


if __name__ == "__main__":
    unittest.main()
