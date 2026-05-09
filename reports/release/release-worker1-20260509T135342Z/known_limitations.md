## Known limitations

- Live Weaviate service benchmarking is not included; current tests verify explicit backend behavior and no silent keyword fallback.
- PostgreSQL support remains safe scan/profile scope with credential-free tests; no production DB execution is included.
- The demo pack was promoted to `approved` for final local package demo purposes, while generated Builder output remains draft/proposal-based.
- MCP stdio server creation is smoke-tested; complete client/server transport integration is still a later integration hardening item.
- Root `unittest discover -s tests` does not discover all tests; run per-suite commands listed above.
- Released evidence uses redacted fixture passwords in docs and reports; this packet intentionally avoids publishing credential-like DSN literals.

## Current known limitations

- `.xlsx` is supported and verified with `openpyxl`.
- legacy `.xls` is supported and verified with `xlrd` against Tableau Sample
  Superstore.
- Large workbook validation should be bounded and reported; do not turn every
  local development test into a full corpus scan unless the phase explicitly
  requires it.
