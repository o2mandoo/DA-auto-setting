# PR-0..PR-5 Gap Audit

Generated: 2026-05-09T14:34:22.374333+00:00
Team: audit-pr-0-through-pr-63d0350b
Worker: worker-6

## Audit summary

PR-0 through PR-5 are audit-supported PASS for local/productization evidence; PR-6 may start only as a constrained imported-workflow smoke/evidence lane and must not claim production readiness.

Task 15 is terminal, so this consolidation incorporates Tasks 1-15. The artifact is report-only: no product code was modified.

## Per-PR status

| PR | Status | Evidence basis | Remaining gap / repair prompt |
|---|---|---|---|
| PR-0 | PASS | `docs/product/PRODUCTION_MODE_ADR.md`<br>`reports/productization/PRODUCTION_READINESS_MATRIX.md`<br>`reports/productization/PRODUCTION_RISK_REGISTER.md`<br>`reports/phases/productization_phase0.md`<br>`Task 8 PR-claims audit` | Keep production-boundary language conservative; do not convert dry-run/local validation evidence into production-readiness claims. |
| PR-1 | PASS | `reports/productization/PR1_CLEAN_CLONE_EVIDENCE.md`<br>`reports/productization/PR1_FINAL_VERIFIER_EVIDENCE.md`<br>`reports/productization/PR1_PIP_FREEZE.txt` | Keep clean-clone evidence attached to exact command output and dependency snapshot rather than implied setup success. |
| PR-2 | PASS | `reports/productization/PR2_HTTP_ADAPTER_EVIDENCE.md`<br>`docs/api/PRODUCT_API.md`<br>`docs/api/OPENAPI_LIKE.yaml`<br>`tests/product/test_pr2_http_adapter.py`<br>`tests/product/test_pr2_http_docs.py` | When adding adapter evidence, prove no execute_query route/handler and keep correlation/audit evidence local unless live service logs are attached. |
| PR-3 | PASS | `reports/productization/PR3_MCP_SAFE_RUNTIME_EVIDENCE.md`<br>`packages/semantic_mcp/src/semantic_mcp/server.py`<br>`tests/mcp/test_preview_query.py`<br>`tests/eval/test_mcp_eval_integration.py`<br>`tests/security/test_phase12_scope.py` | Keep MCP registration evidence explicit: metadata/planning/validation/preview only, no execute_query tool. |
| PR-4 | PASS | `reports/productization/PR4_DB_FIXTURE_READONLY_EVIDENCE.md`<br>`reports/reality/postgres_live_fixture_evidence.json`<br>`reports/reality/mysql_live_fixture_evidence.json`<br>`tests/fixtures/test_db_fixture_comment_modes.py`<br>`tests/builder/test_db_comment_metadata_gaps.py`<br>`tests/contracts/test_metadata_provenance.py` | Keep real_db_comment/no_comment/synthetic_comment provenance visible through cards/retrieval/runtime/API; never promote synthetic comments as approved truth. |
| PR-5 | PASS | `reports/productization/PR5_PRECHECK_DB_CORPUS_EVIDENCE.md`<br>`reports/productization/PR5_SEMANTIC_RETRIEVAL_EVIDENCE.md`<br>`tests/registry/test_vdb_backend.py`<br>`tests/mcp/test_search_context.py`<br>`reports/reality/sinagong_20_live_db_fixture_evidence.json` | Preserve explicit backend status, fallback_used=false evidence, and raw-PII blocking in any retrieval claim. |
| PR-6 | PARTIAL | `reports/productization/phase20_n8n_readiness_report.md`<br>`reports/productization/final_n8n_readiness_evaluate_after_comment_rules.md`<br>`reports/productization/n8n_workflow_templates.md`<br>`tests/product/test_n8n_workflow_templates.py`<br>`Task 14 n8n source-of-truth audit`<br>`Task 15 failure-safe visibility audit` | Missing tests: Imported n8n workflow runtime smoke against the local HTTP/product API adapter.; Failure-path smoke showing visible backend/comment/warning fields in a live imported workflow run. Missing evidence: Live imported n8n workflow smoke output. Before promoting PR-6, run/import the n8n templates against the local adapter and attach visible failure-state output; do not make n8n source of truth. |

## Missing tests

- PR-6 imported n8n workflow smoke against the local adapter/API.
- PR-6 live failure-path evidence that backend/comment-mode/source-status/warnings remain visible in the imported workflow UI/output.
- PR-7 live CI logs and signed/promoted release-candidate approval are outside PR-0..PR-5 but still gate release claims.

