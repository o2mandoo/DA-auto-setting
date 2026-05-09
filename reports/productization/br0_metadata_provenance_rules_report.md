# BR-0 — Metadata Provenance and Comment Usage Rules

## Changed files

- `docs/product/METADATA_PROVENANCE_RULES.md`
- `reports/reality/metadata_provenance_business_rule_audit.md`

## Business rules added

- Real DB table/column comments are product-usable semantic metadata.
- Missing DB comments are metadata gaps and Reverse Question Generator inputs.
- Synthetic comments are fixture-only and never approved product truth automatically.
- All metadata carries source/status/provenance.
- Runtime/Text-to-SQL surfaces must disclose context source and status.

## Future enforcement points

- contracts: provenance model/card fields
- builder/scanner: comment scan, no-comment gaps, synthetic marker detection
- registry/search: allowed source filtering and source disclosure
- runtime/MCP/API: `used_context_sources` and draft/comment-only warnings
- fixture harness: no_comments, real_comments, synthetic_comments separation

## Manager evaluation

PASS. No product code was changed in this phase.
