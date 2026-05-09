# BR-5 — Real Comment vs No Comment DB Fixture Harness Alignment

## Verdict

PASS for code-level harness and planned/E2E comparison evidence. Live DB execution remains explicit and gated.

## Changed files

- `experiments/db_fixtures/scripts/fixture_modes.py`
- `experiments/db_fixtures/scripts/postgres_fixture_loader.py`
- `experiments/db_fixtures/scripts/mode_comparison.py`
- `docs/dev/DB_FIXTURE_GUIDE.md`
- `reports/reality/br5_db_fixture_comment_mode_alignment.md`
- `reports/reality/db_fixture_comment_mode_comparison.json`
- `reports/reality/db_fixture_comment_mode_comparison_with_real_comments.json`
- `tests/fixtures/test_db_fixture_comment_modes.py`
- `tests/e2e/test_db_fixture_comment_mode_comparison.py`

## Fixture modes supported

- `no_comments`: no SQL comments; expected scanner behavior is `metadata_source=no_comment` + gaps/questions.
- `real_comments`: uses manifest/source-provided comments only; product-usable as draft context.
- `synthetic_comments`: generated comments include `TEST_ONLY_SYNTHETIC_METADATA`; fixture-only and not product truth.

## E2E comparison outputs

Generated artifacts:

- `reports/reality/db_fixture_comment_mode_comparison.json`: current sales-style fixture with no real comment manifest, explicitly marks real-comment mode unavailable.
- `reports/reality/db_fixture_comment_mode_comparison_with_real_comments.json`: manifest-provided real-comment example proving real comments can be represented and compared.

Comparison dimensions include reverse-question count, useful metadata coverage, Text-to-SQL context availability, pack-draft quality, runtime warnings, and baseline-vs-system SQL difference.

## Safety and no-fallback behavior

- `SEMANTIC_CONTEXT_FIXTURE_DB=1` is required for live fixture DB loading.
- Fixture schemas must start with `semantic_fixture_`.
- Production-looking DSNs are refused.
- Non-PostgreSQL DSNs are rejected with an explicit reason; no MySQL/Oracle fake support was added.
- Missing real-comment manifests are marked unavailable; synthetic comments are not used as a fallback.

## Tests run

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 -m pytest -q tests/fixtures/test_db_fixture_comment_modes.py tests/e2e/test_db_fixture_comment_mode_comparison.py
```

Result: `6 passed`.

## Manager evaluation

PASS. No n8n workflow was created in this phase. Synthetic metadata is not treated as approved semantic truth.

## Remaining risks

- The current repo has file-origin datasets, not actual PostgreSQL catalogs with real comments. Live DB-backed proof requires a local fixture Postgres run under the explicit safety gates.
