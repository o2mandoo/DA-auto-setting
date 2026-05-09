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

## Safety gates

- No production DB connection.
- No production SQL execution.
- No checked-in credentials.
- No raw PII in sample payloads.
- No hidden DuckDB/SQLite fallback when a Postgres fixture was requested.
- Live fixture DB execution requires `SEMANTIC_CONTEXT_FIXTURE_DB=1` and `semantic_fixture_*` schema/database names.
- Unsupported DBs such as MySQL/Oracle must fail explicitly until real connectors are implemented.

## Minimum workflows

1. DB-backed Onboarding Demo.
2. Comment-aware Reverse Question Demo.
3. Human Confirmation + Pack Promotion.
4. Query Runtime with Baseline vs System SQL Comparison.
5. Failure-safe Demo.
6. 20-domain/fixture Benchmark Runner.

## Demo is READY only when

- no-comment mode produces gaps/questions in a DB-backed run,
- at least one comment-present mode produces draft Text-to-SQL context,
- synthetic comments are shown as fixture-only and excluded from product truth,
- Product API/adapter invocation is stable from n8n,
- failures are visible as failures rather than silently rerouted.
