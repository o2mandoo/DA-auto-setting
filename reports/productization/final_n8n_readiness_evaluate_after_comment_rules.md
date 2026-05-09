# Final Evaluation — n8n Readiness After Corrected Comment Business Rules

## Result

**PARTIAL**

## Pass/fail checklist

| READY criterion | Result | Notes |
|---|---|---|
| Real DB comments are scanned and used as semantic context. | PASS | Scanner/model/retrieval tests cover `real_db_comment`; live DB run still pending. |
| `no_comment` gaps become reverse-question inputs. | PASS | Gap detector and reverse-question tests cover abstract/no-comment cases. |
| Synthetic comments are fixture-only. | PASS | Marker detection and fixture/search exclusion tests cover this. |
| Text-to-SQL retrieval uses allowed context sources. | PASS | Search excludes unusable provenance; planner exposes context source. |
| Runtime discloses used context sources. | PASS | Runtime/Product API response models include provenance fields. |
| DB-backed tests cover `no_comments` and at least one comment-present mode. | PARTIAL | Code-level fixture/E2E comparison covers modes; live Postgres fixture execution was not claimed. |
| Baseline vs system comparison can show context differences. | PARTIAL | Comparison dimensions exist; no live n8n visualization for DB-comment modes yet. |
| Failure-safe states are visible. | PASS | No-silent-fallback fixture safety and existing failure-safe surfaces are documented/tested. |
| n8n requirements are defined. | PASS | `docs/demo/N8N_DB_BACKED_DEMO_REQUIREMENTS.md` created. |
| No n8n workflow has been prematurely created. | PASS for this phase | No new workflow JSON was created in this BR-0~BR-5/n8n-readiness pass. Pre-existing Phase 20 workflow templates remain unchanged. |

## Blockers to READY

1. Execute live Postgres fixture load/scan/profile/build-pack under `SEMANTIC_CONTEXT_FIXTURE_DB=1`.
2. Record live evidence for no-comment gaps and at least one comment-present mode.
3. Add or confirm local HTTP adapter for Product API invocation from n8n.
4. Make existing/next n8n workflows DB-comment-mode-aware only after live evidence exists.

## Required fixes before production-facing n8n

- Do not use synthetic comments to compensate for missing real comments.
- Do not mark comment-only context as approved semantic truth.
- Do not hide fixture/DB environment errors behind alternate local backends.
- Show provenance and warnings in every answer/query workflow.

## First workflow recommendation

Start with **Workflow 01 — DB-backed Onboarding Demo** under the prompt in `reports/productization/n8n_readiness_after_comment_rule_correction.md`. It should be implemented as a gated demo template and must stop visibly if the fixture DB environment is not configured.
