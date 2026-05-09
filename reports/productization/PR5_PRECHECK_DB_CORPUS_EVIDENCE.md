# PR-5 Precheck — Live DB corpus fixture evidence

Date: 2026-05-09 KST

## Verdict

PASS. Before PR-5 retrieval work, the local experimental PostgreSQL and MySQL fixture services were verified with the 20 Sinagong workbook datasets loaded with explicit test-only metadata.

This is product-external fixture infrastructure. The generated DB comments are marked `TEST_ONLY_SYNTHETIC_METADATA` and must not be promoted to approved Semantic Pack truth.

## Live services

- PostgreSQL: `semantic-data-context-pr4-postgres`, `localhost:55432`, healthy.
- MySQL: `semantic-data-context-pr4-mysql`, `localhost:33306`, healthy.

## Command evidence

```bash
export SEMANTIC_CONTEXT_FIXTURE_DB=1
PYTHONPATH=. .venv/bin/python -m experiments.db_fixtures.scripts.sinagong_corpus_live_evidence \
  --postgres-dsn postgresql://sdc_fixture:<FIXTURE_PASSWORD>@localhost:55432/semantic_fixture_postgres_scope_c \
  --mysql-dsn mysql://sdc_fixture:<FIXTURE_PASSWORD>@localhost:33306/semantic_fixture_mysql_scope_c \
  --output reports/reality/sinagong_20_live_db_fixture_evidence.json
```

Result: exit code `0`; evidence written to `reports/reality/sinagong_20_live_db_fixture_evidence.json`.

## Loaded corpus summary

| Item | Count |
| --- | ---: |
| Source workbook datasets | 20 |
| Sheet-backed fixture tables | 89 |
| Loaded source rows | 103,980 |
| Fixture columns with metadata comments | 1,519 |

## Backend verification

| Backend | Status | Dataset count | Tables | Rows | Manifest rows | Table comments | Column comments | Metadata verified | Fallback |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| PostgreSQL | loaded | 20 | 89 | 103,980 | 89 | 89 | 1,519 | true | false |
| MySQL | loaded | 20 | 89 | 103,980 | 89 | 89 | 1,519 | true | false |

## No silent fallback log

1. First live run exposed a PostgreSQL `COMMENT ON ... IS $1` parameterization syntax error. It was not hidden behind another backend; the command exited non-zero with an explicit Postgres failure.
2. The script was fixed to use escaped SQL literals for PostgreSQL comments and rerun.
3. Second live run exposed a MySQL verification issue caused by counting all tables in the shared fixture database, including an older PR-4 table. It was not treated as success; the command exited non-zero with explicit MySQL verification failure.
4. Verification was fixed to count only the 89 Sinagong target tables and rerun.
5. Final run passed for both backends with `fallback_used=false`.

## Regression tests

```bash
.venv/bin/python -m pytest -q tests/fixtures/test_sinagong_corpus_live_evidence.py
# 2 passed

.venv/bin/python -m pytest -q \
  tests/fixtures/test_db_fixture_comment_modes.py \
  tests/fixtures/test_mysql_fixture_loader.py \
  tests/fixtures/test_postgres_live_evidence.py \
  tests/fixtures/test_mysql_live_evidence.py
# 21 passed
```

## PR-5 implication

PR-5 retrieval evaluation can now include DB-backed experimental context as a verified precondition: both local DB engines contain the same 20-workbook corpus with table/column metadata comments, while product retrieval must still treat these generated comments as test-only fixture metadata unless explicitly promoted through Semantic Pack review.
