# BR-1 — Metadata Provenance Model Implementation

## Verdict

PASS.

## Changed files

- `packages/semantic_contracts/semantic_contracts/models.py`
- `packages/semantic_contracts/semantic_contracts/__init__.py`
- `packages/semantic_registry/semantic_registry/cards.py`
- `packages/semantic_registry/semantic_registry/search.py`
- `packages/semantic_builder/src/semantic_builder/metadata.py`
- `tests/contracts/test_metadata_provenance.py`
- `tests/registry/test_text2sql_provenance_context.py`

## Provenance model summary

The contract now distinguishes:

- `real_db_comment`
- `no_comment`
- `test_only_synthetic_comment`
- `sidecar_metadata`
- `llm_hypothesis`
- `human_confirmed`
- `verified_query`

Each provenance item includes source, source detail, confidence, status, test-only flag, Text-to-SQL usability, human confirmation requirement, and optional metadata-gap reason.

## Enforcement evidence

- `test_only_synthetic_comment` cannot be approved/confirmed and cannot be used as Text-to-SQL context.
- `no_comment` requires `metadata_gap_reason` and is never Text-to-SQL truth.
- `real_db_comment` is usable as draft Text-to-SQL context.
- `human_confirmed` / `verified_query` can be approved trusted context.
- Cards preserve provenance through flattening and retrieval metadata.

## Tests run

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 -m pytest -q tests/contracts/test_metadata_provenance.py tests/registry/test_text2sql_provenance_context.py
```

Result: covered by the targeted suite, also included in the later 18-test and 24-test phase runs.

## Manager evaluation

PASS against BR-1 criteria. No n8n workflow was created and no product source-of-truth rule was weakened.

## Remaining risks

- Existing packs without provenance remain backward-compatible, but should be migrated when promoted to approved product context.