## Missing evidence

- Live imported n8n workflow smoke output remains absent.
- Live CI run log remains absent for release claims.
- Signed/promoted release-candidate approval remains absent.

## Risky claims

- Release summaries can say missing evidence is none while missing gate evidence still lists PR-6/PR-7 external evidence; this must stay explicit.
- PR-6 may start only as an evidence-collection/smoke lane, not as a production-readiness or source-of-truth promotion.
- No production execute_query is a hard product boundary, not a temporary missing feature.
- Optional DB/VDB support must stay explicit and no-fallback; unsupported Oracle must not be faked.

## Product-rule inconsistencies / required repairs

### PR evidence claims must match current repo evidence.
- Finding: Task 8 found stale PR-7 wording after a tracked dry-run release packet existed; release summaries still need careful distinction between missing source files and missing external/live gate evidence.
- Required repair: Use missing_gate_evidence wording whenever external/live evidence is absent, even if source files exist.

### n8n is orchestration/demo only, not source of truth.
- Finding: Task 14 confirms source-of-truth remains Registry/Product API; Task 15 notes imported runtime smoke is still missing.
- Required repair: Keep n8n claims at template/readiness level until imported workflow smoke evidence exists.

### No production execute_query.
- Finding: Task 13 confirms code/docs/tests preserve no production execute_query; comparison and preview surfaces are non-executing/local.
- Required repair: Block any future route/tool/handler named execute_query unless it is explicitly test-only proof that production execution remains absent.

### No unauthorized product-code repairs in audit-only lanes.
- Finding: Leader correction records tmux pane fallback launch context, worker-1/worker-3 unauthorized product-code edits, worker-3 native subagents, and worker-6 premature Task 16 completion without durable artifacts as process deviations. These are audit findings, not product fixes.
- Required repair: Treat these as audit/process findings, not implemented fixes; merge only scoped report artifacts from this lane.

## Recommended repair prompts

- PR-6 smoke: Import the n8n templates against the local adapter, capture success and failure outputs, and verify backend/comment/source-status/warnings are visible without duplicating Registry logic.
- Release claim hygiene: Update generated release summaries so missing source files and missing external/live gate evidence cannot be read as contradictory.
- Process hygiene: Exclude unauthorized product-code edits from audit-only worker lanes; require report-only commits for consolidation tasks.
- Evidence hygiene: Attach exact command output for release-test, n8n workflow smoke, and CI logs before upgrading any PARTIAL gate to PASS.

## May PR-6 start?

**Yes, with gates.** PR-6 may start only as an n8n/local workflow smoke and evidence-collection lane. It must not claim production readiness, n8n source-of-truth ownership, production `execute_query`, or silent fallback support. Promotion remains blocked until live imported workflow smoke and visible failure-state evidence are attached.

## Process-deviation notes

- Leader correction: tmux pane fallback launch occurred during team orchestration and should be treated as process context, not product evidence.
- Leader correction: worker-1 and worker-3 unauthorized product-code edits must not be merged from audit-only lanes; treat them as audit/process issues, not implemented fixes.
- Leader correction: worker-3 native subagents are process-deviation evidence for the audit lane and should not expand the product-code scope.
- Worker-6 process correction: premature Task 16 completion happened before artifacts were present after Task 15 terminal; this Task 17 repair writes only the two requested report files.

## Source task terminal status

| Task | Status | Owner | Subject |
|---|---|---|---|
| 1 | completed | worker-1 | real DB comments are product-usable context. |
| 2 | completed | worker-2 | no-comment DBs produce metadata gaps/reverse questions. |
| 3 | completed | worker-1 | synthetic comments are fixture-only. |
| 4 | completed | worker-3 | provenance/status is preserved into cards/retrieval/runtime/API. |
| 5 | completed | worker-4 | baseline SQL is never executed. |
| 6 | completed | worker-4 | system SQL uses Semantic Pack context. |
| 7 | completed | worker-5 | SQL comparison explains differences. |
| 8 | completed | worker-6 | PR claims match evidence. |
| 9 | completed | worker-2 | MySQL/Weaviate optional support is not faked. |
| 10 | completed | worker-3 | Oracle unsupported. |
| 11 | completed | worker-2 | raw PII is not stored/indexed/logged. |
| 12 | completed | worker-5 | no silent fallback. |
| 13 | completed | worker-6 | no production execute_query. |
| 14 | completed | worker-2 | n8n has not become source of truth. |
| 15 | completed | worker-1 | failure-safe states are visible.  Final report: - audit summary - per-PR status  |
