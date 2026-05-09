# Answer UI Specification

The local product UI is a demo surface for Mode C. It must show why Semantic Pack context changes the answer instead of hiding differences behind a single generated SQL block.

## Required panels

1. Query input: question, role, semantic space, mode selector.
2. Baseline SQL panel: physical-schema-only prompt result, provider, warnings, and `not_executed=true`.
3. System SQL panel: Semantic Pack powered plan/draft, selected terms/metrics/joins, validation status, and `execution_allowed=false`.
4. Difference summary: metric/date/join/filter/policy/PII/ambiguity differences.
5. Applied definitions: business terms, metric formulas, value dictionaries, policies, verified queries.
6. Verification panel: SQL guard result, semantic verifier result, preview eligibility.
7. Failure state panel: structured state such as `clarification_required`, `pii_blocked`, or `unsafe_sql_blocked`.
8. Suggested actions: ask a clarification, answer a confirmation question, adjust role, or promote a reviewed pack.

## UX rules

- The baseline panel must visibly state that it is not executed.
- Unsafe SQL must be shown as blocked evidence, not hidden.
- Missing context must surface as a product state with next steps.
- Preview rows may appear only for safe local fixture/test targets after validation.
- The UI must not become a BI application; it is for explanation, validation, and demos.
