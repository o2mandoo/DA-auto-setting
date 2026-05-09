# DB Fixture Guide

This guide describes product-external DB fixture tooling. It is not product runtime and does not create customer-facing metadata-generation capability.

## Supported fixture backends

- `postgres`: fixture DDL planner uses `CREATE SCHEMA`, `CREATE TABLE`, and PostgreSQL `COMMENT ON TABLE` / `COMMENT ON COLUMN` statements.
- `mysql`: fixture DDL planner uses MySQL-specific `CREATE DATABASE`, `CREATE TABLE`, table `COMMENT`, and column `COMMENT` clauses.

Backend selection is explicit. The harness must not fall back from a requested MySQL run to PostgreSQL, DuckDB, SQLite, Oracle, or any other backend.

## Modes

- `no_comments`: creates DB tables without table/column comments. Product scanners must emit `metadata_source=no_comment` and metadata gaps.
- `real_comments`: uses actual comments/descriptions supplied by a source manifest. These comments are product-usable draft semantic metadata.
- `synthetic_comments`: generates comments with `TEST_ONLY_SYNTHETIC_METADATA`. These are fixture-only upper-bound/debug annotations and never approved product truth.

## Safety gates

- `SEMANTIC_CONTEXT_FIXTURE_DB=1` is required for any live fixture DB load.
- PostgreSQL fixture schema names must start with `semantic_fixture_`.
- MySQL fixture database/schema names must start with `semantic_fixture_`.
- Live fixture DSNs must point at local hosts such as `localhost`, `127.0.0.1`, `::1`, or `host.docker.internal`.
- Production-looking DSNs are refused.
- Oracle is not implemented by this fixture harness.
- No silent fallback: DuckDB/SQLite smoke exports, if added, must be explicitly selected and cannot replace a requested Postgres or MySQL run.


## Optional local live fixture services

For PR-4/live evidence reruns, use the product-external Docker Compose file:

```bash
.venv/bin/python -m pip install -r requirements-live-db.txt
docker compose -f experiments/db_fixtures/docker-compose.live.yml up -d
export SEMANTIC_CONTEXT_FIXTURE_DB=1
export SEMANTIC_CONTEXT_POSTGRES_FIXTURE_DSN=postgresql://sdc_fixture:sdc_fixture_pw@localhost:55432/semantic_fixture_postgres_scope_c
export SEMANTIC_CONTEXT_MYSQL_FIXTURE_DSN=mysql://sdc_fixture:sdc_fixture_pw@localhost:33306/semantic_fixture_mysql_scope_c
.venv/bin/python -m experiments.db_fixtures.scripts.postgres_live_evidence --output reports/reality/postgres_live_fixture_evidence.json
.venv/bin/python -m experiments.db_fixtures.scripts.mysql_live_evidence --output reports/reality/mysql_live_fixture_evidence.json
```

The Compose credentials are fixture-only local defaults. They must not be reused
for production services. If any selected backend is unavailable, the evidence
writer must report the exact unavailable state; it must not reroute to another
DB or cached artifact.

## n8n handoff criterion

n8n live work may start only after DB-backed evidence proves:

1. seeded Postgres or MySQL fixture exists or environment failure is explicit,
2. scan/profile succeeds for the selected backend or fails explicitly without fallback,
3. build-pack succeeds,
4. no_comments create gaps/questions,
5. real_comments become context,
6. synthetic_comments remain test-only,
7. readiness report is generated.

This run must not create n8n workflow JSON. n8n may consume the evidence later, but workflow authoring/import remains outside this fixture planner task.
