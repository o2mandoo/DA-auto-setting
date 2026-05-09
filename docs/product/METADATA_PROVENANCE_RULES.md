# Metadata Provenance and DB Comment Business Rules

This document is the product rule source for DB comments, no-comment gaps, test-only synthetic comments, and Text-to-SQL dictionary/context usage.

## Correct product framing

The product rule is not that DB comments are merely test metadata. The product rule is:

1. **Real DB table/column comments and descriptions are product-usable semantic metadata.** When present, scanners must preserve them with `metadata_source=real_db_comment`, source detail, confidence/status, and safe evidence references. They may be used as draft Text-to-SQL dictionary/context data until a human confirms or supersedes them.
2. **Missing DB comments are explicit metadata gaps, not failures.** Scanners must mark missing comments with `metadata_source=no_comment` and create structured metadata-gap findings that the Reverse Question Generator can turn into domain/user confirmation questions.
3. **Test-only synthetic comments are fixture-only.** Synthetic comments generated for lab/fixture DBs must carry `metadata_source=test_only_synthetic_comment`, `is_test_only=true`, and must never become approved semantic truth or approved Text-to-SQL context automatically.
4. **All metadata must carry provenance and status.** Runtime and retrieval must disclose which context source was used and warn when using draft/comment-only context.

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

## Required provenance fields

- `metadata_source`
- `source_detail`
- `confidence`
- `status`
- `is_test_only`
- `can_use_for_text2sql`
- `requires_human_confirmation`
- optional `metadata_gap_reason`

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

## Enforcement map

- Contracts: `semantic_contracts.models.MetadataProvenance` and card models.
- DB scanner: Postgres catalog comment scan, no-comment gap detection, synthetic marker detection.
- Builder: profile/hypothesis/question artifacts must preserve provenance and metadata gaps.
- Registry/search: card documents must expose and filter provenance according to `can_use_for_text2sql`.
- Runtime/MCP/API: query plans and answer payloads must include `used_context_sources`, source status, and warnings.
- Fixture harness: synthetic comments must remain under fixture paths and `semantic_fixture_*` schemas only.
