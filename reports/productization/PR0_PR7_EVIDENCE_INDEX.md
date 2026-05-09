# PR-0 through PR-7 Evidence Index

Date: 2026-05-09 KST
Owner: worker-1
Task: Collect evidence from PR-0 through PR-7, plus optional DB/comment/SQL comparison evidence when available.

## Purpose

This index collects the current evidence artifacts for the PR-0 through PR-7 productization line in one place. It points to the primary report files and supporting docs/tests that already exist in the repository. Where a PR does not yet have a dedicated standalone artifact, the best current evidence source is noted explicitly.

## Core PR evidence map

| PR | Evidence status | Primary evidence source | Notes |
|---|---|---|---|
| PR-0 | PASS | `reports/phases/productization_phase0.md` | Phase 0 clone-ready baseline report with scope, changed files, and verification evidence. |
| PR-1 | PASS | `reports/productization/PR1_CLEAN_CLONE_EVIDENCE.md` | Clean-clone packaging baseline evidence and current leader/main truth alignment. |
| PR-2 | PASS | `reports/productization/PR2_HTTP_ADAPTER_EVIDENCE.md` | HTTP adapter verifier refresh with env-check, regression sweep, security checks, smoke, and static audit. |
| PR-3 | PASS | `reports/productization/PR3_MCP_SAFE_RUNTIME_EVIDENCE.md` | Safe runtime/MCP evidence with environment check, registration-surface inspection, and acceptance sweep. |
| PR-4 | PASS | `reports/productization/PR4_DB_FIXTURE_READONLY_EVIDENCE.md` | Live fixture DB read-only evidence packet for PostgreSQL/MySQL. |
| PR-5 | PASS | `reports/productization/PR5_PRECHECK_DB_CORPUS_EVIDENCE.md`, `reports/productization/PR5_SEMANTIC_RETRIEVAL_EVIDENCE.md` | Live DB corpus precheck plus semantic retrieval evidence. |
| PR-6 | PARTIAL | `reports/productization/phase20_n8n_readiness_report.md`, `reports/productization/final_n8n_readiness_evaluate_after_comment_rules.md`, `reports/productization/PRODUCTION_READINESS_MATRIX.md` | No dedicated PR-6 report file found; current evidence is the n8n readiness analysis and matrix guidance. |
| PR-7 | PARTIAL | `reports/productization/PRODUCTION_READINESS_MATRIX.md`, `reports/productization/PRODUCTION_RISK_REGISTER.md`, `reports/productization/s21_41_execution_final_report.md` | No dedicated PR-7 release packet file found; current evidence is the readiness matrix, risk register, and final execution report. |

## Optional evidence requested by the task

### 1) DB fixture / read-only evidence

Available and strongest current source:

- `reports/productization/PR4_DB_FIXTURE_READONLY_EVIDENCE.md`

Key proof points captured there:

- live local PostgreSQL fixture service loaded successfully,
- live local MySQL fixture service loaded successfully,
- both ran under explicit fixture-only gates,
- no fallback backend was used,
- no reroute to PostgreSQL/DuckDB/SQLite/cached JSON/synthetic comments occurred.

### 2) No-comment / real-comment / synthetic-comment evidence

Available current sources:

- `docs/product/METADATA_PROVENANCE_RULES.md`
- `tests/builder/test_db_comment_metadata_gaps.py`
- `tests/fixtures/test_db_fixture_comment_modes.py`
- `tests/registry/test_text2sql_provenance_context.py`
- `tests/contracts/test_metadata_provenance.py`
- `reports/productization/final_n8n_readiness_evaluate_after_comment_rules.md`
- `reports/productization/br5_db_fixture_harness_alignment_report.md`

Key proof points captured across those sources:

- `real_db_comment` is draft product-usable semantic metadata,
- `no_comment` is an explicit gap and reverse-question input,
- `test_only_synthetic_comment` stays fixture-only and cannot become approved truth,
- DB-backed demo flows must surface the selected backend and comment mode,
- synthetic comments are blocked from approved Text-to-SQL truth.

### 3) Baseline SQL vs system SQL comparison evidence

Available current sources:

- `reports/productization/phase15_sql_comparison_engine.md`
- `docs/product/BASELINE_COMPARISON_SPEC.md`
- `docs/product/PRODUCT_MODES.md`
- `docs/api/examples/compare_sql_request.json`
- `packages/semantic_registry/semantic_registry/product/comparison.py`
- `packages/semantic_mcp/src/semantic_mcp/tools/__init__.py`
- `reports/reality/db_fixture_comment_mode_comparison.json`
- `reports/reality/db_fixture_comment_mode_comparison_with_real_comments.json`

Key proof points captured across those sources:

- comparison profiles SQL text only,
- baseline and system candidates are not executed,
- `compare_baseline_vs_system_sql` is exposed through MCP,
- comparison surfaces can show baseline/system differences without mutating execution state,
- the docs and example payloads keep the comparison flow explicit and non-executing.

## Current gaps / observations

- PR-6 and PR-7 do not appear to have standalone dedicated evidence packets yet; the strongest available evidence is embedded in readiness matrix, risk register, and related phase reports.
- The existing evidence set is sufficient to map the current productization story, but PR-6/PR-7 still read as partially synthesized rather than fully standalone release artifacts.

## Summary

The repository already contains solid evidence for PR-0 through PR-5, and supporting evidence for the PR-6 and PR-7 gates exists in readiness/risk/final-report documents. This index makes those sources easy to hand to the leader for audit or follow-up release packet work.
