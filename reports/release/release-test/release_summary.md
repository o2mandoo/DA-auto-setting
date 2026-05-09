# Release Packet: release-test

- generated_at: 2026-05-09T15:33:05.098356+00:00
- git_commit: 7fcce00604bbfb62edecb67e44afda8a3b73abda
- status: dry-run release packet

## Evidence snapshot

- Production readiness matrix included.
- Risk register included.
- Known limitations included.
- Support matrix included.
- Secret-like and PII-like values are redacted before writing packet files.

## Missing source evidence

- none (all tracked source files exist; external/live gate gaps are listed separately below)

## Missing gate evidence

- PR-6 n8n workflow smoke: missing external/live evidence: live imported n8n workflow smoke output
- PR-7 CI, observability, release packet: missing external/live evidence: live CI run log, signed or promoted release candidate approval

## Baseline vs system SQL comparison evidence

- reports/productization/phase15_sql_comparison_engine.md: available
- docs/product/BASELINE_COMPARISON_SPEC.md: available
- docs/product/PRODUCT_MODES.md: available
- docs/api/examples/compare_sql_request.json: available
- packages/semantic_registry/semantic_registry/product/comparison.py: available
- packages/semantic_mcp/src/semantic_mcp/tools/__init__.py: available
- reports/reality/db_fixture_comment_mode_comparison.json: available
- reports/reality/db_fixture_comment_mode_comparison_with_real_comments.json: available

## Redaction summary

- local_path: 2
- worker_id: 3
