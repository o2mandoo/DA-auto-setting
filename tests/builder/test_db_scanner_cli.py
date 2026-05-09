from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILDER_SRC = REPO_ROOT / "packages" / "semantic_builder" / "src"
if str(BUILDER_SRC) not in sys.path:
    sys.path.insert(0, str(BUILDER_SRC))

from semantic_builder.cli import main  # noqa: E402


class _FakePostgresConnector:
    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn
        self.closed = False

    def close(self) -> None:
        self.closed = True


class DBScannerCLITests(unittest.TestCase):
    def test_db_scan_writes_report_without_real_credentials(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_path = tmp / "scan_config.yaml"
            report_path = tmp / "scan_report.json"
            config_path.write_text(
                "\n".join(
                    [
                        "connector:",
                        "  dsn: postgresql://demo/warehouse",
                        "scan:",
                        "  schemas: [public]",
                        "  tables: [public.users]",
                        "  max_tables: 5",
                        "  max_columns: 3",
                        "  max_sample_rows: 2",
                        "  timeout_ms: 1500",
                        "  low_cardinality_threshold: 10",
                        "  pii_policy: block_raw_values",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            fake_report = {
                "connector": "postgres",
                "config": {
                    "schemas": ["public"],
                    "tables": ["public.users"],
                    "schemas_allowlist": ["public"],
                    "tables_allowlist": ["public.users"],
                    "max_tables": 5,
                    "max_columns": 3,
                    "max_sample_rows": 2,
                    "timeout_ms": 1500,
                    "low_cardinality_threshold": 10,
                    "pii_policy": "block_raw_values",
                },
                "tables": [
                    {
                        "schema_name": "public",
                        "table_name": "users",
                        "qualified_name": "public.users",
                        "table_type": "TABLE",
                        "is_view": False,
                        "is_materialized_view": False,
                        "columns": [
                            {
                                "schema_name": "public",
                                "table_name": "users",
                                "qualified_name": "public.users",
                                "column_name": "id",
                                "column_type": "integer",
                                "is_nullable": False,
                                "ordinal_position": 1,
                                "row_count": 3,
                            }
                        ],
                    }
                ],
            }

            seen: dict[str, object] = {}

            def fake_scan(connector: _FakePostgresConnector, *, config):
                seen["connector"] = connector
                seen["config"] = config
                return fake_report

            with patch("semantic_builder.cli.PostgresConnector", _FakePostgresConnector), patch(
                "semantic_builder.cli.scan_postgres_database", side_effect=fake_scan
            ) as scan_mock:
                exit_code = main(["db", "scan", "--connector", "postgres", "--config", str(config_path), "--out", str(report_path)])

            self.assertEqual(0, exit_code)
            self.assertTrue(report_path.exists())
            self.assertEqual(fake_report, json.loads(report_path.read_text(encoding="utf-8")))
            self.assertEqual("postgresql://demo/warehouse", getattr(seen["connector"], "dsn"))
            self.assertTrue(getattr(seen["connector"], "closed"))
            self.assertEqual(["public"], list(getattr(seen["config"], "schemas")))
            scan_mock.assert_called_once()

    def test_db_scan_missing_connection_string_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_path = tmp / "scan_config.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "connector:",
                        "  host: localhost",
                        "scan:",
                        "  schemas: [public]",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "requires a connection_string or dsn"):
                main(["db", "scan", "--connector", "postgres", "--config", str(config_path), "--out", str(tmp / "scan_report.json")])

    def test_db_profile_flattens_scan_report_to_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            scan_path = tmp / "scan_report.json"
            out_path = tmp / "column_profiles.jsonl"
            scan_payload = {
                "connector": "postgres",
                "tables": [
                    {
                        "schema_name": "public",
                        "table_name": "users",
                        "qualified_name": "public.users",
                        "columns": [
                            {
                                "schema_name": "public",
                                "table_name": "users",
                                "qualified_name": "public.users",
                                "column_name": "id",
                                "column_type": "integer",
                                "is_nullable": False,
                                "ordinal_position": 1,
                            },
                            {
                                "schema_name": "public",
                                "table_name": "users",
                                "qualified_name": "public.users",
                                "column_name": "status",
                                "column_type": "text",
                                "is_nullable": True,
                                "ordinal_position": 2,
                            },
                        ],
                    }
                ],
            }
            scan_path.write_text(json.dumps(scan_payload, indent=2) + "\n", encoding="utf-8")

            exit_code = main(["db", "profile", "--scan", str(scan_path), "--out", str(out_path)])

            self.assertEqual(0, exit_code)
            lines = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(2, len(lines))
            self.assertEqual("id", lines[0]["column_name"])
            self.assertEqual("status", lines[1]["column_name"])
            self.assertEqual("public.users", lines[0]["qualified_name"])


if __name__ == "__main__":
    unittest.main()
