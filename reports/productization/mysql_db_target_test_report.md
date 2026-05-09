# MySQL DB Target Test Report

## Verdict

**PASS for code-verified MySQL Scope C scanner behavior; PARTIAL for live DB evidence.**

Worker 2 implemented and verified the read-only MySQL catalog connector and scanner provenance path with fake/injected connection tests. No production DB was contacted, no general SQL execution surface was added, and no MySQL-to-PostgreSQL/DuckDB/SQLite fallback was used. Live MySQL fixture execution remains **not run** and must be reported as `live_mysql_not_run` until an explicitly gated local fixture is available.

## Covered requirements

| Requirement | Status | Evidence |
|---|---|---|
| Read-only MySQL connector exists. | PASS | `packages/semantic_builder/src/semantic_builder/connectors/mysql_connector.py` exposes `read_only=True`, explicit `pymysql` dependency errors, injected connection support, bounded metadata/sample/profile methods. |
| Table comments come from `information_schema.tables.TABLE_COMMENT`. | PASS | `MySQLConnector.list_tables()` selects `table_comment`; `tests/builder/test_optional_db_adapters.py::test_mysql_connector_lists_tables_through_read_only_information_schema` verifies comment mapping. |
| Column comments come from `information_schema.columns.COLUMN_COMMENT`. | PASS | `MySQLConnector.list_columns()` selects `column_comment`; `tests/builder/test_optional_db_adapters.py::test_mysql_connector_lists_columns_through_read_only_information_schema` verifies comment mapping. |
| Real MySQL comments become draft product metadata. | PASS | `tests/builder/test_db_comment_metadata_gaps.py` verifies `metadata_source=real_db_comment`, `mysql.table_comment` / `mysql.column_comment` source detail, and `can_use_for_text2sql=true`. |
| Missing MySQL comments become gaps/questions. | PASS | `tests/builder/test_db_comment_metadata_gaps.py` and `tests/builder/test_comment_aware_reverse_questions.py` verify `no_comment`, structured metadata gaps, and reverse-question evidence. |
| Synthetic comments remain fixture-only. | PASS | `tests/fixtures/test_db_fixture_comment_modes.py` verifies `TEST_ONLY_SYNTHETIC_METADATA` on synthetic table and column fixture comments; provenance tests verify `test_only_synthetic_comment` is test-only and not Text-to-SQL context. |
| No silent fallback. | PASS (code/docs) | MySQL connector raises explicit dependency/configuration errors; docs require `live_mysql_not_run` rather than fallback. |
| Live MySQL execution. | NOT RUN | No local MySQL fixture/server was exercised in this worker. |

## Verification commands

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_builder/src:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 -m pytest \
  tests/builder/test_optional_db_adapters.py \
  tests/builder/test_db_comment_metadata_gaps.py \
  tests/builder/test_comment_aware_reverse_questions.py \
  tests/contracts/test_metadata_provenance.py \
  tests/registry/test_text2sql_provenance_context.py -q
# 21 passed in 0.13s
```

Additional focused checks completed during task execution:

- Table-comment path: `test_mysql_connector_lists_tables_through_read_only_information_schema` -> `1 passed`.
- Column-comment path: `test_mysql_connector_lists_columns_through_read_only_information_schema` -> `1 passed`.
- Connector/provenance subset: `tests/builder/test_optional_db_adapters.py tests/builder/test_db_comment_metadata_gaps.py` -> `9 passed`.
- Scanner provenance subset: `tests/builder/test_db_comment_metadata_gaps.py tests/contracts/test_metadata_provenance.py tests/registry/test_text2sql_provenance_context.py` -> `14 passed`.
- Gap/reverse-question subset: `tests/builder/test_db_comment_metadata_gaps.py tests/builder/test_comment_aware_reverse_questions.py` -> `8 passed`.

`ruff` was not installed in this worker environment; Python syntax checks were run with `py_compile` for edited/related files during connector task verification.

## Changed implementation/docs slice

- `packages/semantic_builder/src/semantic_builder/connectors/mysql_connector.py` — read-only MySQL connector implementation and information_schema metadata reads.
- `packages/semantic_builder/src/semantic_builder/scanner/postgres.py` — backend label invariants so `MySQLScanner` emits `mysql.*` source details.
- `tests/builder/test_optional_db_adapters.py` — fake-connection tests for MySQL table/column comments and explicit missing dependency behavior.
- `tests/builder/test_db_comment_metadata_gaps.py` — MySQL scanner provenance and no-comment gap regressions.
- `tests/fixtures/test_db_fixture_comment_modes.py` — synthetic fixture marker regression for table and column comments.
- `reports/productization/mysql_scope_c_team_execution_plan.md` — Worker 2 lane contract and Scope C safety constraints.
- `reports/productization/n8n_readiness_after_comment_rule_correction.md` — MySQL Scope C readiness and live evidence gate.
- `docs/demo/N8N_DB_BACKED_DEMO_REQUIREMENTS.md` — MySQL no-fallback and fixture-only synthetic comment rules.

## Remaining risks

1. **Live MySQL not run:** real server/driver behavior remains unproven until a local fixture is explicitly gated and executed.
2. **No MySQL DDL fixture loader evidence in this lane:** Worker 2 verified scanner/catalog behavior, not MySQL fixture DDL creation.
3. **No n8n dry-run:** report/docs are ready for n8n planning, but workflow import/runtime is outside this lane.
4. **Lint gap:** `ruff` was unavailable; rely on `py_compile` plus pytest evidence in this worker.

## Stop condition

The code-verified MySQL scanner target is ready for integration review. Do not claim production/live MySQL readiness until a gated local MySQL fixture run is added and reported separately.
