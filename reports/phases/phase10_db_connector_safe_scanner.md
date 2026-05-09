# Phase 10 — DB Connector Safe Scanner

## Worker lane progress
- `worker-5` completed the explicit-error adapter slice for MySQL/Oracle.
- DB adapters now fail fast on missing connection strings and missing optional drivers.
- PostgreSQL connector contract shape was repaired so the existing read-only protocol test passes.
- `worker-5` added the Phase 10 CLI follow-up for `semantic-builder db scan/profile`.
- The CLI now supports a safe PostgreSQL scan command backed by YAML config plus a profile command that flattens scan results to JSONL.

## Changed files
- `packages/semantic_builder/src/semantic_builder/connectors/sql.py`
- `packages/semantic_builder/src/semantic_builder/connectors/mysql_connector.py`
- `packages/semantic_builder/src/semantic_builder/connectors/oracle_connector.py`
- `packages/semantic_builder/src/semantic_builder/connectors/postgres_connector.py`
- `packages/semantic_builder/src/semantic_builder/connectors/__init__.py`
- `packages/semantic_builder/src/semantic_builder/cli.py`
- `tests/builder/test_optional_db_adapters.py`
- `tests/builder/test_db_scanner_cli.py`

## Verification evidence
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/semantic-data-context-deps:packages/semantic_builder/src python3 -m unittest discover -s tests/builder -p 'test_optional_db_adapters.py' -v`
  - result: `OK` (`3 tests`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/semantic-data-context-deps:packages/semantic_builder/src python3 -m unittest discover -s tests/builder -p 'test_db_connector_contract.py' -v`
  - result: `OK` (`4 tests`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/semantic-data-context-deps:packages/semantic_builder/src python3 -m unittest tests.contracts.test_phase0_scope_contract -v`
  - result: `OK` (`2 tests`)
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/semantic-data-context-deps:packages/semantic_builder/src python3 -m unittest tests.builder.test_db_scanner_cli tests.builder.test_db_connector_contract -v`
  - result: `OK` (`8 tests`)

## Notes
- Validation used the shared `/tmp/semantic-data-context-deps` bundle because the plain repo `PYTHONPATH` did not provide `yaml` for `semantic_builder.__init__`.
- The DB adapters intentionally remain non-operational; they validate configuration/dependency presence and then refuse to fake live scanning.
- The CLI scan test used a stubbed PostgreSQL connector/scanner seam so no real database credentials were needed.
