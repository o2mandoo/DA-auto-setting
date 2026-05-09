# Weaviate Multi-domain Semantic-gold PII Safety Report

Date: 2026-05-09 KST

## Scope

Worker-5 safety audit for the no-raw-PII rule across generated artifacts and indexed payloads.

This report stays within the local repository boundary:

- no product code changes outside the allowed security/docs/report surfaces,
- no SQL execution,
- no dashboard/UI or SaaS work,
- no production credential access,
- no silent fallback to keyword search for explicit Weaviate paths.

## What was verified

1. `docs/execution/SECURITY_CHECKLIST.md` now states that PII candidates must not emit raw values into indexed search payloads and that generated benchmark/final-report artifacts under `reports/**` must stay free of raw PII literals.
2. `tests/security/test_phase12_hardening.py` now checks:
   - search-document projections from the demo pack remain PII-safe,
   - blocked columns do not produce raw value-dictionary payloads,
   - generated benchmark and final-report artifacts do not contain known raw PII literals,
   - existing hardening checks still pass for execute-query, credentials, SQL red-team cases, and explicit VDB fallback behavior.

## Evidence

Security suite:

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 -m unittest discover -s tests/security -v
```

Result:

```text
Ran 10 tests in 0.293s
OK
```

Repo scan:

- `reports/benchmarks/` and `reports/final/` contain no known raw PII literals from the configured forbidden email, phone, or person-name fixtures. The literals are intentionally not repeated in this report.
- `semantic_registry.retrieval.documents_from_pack()` on `demo_company.revenue` does not produce raw value-dictionary payloads for the blocked `users.email`, `users.phone`, or `users.name` columns.

## Remaining constraint

The current workspace tree is not a git repository, so I could not create the protocol-mandated commit from this directory. The nearest sibling checkout on this machine is `/Users/jtm427/Desktop/workplace/claude-code`, but it is a different project tree and was not used for this task.

