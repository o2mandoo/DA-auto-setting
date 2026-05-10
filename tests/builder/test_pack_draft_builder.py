from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_SUPERSTORE_XLS = REPO_ROOT / "docs" / "reference" / "test_datasets" / "tableau_superstore" / "Sample - Superstore.xls"
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
CONTRACTS_SRC = REPO_ROOT / "packages" / "semantic_contracts"
for path in (BUILDER_SRC, CONTRACTS_SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from semantic_builder.builder import build_semantic_pack_draft  # noqa: E402
from semantic_builder.cli import main as builder_main  # noqa: E402
from semantic_builder.connectors import scan_source  # noqa: E402
from semantic_builder.profiler import profile_dataset  # noqa: E402
from semantic_contracts import validate_semantic_pack  # noqa: E402


class PackDraftBuilderTests(unittest.TestCase):
    def test_build_draft_pack_validates_and_blocks_pii_value_dictionaries(self) -> None:
        datasets = scan_source(REPO_ROOT / "examples" / "demo_data")
        profiles = [profile_dataset(dataset) for dataset in datasets]

        document = build_semantic_pack_draft(profiles)
        result = validate_semantic_pack(document)

        self.assertTrue(result.valid, result.errors)
        pack = document["semantic_pack"]
        blocked_columns = {column for policy in pack["policies"] for column in policy["blocked_columns"]}
        self.assertIn("users.email", blocked_columns)
        value_dictionary_refs = {f"{item['table']}.{item['column']}" for item in pack["value_dictionaries"]}
        self.assertNotIn("users.email", value_dictionary_refs)
        self.assertIn("payments.status", value_dictionary_refs)
        serialized = json.dumps(document, ensure_ascii=False)
        self.assertNotIn("ada@example.com", serialized)
        self.assertNotIn("grace@example.com", serialized)

    def test_draft_pack_suppresses_stale_pii_extrema_but_preserves_safe_extrema(self) -> None:
        document = build_semantic_pack_draft(
            [
                {
                    "table_name": "customers",
                    "row_count": 2,
                    "columns": [
                        {
                            "name": "postal_code",
                            "type_guess": "number",
                            "null_count": 0,
                            "null_ratio": 0.0,
                            "cardinality_estimate": 2,
                            "top_values": [],
                            "numeric_min": 10001,
                            "numeric_max": 90210,
                            "pii": {"is_pii": True, "categories": ["address"]},
                        },
                        {
                            "name": "amount",
                            "type_guess": "number",
                            "null_count": 0,
                            "null_ratio": 0.0,
                            "cardinality_estimate": 2,
                            "top_values": [],
                            "numeric_min": 10.5,
                            "numeric_max": 20.0,
                            "pii": {"is_pii": False, "categories": []},
                        },
                    ],
                }
            ]
        )

        columns = {column["name"]: column for column in document["semantic_pack"]["columns"]}
        self.assertNotIn("min_value", columns["postal_code"]["profile"])
        self.assertNotIn("max_value", columns["postal_code"]["profile"])
        self.assertEqual(10.5, columns["amount"]["profile"]["min_value"])
        self.assertEqual(20.0, columns["amount"]["profile"]["max_value"])

    def test_cli_scan_profile_build_pack_pipeline_writes_valid_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            scan_path = tmp / "scan_report.json"
            profiles_path = tmp / "column_profiles.jsonl"
            draft_path = tmp / "semantic_pack.draft.yaml"

            self.assertEqual(0, builder_main(["scan", "--source", str(REPO_ROOT / "examples" / "demo_data"), "--out", str(scan_path)]))
            self.assertEqual(0, builder_main(["profile", "--scan", str(scan_path), "--out", str(profiles_path)]))
            self.assertEqual(0, builder_main(["build-pack", "--profiles", str(profiles_path), "--out", str(draft_path)]))

            self.assertTrue(scan_path.exists())
            self.assertTrue(profiles_path.exists())
            self.assertTrue(draft_path.exists())
            text = draft_path.read_text(encoding="utf-8")
            self.assertIn("semantic_pack:", text)
            self.assertNotIn("ada@example.com", text)

    def test_cli_pipeline_builds_per_sheet_tables_for_superstore_xls_without_pii_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            source = LOCAL_SUPERSTORE_XLS
            if not source.exists():
                self.skipTest(f"local-only Superstore XLS is not tracked in git: {source}")
            scan_path = tmp / "scan_report.json"
            profiles_path = tmp / "column_profiles.jsonl"
            draft_path = tmp / "semantic_pack.draft.yaml"

            self.assertEqual(0, builder_main(["scan", "--source", str(source), "--out", str(scan_path)]))
            self.assertEqual(0, builder_main(["profile", "--scan", str(scan_path), "--out", str(profiles_path)]))
            self.assertEqual(0, builder_main(["build-pack", "--profiles", str(profiles_path), "--out", str(draft_path)]))

            scan_payload = json.loads(scan_path.read_text(encoding="utf-8"))
            scan_tables = {record["table_name"]: record.get("sheet_name") for record in scan_payload["datasets"]}
            self.assertEqual(
                {
                    "sample_superstore_orders": "Orders",
                    "sample_superstore_people": "People",
                    "sample_superstore_returns": "Returns",
                },
                scan_tables,
            )
            profiles = [json.loads(line) for line in profiles_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(["sample_superstore_orders", "sample_superstore_people", "sample_superstore_returns"], [item["table_name"] for item in profiles])
            self.assertEqual(["Orders", "People", "Returns"], [item.get("sheet_name") for item in profiles])

            document_text = draft_path.read_text(encoding="utf-8")
            self.assertIn("table.sample_superstore_orders", document_text)
            self.assertIn("table.sample_superstore_people", document_text)
            self.assertIn("table.sample_superstore_returns", document_text)
            self.assertNotIn("Claire Gute", document_text)
            self.assertNotIn("Sadie Pawthorne", document_text)


if __name__ == "__main__":
    unittest.main()
