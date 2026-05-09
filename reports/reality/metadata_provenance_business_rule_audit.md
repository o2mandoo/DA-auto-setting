# BR-0 Audit — Metadata Provenance and DB Comment Rules

## Findings

- Current productization docs already separate synthetic fixture comments from product truth, but they did not clearly state the corrected positive rule: real DB comments are product-usable Text-to-SQL semantic metadata.
- Current scanner code did not yet read Postgres table/column comments from the DB catalog.
- Current no-comment behavior did not explicitly create metadata-gap records that can feed reverse questions.
- Current Text-to-SQL search/card context did not expose a full provenance taxonomy or source/status transitions.
- Existing synthetic-comment fixture framing must be preserved as fixture-only and must not be mistaken for approved semantic truth.

## Inconsistencies to repair in implementation

1. Add enforceable provenance model rather than free-form strings only.
2. Add real DB comment scan and `no_comment` gap detection.
3. Propagate comment/gap provenance through Builder profiles, hypotheses, reverse questions, draft packs, cards, retrieval, and runtime output.
4. Keep synthetic fixture comments excluded from approved Text-to-SQL truth.

## No-code phase verification

BR-0 changed documentation and audit reports only. Product runtime code remains unchanged in this phase.
