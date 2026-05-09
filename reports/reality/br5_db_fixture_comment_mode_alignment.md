# BR-5 — DB Fixture Comment Mode Alignment

## Purpose

This report aligns DB fixture work with the corrected product rule:

- real DB comments/descriptions are product-usable draft semantic metadata,
- missing comments are metadata gaps and reverse-question inputs,
- synthetic comments are test-only fixture annotations and never product truth.

## Fixture modes

| Mode | Meaning | Product behavior | Fixture behavior |
|---|---|---|---|
| `no_comments` | Tables/columns have no DB comments. | Emit `metadata_source=no_comment`; generate metadata gaps and reverse questions. | SQL plan contains no `COMMENT ON` statements. |
| `real_comments` | Manifest/source provides actual comments/descriptions. | Emit `metadata_source=real_db_comment`; use as draft Text-to-SQL context with warning. | SQL plan uses only provided comments; missing manifest marks mode unavailable. |
| `synthetic_comments` | Generated comments for lab/debug. | Exclude from approved product context; mark `test_only_synthetic_comment`. | Comments contain `TEST_ONLY_SYNTHETIC_METADATA`. |

## Current dataset reality

The current copied Superstore/Sinagong files are file-origin datasets, not live DB catalogs. They generally do not include authoritative table/column catalog comments. Therefore:

- `no_comments` is the realistic default for DB fixture loading from these files.
- `real_comments` is available only when a manifest supplies actual source descriptions.
- `synthetic_comments` is allowed only for upper-bound/debug comparisons.

No synthetic fallback is used when real comments are missing.

## Generated comparison artifacts

- `reports/reality/db_fixture_comment_mode_comparison.json`
  - no real-comment manifest supplied; real-comment mode is explicitly unavailable.
- `reports/reality/db_fixture_comment_mode_comparison_with_real_comments.json`
  - example manifest comments supplied; real-comment mode becomes available and draft Text-to-SQL context is marked with `comment_only_draft_context`.

## n8n readiness recommendation

PARTIAL until a live Postgres fixture run is executed in the user environment. The code-level fixture mode contracts and scanner behavior are ready for local DB validation, but no report should claim live DB evidence unless the explicit fixture safety gate was used.
