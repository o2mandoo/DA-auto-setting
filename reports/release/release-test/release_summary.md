# Release Packet: release-test

- generated_at: 2026-05-10T02:01:12.334220+00:00
- git_commit: 8f1f3fab00c94c16c46971073ec7dcae2eb81ca1
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

- PR-7 CI, observability, release packet: missing external/live evidence: live CI run log, signed or promoted release candidate approval

## n8n status

- status: pr6_completed_live_runtime_smoke_present
- readiness: demo_orchestration_only_not_production
- evidence: reports/productization/pr6_n8n_live_runtime_smoke.md, reports/productization/phase20_n8n_readiness_report.md
- summary: PR-6 live n8n runtime smoke evidence is present; n8n is demo orchestration over product APIs, not source of truth or production SQL execution.

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

- email: 4
- worker_id: 3
