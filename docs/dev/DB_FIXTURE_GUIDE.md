# DB Fixture Guide

This guide describes product-external DB fixture tooling. It is not product runtime and does not create customer-facing metadata-generation capability.

## Modes

- `no_comments`: creates DB tables without table/column comments. Product scanners must emit `metadata_source=no_comment` and metadata gaps.
- `real_comments`: uses actual comments/descriptions supplied by a source manifest. These comments are product-usable draft semantic metadata.
- `synthetic_comments`: generates comments with `TEST_ONLY_SYNTHETIC_METADATA`. These are fixture-only upper-bound/debug annotations and never approved product truth.

## Safety gates

- `SEMANTIC_CONTEXT_FIXTURE_DB=1` is required for any live fixture DB load.
- PostgreSQL fixture schema must start with `semantic_fixture_`.
- Production-looking DSNs are refused.
- MySQL/Oracle are not supported by this fixture harness until real vetted connectors exist.
- No silent fallback: DuckDB/SQLite smoke exports, if added, must be explicitly selected and cannot replace a requested Postgres run.

## n8n handoff criterion

n8n live work may start only after DB-backed evidence proves:

1. seeded Postgres fixture exists or environment failure is explicit,
2. scan/profile succeeds,
3. build-pack succeeds,
4. no_comments create gaps/questions,
5. real_comments become context,
6. synthetic_comments remain test-only,
7. readiness report is generated.
