# n8n DB-Backed Demo Requirements

## Purpose

n8n is a demo/orchestration wrapper around the Semantic Data Context product APIs and fixture tooling. It must not become the source of truth and must not implement hidden fallback logic.

## Comment-mode requirements

Every DB-backed demo workflow must show the selected fixture/comment mode:

- `no_comments`: no catalog comments; scanner should emit metadata gaps and reverse questions.
- `real_comments`: source/manifest-provided comments; scanner should emit draft product context with `real_db_comment` provenance.
- `synthetic_comments`: generated lab comments marked `TEST_ONLY_SYNTHETIC_METADATA`; fixture-only and excluded from approved product context.

If `real_comments` are requested but the manifest has no real comments, the workflow must display that as unavailable. It must not generate synthetic comments as a silent replacement.

## Required visible fields

Workflows that answer or plan a query must display:

- `used_context_sources`
- `cards_used`
- `source_status`
- `context_warnings`
- whether context is draft/comment-only/human-confirmed/verified
- whether a missing context should become a reverse-question task

## DB-backed validation targets

The supported DB-backed demo targets are PostgreSQL fixtures and explicit MySQL validation runs. The selected target must be visible in n8n output and in any generated comparison artifact.

- PostgreSQL remains the default fixture-backed validation target when `SEMANTIC_CONTEXT_FIXTURE_DB=1` and `semantic_fixture_*` schema/database names are used.
- MySQL is opt-in only: `SEMANTIC_MYSQL_ENABLED=1`, `SEMANTIC_MYSQL_DSN`, `SEMANTIC_MYSQL_DATABASE`, and `SEMANTIC_MYSQL_TABLES` must be provided before MySQL evidence is attempted.
- If MySQL connector support, `pymysql`, or required config is unavailable, the workflow must report `live_mysql_evidence_pending` or an explicit configuration error. It must not reroute to PostgreSQL, DuckDB, or SQLite.

## Safety gates

- No production DB connection.
- No production SQL execution or `execute_query` path.
- No checked-in credentials.
- No raw PII in sample payloads.
- No hidden PostgreSQL/DuckDB/SQLite fallback when a MySQL target was requested.
- No hidden DuckDB/SQLite fallback when a PostgreSQL fixture was requested.
- Live fixture DB access requires the target-specific opt-in environment variables above and demo-only schema/database names.
- Unsupported DBs such as Oracle must fail explicitly until real connectors are implemented.

## Minimum workflows

1. DB-backed Onboarding Demo.
2. Comment-aware Reverse Question Demo.
3. Human Confirmation + Pack Promotion.
4. Query Runtime with Baseline vs System SQL Comparison.
5. MySQL Baseline vs System SQL Comparison Artifact.
6. Failure-safe Demo.
7. 20-domain/fixture Benchmark Runner.

## Demo is READY only when

- no-comment mode produces gaps/questions in a DB-backed run,
- at least one comment-present mode produces draft Text-to-SQL context,
- synthetic comments are shown as fixture-only and excluded from product truth,
- Product API/adapter invocation is stable from n8n,
- PostgreSQL and MySQL comparison artifacts show the requested target and evidence status,
- failures are visible as failures rather than silently rerouted.
