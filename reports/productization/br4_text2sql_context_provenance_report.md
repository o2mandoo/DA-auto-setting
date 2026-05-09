# BR-4 — Text-to-SQL Dictionary Context from DB Comments and Semantic Metadata

## Verdict

PASS.

## Changed files

- `packages/semantic_registry/semantic_registry/cards.py`
- `packages/semantic_registry/semantic_registry/search.py`
- `packages/semantic_registry/semantic_registry/query_planner.py`
- `packages/semantic_registry/semantic_registry/runtime/query_planner.py`
- `packages/semantic_registry/semantic_registry/runtime/verifiers.py`
- `packages/semantic_registry/semantic_registry/product/api.py`
- `packages/semantic_registry/semantic_registry/product/view_models.py`
- `packages/semantic_contracts/semantic_contracts/mcp_tool_contracts.py`
- `packages/semantic_contracts/semantic_contracts/runtime_contracts.py`
- `tests/registry/test_text2sql_provenance_context.py`

## Implemented behavior

- Real DB comments can be flattened as Table/Column Card context.
- Search filters out `no_comment` and `test_only_synthetic_comment` when they are not usable for Text-to-SQL.
- Human-confirmed definitions remain approved context and can outrank raw comments in planning.
- Query planning/runtime/product API surfaces expose `used_context_sources`, `source_status`, and `context_warnings`.
- Comment-only context produces `comment_only_draft_context` warning.
- Metadata gaps remain onboarding/question evidence, not Text-to-SQL truth.

## Sample retrieval/runtime evidence

- Searching a real-comment column returns metadata source `real_db_comment` and `can_use_for_text2sql=true`.
- Searching a synthetic fixture-only column returns no result.
- Planning for a human-confirmed metric reports `used_context_sources=['human_confirmed']` and `source_status['human_confirmed']='approved'`.

## Tests run

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 -m pytest -q tests/registry/test_text2sql_provenance_context.py
```

Result: covered by the targeted suite, also included in the later 18-test and 24-test phase runs.

## Manager evaluation

PASS. No synthetic fixture truth leakage was found and runtime provenance disclosure is present.

## Remaining risks

- Missing-context safe-failure behavior is represented in product/API failure states, but should be demonstrated in a live n8n workflow only after the DB-backed harness is verified.
