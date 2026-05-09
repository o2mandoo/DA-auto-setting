# BR-3 — Reverse Question Generator from Comment and Metadata Gap Signals

## Verdict

PASS.

## Changed files

- `packages/semantic_builder/src/semantic_builder/inference/reverse_questions.py`
- `packages/semantic_builder/src/semantic_builder/inference/pipeline.py`
- `tests/builder/test_comment_aware_reverse_questions.py`

## Implemented behavior

- Reverse questions consume `metadata_source` and structured `metadata_gaps`.
- Informative real DB comments are used as evidence and reduce generic question spam.
- Missing comments on uncertain or abstract columns create targeted questions.
- Vague comments create clarification questions.
- Comment/profile conflicts create clarification questions.
- Questions include evidence source, metadata-gap reason, expected answer type, candidate options, severity, and risk if unanswered.
- Synthetic comments remain fixture-only evidence and are not promoted.

## Sample question behavior

- `no_comment` + `status` column -> asks for value dictionary/business meaning and cites `metadata_gap_reason=abstract_column_without_comment`.
- vague `real_db_comment` such as `code` -> asks for clarification instead of accepting it as truth.
- conflicting comment/profile such as numeric `amount` described as customer name -> asks for clarification.

## Tests run

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 -m pytest -q tests/builder/test_comment_aware_reverse_questions.py
```

Result: covered by the targeted suite, also included in the later 18-test and 24-test phase runs.

## Manager evaluation

PASS. Real comments are evidence, absent comments are reverse-question triggers, and no automatic approval path was introduced.

## Remaining risks

- Question prioritization is deterministic/rule-based; richer ranking may be needed after live domain feedback.
