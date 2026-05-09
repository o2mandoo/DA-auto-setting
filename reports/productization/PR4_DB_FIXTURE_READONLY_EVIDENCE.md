# PR-4 DB Fixture Readonly Evidence

## Classification

**LIVE FIXTURE DB EVIDENCE PACKET; FIXTURE/DEMO/READ-ONLY PRODUCT CLAIM ONLY**

This report captures the PR-4 live rerun requested after the initial no-DSN
pending evidence. It proves that local fixture PostgreSQL and MySQL services can
be started and loaded through the product-external DB fixture harness. It does
not claim production DB readiness and does not add production SQL execution.

## Environment prepared for live rerun

- Repo-local `.venv` was configured with normal development dependencies via
  `make setup`.
- Optional live DB dependencies were installed from `requirements-live-db.txt`:
  `psycopg[binary]` and `PyMySQL`.
- Local fixture-only services were started with
  `experiments/db_fixtures/docker-compose.live.yml`.
- Docker containers reached healthy state:
  - `semantic-data-context-pr4-postgres` on local port `55432`
  - `semantic-data-context-pr4-mysql` on local port `33306`

The Compose credentials are fixture-only local defaults and are not production
credentials.

## Evidence artifacts written

- `reports/reality/postgres_live_fixture_evidence.json`
- `reports/reality/mysql_live_fixture_evidence.json`

Both files were regenerated from the live local fixture services. They record:

| Backend | status | attempted | safe | fixture_only | dsn_configured | fallback_used | fallback_backend | executed statements | rows |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|
| PostgreSQL | `loaded` | `True` | `True` | `True` | `True` | `False` | `None` | `9` | `2` |
| MySQL | `loaded` | `True` | `True` | `True` | `True` | `False` | `None` | `5` | `2` |

## Live service commands

```bash
.venv/bin/python -m pip install -r requirements-live-db.txt
docker compose -f experiments/db_fixtures/docker-compose.live.yml up -d
export SEMANTIC_CONTEXT_FIXTURE_DB=1
export SEMANTIC_CONTEXT_POSTGRES_FIXTURE_DSN=postgresql://sdc_fixture:<FIXTURE_PASSWORD>@localhost:55432/semantic_fixture_postgres_scope_c
export SEMANTIC_CONTEXT_MYSQL_FIXTURE_DSN=mysql://sdc_fixture:<FIXTURE_PASSWORD>@localhost:33306/semantic_fixture_mysql_scope_c
.venv/bin/python -m experiments.db_fixtures.scripts.postgres_live_evidence --output reports/reality/postgres_live_fixture_evidence.json
.venv/bin/python -m experiments.db_fixtures.scripts.mysql_live_evidence --output reports/reality/mysql_live_fixture_evidence.json
```

## Live DB content verification

Additional direct verification confirmed the fixture tables were loaded:

```text
postgres row_count 2
postgres table_comment Fixture-only order table for PostgreSQL scope C validation
mysql row_count 2
mysql table_comment Fixture-only order table for MySQL scope C validation
```

## Environment check

Command:

```bash
make env-check
```

Expected output:

```text
environment ok: 3.14.4
```

## Acceptance command output

Command:

```bash
.venv/bin/python -m pytest -q tests/builder/test_postgres_scanner.py tests/builder/test_mysql_comment_scanner.py tests/fixtures tests/e2e/test_mysql_db_fixture_comparison.py
```

Output from the live-rerun environment:

```text
..................................                                       [100%]
34 passed in 0.10s
```

Focused live-evidence tests also passed:

```text
.venv/bin/python -m pytest -q tests/fixtures/test_postgres_live_evidence.py tests/fixtures/test_mysql_live_evidence.py tests/fixtures/test_mysql_fixture_loader.py
.........                                                                [100%]
9 passed in 0.02s
```

## PostgreSQL status

- Live local PostgreSQL fixture service was started and reached `healthy`.
- Fixture loading was gated by `SEMANTIC_CONTEXT_FIXTURE_DB=1`.
- DSN used local host and `semantic_fixture_*` database/schema naming.
- Evidence status is `loaded` with `9` executed fixture statements and `2` rows.
- No fallback backend was used.

## MySQL status

- Live local MySQL fixture service was started and reached `healthy`.
- Fixture loading was gated by `SEMANTIC_CONTEXT_FIXTURE_DB=1`.
- DSN used local host and `semantic_fixture_*` database/schema naming.
- Evidence status is `loaded` with `5` executed fixture statements and `2` rows.
- No fallback backend was used.

## No fallback proof

- Both evidence JSON files have `fallback_used: false`.
- Both evidence JSON files have `fallback_backend: null`.
- Backend labels remain exact: PostgreSQL evidence uses `backend: postgres`; MySQL evidence uses `backend: mysql`.
- No MySQL request was rerouted to PostgreSQL, DuckDB, SQLite, cached JSON, or synthetic comments.
- No PostgreSQL request was rerouted to MySQL, DuckDB, SQLite, cached JSON, or synthetic comments.

## Oracle unsupported proof

Oracle remains unsupported for PR-4. The DB fixture guide states that Oracle is
not implemented by this fixture harness, and this rerun did not add Oracle live
service, connector behavior, or fake evidence.

## No production credentials / no production SQL execution

- Only local fixture containers were used.
- DSNs point to `localhost` and `semantic_fixture_*` databases.
- No production-looking DSN was used.
- No product `execute_query` route/tool/function was added.
- Fixture DDL/INSERT execution is product-external validation tooling, not
  product runtime SQL execution.

## Remaining risk

- This is live local fixture evidence, not production DB evidence.
- Containers must be running for another live rerun; otherwise the evidence
  writers must return explicit pending/unavailable status instead of falling
  back.
