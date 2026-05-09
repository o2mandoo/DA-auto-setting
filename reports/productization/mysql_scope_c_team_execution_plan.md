# MySQL Scope C Team Execution Plan

## Scope C definition

Scope C means MySQL is added as a DB-backed target through three layers:

1. Fixture target: MySQL-specific DDL/comment planner and safety gate.
2. Scanner target: read-only MySQL metadata/comment scanner that emits the same provenance contract as PostgreSQL.
3. Live/e2e harness: optional local MySQL fixture loading and scan evidence path. If local MySQL is unavailable, evidence is marked pending explicitly; no fallback backend is used.

## Non-goals

- No n8n workflow JSON creation.
- No Oracle implementation.
- No production DB connection.
- No general SQL execution surface.
- No silent MySQL-to-PostgreSQL/DuckDB/SQLite fallback.

## Team lanes

### Worker 1 — mysql-fixture-loader-dev
Owns product-external fixture DDL planner/loader for MySQL.

### Worker 2 — mysql-scanner-dev
Owns MySQL connector/scanner and provenance propagation.

### Worker 3 — live-e2e-harness-dev
Owns cross-DB/live optional evidence runner and e2e comparison artifacts.

### Worker 4 — docs-readiness-dev
Owns docs, env template, and n8n readiness report updates.

### Worker 5 — tests-hardening-dev
Owns focused tests, no-silent-fallback/security assertions, and regression command wiring.

### Worker 6 — verifier
Owns final inspection, test execution, scope violation checks, and final verification report.

## Acceptance criteria

- MySQL fixture planner supports no_comments, real_comments, synthetic_comments.
- MySQL DDL uses MySQL comment syntax, not PostgreSQL syntax.
- MySQL safety gate rejects production-looking DSNs and non-local hosts.
- MySQL scanner reads table/column comments from information_schema using mocked/fake connection tests.
- no_comment produces metadata gaps and reverse-question evidence.
- synthetic comments carry TEST_ONLY_SYNTHETIC_METADATA and are not context truth.
- Optional live MySQL loader exists but is gated and explicit.
- Reports show live evidence status accurately.
- Full test suite passes or failures are reported with exact required fixes.
