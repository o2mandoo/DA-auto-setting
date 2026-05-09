# Metadata Provenance and DB Comment Business Rules

This document is the product rule source for DB comments, no-comment gaps, test-only synthetic comments, and Text-to-SQL dictionary/context usage.

## Correct product framing

The product rule is not that DB comments are merely test metadata. The product rule is:

1. **Real DB table/column comments and descriptions are product-usable semantic metadata.** When present, scanners must preserve them with `metadata_source=real_db_comment`, source detail, confidence/status, and safe evidence references. They may be used as draft Text-to-SQL dictionary/context data until a human confirms or supersedes them.
2. **Missing DB comments are explicit metadata gaps, not failures.** Scanners must mark missing comments with `metadata_source=no_comment` and create structured metadata-gap findings that the Reverse Question Generator can turn into domain/user confirmation questions.
3. **Test-only synthetic comments are fixture-only.** Synthetic comments generated for lab/fixture DBs must carry `metadata_source=test_only_synthetic_comment`, `is_test_only=true`, and must never become approved semantic truth or approved Text-to-SQL context automatically.
4. **All metadata must carry provenance and status.** Runtime and retrieval must disclose which context source was used and warn when using draft/comment-only context.
5. **DB backend selection must be explicit.** Any DB-backed loader, scanner, demo, or n8n workflow must declare the intended `db_backend`/target. It must not silently reroute a requested backend to PostgreSQL, DuckDB, SQLite, or a fake adapter.

## Metadata source taxonomy

| metadata_source | Product meaning | Default status | Text-to-SQL use | Human confirmation |
|---|---|---|---|---|
| `real_db_comment` | Real table/column comment or description read from a DB catalog | `draft` | Allowed as draft context with warning | Required before approved truth |
| `no_comment` | Explicit absence of table/column description | `open` gap | Not context truth; creates questions | Required |
| `test_only_synthetic_comment` | Generated fixture/lab comment | `draft` test-only | Excluded from approved product context | Required and must be re-sourced before approval |
| `sidecar_metadata` | External metadata file supplied for onboarding | `draft` | Allowed only if policy marks it usable | Required before approval |
| `llm_hypothesis` | LLM-generated meaning hypothesis | `draft` | Draft only with warning | Required before approval |
| `human_confirmed` | Human-confirmed definition/evidence | `approved` or `confirmed` | Preferred context | Already confirmed |
| `verified_query` | Verified query or query template | `confirmed` | Trusted query context | Already verified |

## DB-backed comment modes

DB-backed fixture/demo flows must expose the selected comment mode and map it to provenance in the same way for every supported backend.

| comment mode | Catalog/comment reality | Required provenance behavior | Fallback rule |
|---|---|---|---|
| `no_comments` | Tables/columns have no DB comments or descriptions. | Emit `metadata_source=no_comment`, `metadata_gap_reason`, and reverse-question inputs. | Do not synthesize replacement comments. |
| `real_comments` | Real catalog comments/descriptions are present or supplied by a source manifest. | Emit `metadata_source=real_db_comment`, safe `source_detail`, draft status, and comment-only context warnings. | If no real manifest/catalog comment exists, mark the mode unavailable. |
| `synthetic_comments` | Fixture/lab comments were generated for comparison or debugging. | Emit `metadata_source=test_only_synthetic_comment`, `is_test_only=true`, and exclude from approved product context. | Never promote to real comments or approved truth automatically. |

`real_comments` means source- or catalog-derived comments only. Generated text is always `synthetic_comments` unless a human explicitly confirms and re-sources it through the human-confirmation path.

## DB backend support rules

- PostgreSQL is the current primary DB-backed scanner/fixture target.
- MySQL targets must preserve the same metadata provenance contract when implemented: MySQL table/column comments are `real_db_comment`; missing comments are `no_comment`; lab-generated MySQL comments are `test_only_synthetic_comment`.
- MySQL readiness evidence must distinguish mocked/fake connector tests from explicit live fixture execution. Default tests must not require a live MySQL database.
- Optional live loaders may run only when explicitly called with safe fixture environment settings and local fixture schema/database names.
- Oracle is unsupported for fake fixture/scanner behavior. Unsupported backends must fail visibly instead of returning fake success or another backend's results.
- n8n and other orchestration wrappers must display the selected `db_backend`, selected comment mode, context-source warnings, and any unavailable mode rather than hiding backend/comment-mode decisions.

## Required provenance fields

- `metadata_source`
- `source_detail`
- `confidence`
- `status`
- `is_test_only`
- `can_use_for_text2sql`
- `requires_human_confirmation`
- optional `metadata_gap_reason`
- backend/comment-mode detail when metadata came from a DB-backed fixture or scanner (`db_backend`, comment mode, catalog/manifest source detail, or equivalent safe fields)

## Allowed transitions

- `real_db_comment` → draft Semantic Pack context → human-confirmed approved context.
- `no_comment` → metadata gap → reverse question → human-confirmed context.
- `test_only_synthetic_comment` → fixture evidence only; never direct approved truth.
- `llm_hypothesis` → draft proposal only → human confirmation required.
- `human_confirmed` → approved semantic context.
- `verified_query` → trusted query context.

## Context use rules

| Surface | Allowed sources | Required disclosure |
|---|---|---|
| Draft Semantic Pack | `real_db_comment`, `sidecar_metadata`, `llm_hypothesis`, `no_comment` gaps as questions | provenance/status/gap reason |
| Approved Semantic Pack | `human_confirmed`, `verified_query`, reviewed real comments after confirmation | approval evidence |
| VDB/card index | allowed context sources only; exclude test-only approved truth | source/status metadata |
| Text-to-SQL retrieval | `human_confirmed`, `verified_query`, approved dictionaries first; `real_db_comment` as draft with warning | `used_context_sources` |
| SQL generation | prefer human/verified; use real DB comments only as draft evidence | warnings when comment-only |
| Final answer explanation | disclose source and status of context used | source/status/warning |
| n8n/demo workflow | explicit `db_backend`, comment mode, and product API/adapter result | backend, mode, unavailable/failure state, source/status/warning |

## Enforcement map

- Contracts: `semantic_contracts.models.MetadataProvenance` and card models.
- DB scanner: Postgres catalog comment scan, no-comment gap detection, synthetic marker detection.
- Builder: profile/hypothesis/question artifacts must preserve provenance and metadata gaps.
- Registry/search: card documents must expose and filter provenance according to `can_use_for_text2sql`.
- Runtime/MCP/API: query plans and answer payloads must include `used_context_sources`, source status, and warnings.
- Fixture harness: synthetic comments must remain under fixture paths and `semantic_fixture_*` schemas only.
- n8n/demo wrappers: backend and comment-mode selection must be explicit and visible; unsupported or unavailable backends/modes must surface as failures or unavailable states, not fallback success.
