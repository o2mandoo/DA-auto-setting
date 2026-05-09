# n8n Readiness After Corrected DB Comment Business Rules

## Classification

**PARTIAL**

The product contracts and local code paths now support the corrected rule for real DB comments, no-comment gaps, synthetic fixture separation, Text-to-SQL provenance, and fixture-mode comparison. n8n workflow implementation can be planned, but should not be treated as fully READY until a live Postgres fixture run proves the DB-backed path end to end under explicit fixture safety gates.

## Evidence reviewed

- Business rules: `docs/product/METADATA_PROVENANCE_RULES.md`
- BR-1 report: `reports/productization/br1_metadata_provenance_model_report.md`
- BR-2 report: `reports/productization/br2_db_comment_scan_gap_detection_report.md`
- BR-3 report: `reports/productization/br3_comment_aware_reverse_questions_report.md`
- BR-4 report: `reports/productization/br4_text2sql_context_provenance_report.md`
- BR-5 report: `reports/productization/br5_db_fixture_harness_alignment_report.md`
- Fixture comparison: `reports/reality/db_fixture_comment_mode_comparison.json`
- Fixture comparison with manifest real comments: `reports/reality/db_fixture_comment_mode_comparison_with_real_comments.json`

## Readiness criteria

| Criterion | Status | Evidence |
|---|---|---|
| Real DB comments can be scanned and represented. | PASS | PostgreSQL scanner reads table/column comments and emits `real_db_comment`. |
| Real DB comments can be used as Text-to-SQL context. | PASS | Search/planner preserve provenance and emit draft warnings. |
| Missing comments produce gaps/questions. | PASS | `no_comment` metadata gaps feed reverse questions. |
| Synthetic comments remain test-only. | PASS | Marker detection, search exclusion, fixture-only reports. |
| Runtime discloses context provenance. | PASS | Runtime/Product API models expose `used_context_sources`, `source_status`, `context_warnings`. |
| DB-backed E2E tests prove mode differences. | PARTIAL | Planned/code-level harness and comparison tests exist; live Postgres fixture execution remains gated and not yet run. |
| Baseline vs system SQL comparison can show differences. | PARTIAL | Existing comparison product surface exists; comment-mode comparison explains expected baseline/system differences, but live n8n visualization is not created. |
| Failure-safe behavior is visible. | PASS | Product failure-safe reports and no-silent-fallback fixture behavior exist. |
| API endpoints are stable enough for n8n. | PARTIAL | Product API pure Python contract exists; HTTP adapter/live n8n binding remains next work. |

## Blockers before READY

1. Run a live local Postgres fixture with `SEMANTIC_CONTEXT_FIXTURE_DB=1`, `semantic_fixture_*` schema/database names, and no production-looking DSN.
2. Produce DB-backed evidence for at least:
   - `no_comments` -> gaps/questions,
   - `real_comments` where manifest comments are available -> draft Text-to-SQL context,
   - `synthetic_comments` -> fixture-only exclusion.
3. Expose the Product API through a stable local HTTP adapter for n8n, or document the exact invocation bridge.
4. Import and dry-run n8n workflows only after the above evidence exists.

## Required n8n workflows if proceeding under PARTIAL

1. **DB-backed Onboarding Demo**
   - input: fixture dataset/mode
   - calls scan/profile/build-pack or API adapter
   - displays mode, provenance, and gaps explicitly

2. **Comment-aware Reverse Question Demo**
   - displays no-comment gaps, vague/conflict questions, and real-comment evidence
   - never hides missing metadata behind a generated fallback

3. **Human Confirmation + Pack Promotion**
   - shows review decisions and provenance transition from draft/hypothesis/comment to human-confirmed approved context
   - never auto-promotes synthetic comments

4. **Query Runtime with Baseline vs System SQL Comparison**
   - compares baseline SQL vs semantic-context-guided output without executing unsafe SQL
   - displays `used_context_sources`, `source_status`, and `context_warnings`

5. **Failure-safe Demo**
   - shows missing context, blocked SQL, synthetic-only context, and DB fixture safety failures explicitly

6. **20-domain/fixture Benchmark Runner**
   - runs all available benchmark domains/modes and reports missing evidence as missing, not as pass

## First n8n implementation prompt

```text
Implement n8n Workflow 01 only: DB-backed Onboarding Demo.

Read:
- docs/product/METADATA_PROVENANCE_RULES.md
- docs/demo/N8N_DB_BACKED_DEMO_REQUIREMENTS.md
- reports/productization/n8n_readiness_after_comment_rule_correction.md
- reports/productization/br5_db_fixture_harness_alignment_report.md

Goal:
Create an n8n workflow template that demonstrates fixture-mode onboarding against the local Product API/adapter.

Rules:
- Do not execute production SQL.
- Do not connect to production DBs.
- Do not silently fallback if Postgres fixture env is missing.
- Display no_comments / real_comments / synthetic_comments mode explicitly.
- Display metadata provenance and warnings explicitly.
- Synthetic comments must remain fixture-only.
- If a live DB is unavailable, the workflow must stop with an explicit environment error, not substitute DuckDB/SQLite.

Final output:
- workflow JSON template
- required environment variables
- dry-run instructions
- failure-state examples
```

## Final manager decision

n8n may proceed only as a **PARTIAL / gated demo implementation**, beginning with Workflow 01. It must not be presented as production-ready until live DB-backed evidence and the HTTP adapter/dry-run are complete.
