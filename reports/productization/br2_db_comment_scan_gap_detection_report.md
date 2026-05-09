# BR-2 — DB Comment Scan and No-Comment Gap Detection

## Verdict

PASS.

## Changed files

- `packages/semantic_builder/src/semantic_builder/connectors/db.py`
- `packages/semantic_builder/src/semantic_builder/connectors/postgres_connector.py`
- `packages/semantic_builder/src/semantic_builder/scanner/postgres.py`
- `packages/semantic_builder/src/semantic_builder/metadata.py`
- `packages/semantic_builder/src/semantic_builder/builder/draft_pack.py`
- `tests/builder/test_db_comment_metadata_gaps.py`

## Implemented behavior

- PostgreSQL table/column comments are scanned from `obj_description` and `col_description`.
- Present comments become `metadata_source=real_db_comment` unless they include the explicit `TEST_ONLY_SYNTHETIC_METADATA` marker.
- Absent comments become `metadata_source=no_comment` with structured metadata gaps.
- Synthetic fixture comments become `metadata_source=test_only_synthetic_comment` and are marked `is_test_only=true` / `can_use_for_text2sql=false`.
- Scanner reports and pack drafts preserve provenance.

## Metadata gap coverage

Structured gaps are emitted for:

- missing table comments
- missing column comments
- abstract columns such as status/type/code/category/channel/segment
- possible PII columns
- join-key ambiguity
- multiple date candidates
- multiple metric-like numeric candidates

## Tests run

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 -m pytest -q tests/builder/test_db_comment_metadata_gaps.py
```

Result: covered by the targeted suite, also included in the later 18-test and 24-test phase runs.

## Manager evaluation

PASS. Missing comments do not cause scanner failure; they produce explicit gap evidence. Comments do not auto-approve definitions.

## Remaining risks

- Live PostgreSQL catalog verification still requires a local fixture DB run with `SEMANTIC_CONTEXT_FIXTURE_DB=1`; no fallback DB is substituted.
