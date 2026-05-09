# Production Risk Register

Date: 2026-05-10 KST  
Lane contract: worker-5 task-8 refresh edits only this risk register; no feature/runtime code.

Replacement task note: this file is the replacement correction artifact for failed task-3 / task-6 and remains docs-only.

## Decision context

Chosen v1 target: **clone-ready package + MCP + optional local HTTP adapter**.

This register assumes the system remains validation-first and source-of-truth-driven by Semantic Packs, Registry, and MCP. It does **not** assume production BI/SaaS, runtime SQL execution, mandatory Docker, or mandatory live DB/VDB evidence.

## ADR alternatives considered

Required alternatives considered exactly as tasked: MCP-only, no HTTP adapter; full SaaS/BI/runtime SQL product; Docker-first production app; live DB/VDB mandatory evidence; chosen: clone-ready package + MCP + optional local HTTP adapter.

Risk fields required in every row: severity, likelihood, mitigation, verification evidence, owner lane.

No production `execute_query` is permitted in the v1 target.

| Alternative | Risk posture | Register decision |
|---|---|---|
| MCP-only, no HTTP adapter | Lower web-surface risk, but n8n/local product API smoke remains indirect and harder to operate. | Rejected for v1 because an optional local HTTP adapter is needed for productization demos and n8n integration. |
| Full SaaS/BI/runtime SQL product | High security, tenancy, auth, data-governance, UI, and execution risk. | Rejected for v1; no BI/SaaS and no production `execute_query`. |
| Docker-first production app | Improves reproducibility later, but can hide package/dependency gaps and overstate deploy readiness. | Rejected as the first gate; PR-1 must prove clean clone/venv first. |
| Live DB/VDB mandatory evidence | Stronger integration evidence, but brittle for clone-ready users and easy to confuse missing services with product failure. | Rejected as mandatory; live DB/VDB is optional/env-gated and missing evidence must be explicit. |
| Clone-ready package + MCP + optional local HTTP adapter | Keeps scope narrow while enabling local automation and demos. | Chosen; risks below are gated by PR-1 through PR-7. |

## Severity and likelihood scale

- Severity: Critical, High, Medium, Low.
- Likelihood: High, Medium, Low.
- Risk status: Open, Mitigated-by-gate, Accepted limitation.

## Current evidence refresh — 2026-05-10 KST

This refresh keeps the register current against the repo-local PR-7/release-packet artifacts now present:

- Release-packet scaffolding exists: `.github/workflows/packaging-clean-clone.yml`, `scripts/release/build_release_packet.py`, `tests/release/test_build_release_packet.py`, and `reports/release/release-test/**`. PR-7 remains partial until live CI logs and signed/promoted release-candidate approval are attached.
- PR-1 clean-clone/package evidence is now represented by `reports/productization/PR1_CLEAN_CLONE_EVIDENCE.md`, `reports/productization/PR1_FINAL_VERIFIER_EVIDENCE.md`, and `reports/productization/PR1_PIP_FREEZE.txt`; hidden `/tmp/semantic-data-context-deps` dependency risk is mitigated by gate, not removed as a future regression risk.
- PR-4 and PR-5 evidence packets are present for read-only DB fixtures and explicit retrieval/no-fallback behavior; MySQL remains fixture/demo/read-only only, not production MySQL execution support.
- PR-6 local and live n8n runtime smoke reports exist (`reports/productization/pr6_n8n_local_workflow_smoke.md`, `reports/productization/pr6_n8n_live_runtime_smoke.md`), but release promotion still requires final packet evidence to preserve the limitations distinction.
- No production `execute_query`, BI/SaaS/dashboard claim, production credentials, or silent fallback is permitted by this register.

## Risk register

| ID | Risk | Severity | Likelihood | Mitigation / control | Verification evidence required | Owner lane | Status |
|---|---|---:|---:|---|---|---|---|
| R-01 | Production readiness is overstated from local demo evidence. | High | Medium | Keep release wording at clone-ready/local validation until PR-1..PR-7 evidence is attached. | `reports/productization/PRODUCTION_READINESS_MATRIX.md`; PR-7 release packet with pass/fail evidence and known limitations. | readiness-risk-docs + verifier | Mitigated-by-gate |
| R-02 | Clean clone depends on hidden local dependency cache. | High | Medium | PR-1 requires clean venv install and explicitly forbids relying on `/tmp/semantic-data-context-deps`; keep this as a regression guard for future packaging edits. | `reports/productization/PR1_CLEAN_CLONE_EVIDENCE.md`, `reports/productization/PR1_FINAL_VERIFIER_EVIDENCE.md`, `reports/productization/PR1_PIP_FREEZE.txt`, plus rerun `make env-check`/`make test` in release CI. | package/CI lane | Mitigated-by-gate |
| R-03 | Optional HTTP adapter accidentally owns product logic or bypasses Registry/MCP safety. | High | Medium | Adapter must mount existing handlers only; core validation remains in `semantic_registry` and `semantic_mcp`. | `/healthz`, `/readyz`, OpenAPI, typed errors, correlation ID, adapter tests proving delegated handlers. | HTTP-adapter lane | Open |
| R-04 | An HTTP route or MCP tool exposes production SQL execution. | Critical | Low | Preserve no-production-execution invariant; only validation and local/demo preview allowed. | Registration-surface check, route audit, grep/static scan for product `execute_query`, SQL red-team results with `execution_allowed=false`. | MCP/adapter + verifier | Mitigated-by-gate |
| R-05 | Safe preview is misread as production query execution. | High | Medium | Label preview as local/demo/test only; keep fixture roots explicit and audit output under `runtime/**`. | `tests/mcp/test_preview_query.py`, `tests/registry/test_preview_safety.py`, preview artifact paths, docs showing no production DB connection. | registry/MCP lane | Open |
| R-06 | Silent fallback hides backend/provider/DB failures. | Critical | Medium | Backend/provider/DB selection must fail explicitly; no keyword fallback after selected Weaviate failure, no DB reroute. | Security tests, retrieval tests, DB fixture tests, docs in `docs/setup/user-configuration.md` and `docs/execution/SECURITY_CHECKLIST.md`. | retrieval/DB + verifier | Mitigated-by-gate |
| R-07 | Weaviate live readiness is inferred from fake/deterministic tests. | Medium | Medium | Mark live Weaviate as optional; require explicit pass/skip/failure artifact when env vars are set. | `tests/integration/test_weaviate_live_optional.py`; optional live command output; fake backend test result separately labeled. | retrieval lane | Open |
| R-08 | Raw PII leaks into profiles, retrieval payloads, prompts, runtime artifacts, or reports. | Critical | Low | Keep PII suppression/redaction tests mandatory; reject raw PII feedback/prompts/artifacts. | `tests/security/test_phase12_hardening.py`, builder/profile tests, retrieval payload checks, runtime artifact scan. | security/verifier lane | Mitigated-by-gate |
| R-09 | PostgreSQL support is widened into production DB execution. | Critical | Low | Define PostgreSQL as metadata scan/profile/demo validation only. | PR-4 evidence: scanner/profile tests, no production credentials, explicit fixture schema/env gate. | DB lane | Mitigated-by-gate |
| R-10 | MySQL support is overstated beyond fixture/demo or silently reroutes to another DB. | High | Medium | MySQL remains fixture/demo/read-only even when live fixture evidence exists; no fallback to PostgreSQL/DuckDB/SQLite/cached JSON/synthetic comments. | `reports/productization/PR4_DB_FIXTURE_READONLY_EVIDENCE.md`, `reports/reality/mysql_live_fixture_evidence.json`, `tests/builder/test_mysql_comment_scanner.py`, `tests/fixtures/test_mysql_*`, `tests/e2e/test_mysql_db_fixture_comparison.py`. | DB lane | Mitigated-by-gate |
| R-11 | Oracle support is faked for symmetry. | High | Low | Keep Oracle unsupported until real connector and tests exist; unsupported backends fail visibly. | `docs/dev/DB_FIXTURE_GUIDE.md`, `docs/product/METADATA_PROVENANCE_RULES.md`, adapter/backend unsupported-path tests. | DB lane | Accepted limitation |
| R-12 | n8n workflow duplicates source-of-truth logic or hides failures. | High | Medium | n8n remains orchestration/demo wrapper over Product API; display backend/comment mode/source warnings and failures. | `reports/productization/pr6_n8n_local_workflow_smoke.md`, `reports/productization/pr6_n8n_live_runtime_smoke.md`, `tests/product/test_n8n_workflow_templates.py`, `docs/demo/N8N_WORKFLOW_REQUIREMENTS.md`, `docs/demo/N8N_DB_BACKED_DEMO_REQUIREMENTS.md`; final release packet must preserve partial/live-import limitations. | n8n lane | Open |
| R-13 | MCP stdio launch fails because official SDK is missing, but tests pass through function-level tools. | Medium | Medium | Keep import-time-safe function tests but require explicit SDK smoke for stdio readiness. | `semantic_mcp.server.inspect_registration_surface()` output plus stdio smoke in PR-3 when SDK installed; missing SDK returns explicit error. | MCP lane | Open |
| R-14 | CI is absent or diverges from local verification commands. | High | Medium | PR-7 has local workflow scaffolding, but live CI logs must still be attached before release claims. | `.github/workflows/packaging-clean-clone.yml`, `make env-check`, `make test`, targeted security/packaging/e2e outputs, and external CI URL/log artifacts. | CI/release lane | Open |
| R-15 | Observability is too weak for adapter/API troubleshooting. | Medium | Medium | Add correlation IDs, typed errors, and audit JSONL samples in PR-2/PR-7. | HTTP smoke showing correlation ID in headers/logs; audit record sample; typed error examples. | observability/HTTP lane | Open |
| R-16 | Release packet lacks support-level clarity. | High | Medium | Publish support matrix and known limitations with every release candidate; keep dry-run release packets clearly non-production. | `reports/release/release-test/release_summary.md`, `reports/release/release-test/support_matrix.md`, `reports/release/release-test/known_limitations.md`, readiness matrix, risk register, ADR, release notes, version/tag. | release lane | Mitigated-by-gate |
| R-17 | Product API docs drift from actual Python handlers. | Medium | Medium | Generate or test route inventory against `semantic_registry.product.api.API_ENDPOINTS`. | `docs/api/PRODUCT_API.md`, `docs/api/OPENAPI_LIKE.yaml`, route inventory test or smoke output. | HTTP-adapter/docs lane | Open |
| R-18 | Productization work edits runtime artifacts or feature code outside lane. | Medium | Low | Keep this run docs-only; verifier checks no code feature files changed. | `git diff --name-only` scoped to `reports/productization/PRODUCTION_READINESS_MATRIX.md` and `reports/productization/PRODUCTION_RISK_REGISTER.md`. | readiness-risk-docs + verifier | Mitigated-by-gate |
| R-19 | Full `make test` is too slow/flaky and gets skipped without recording why. | Medium | Medium | Worker/verifier must run it or capture exact blocker; targeted checks are not a substitute for final PR evidence. | `make test` command output or exact impossible reason; targeted tests listed separately. | verifier/CI lane | Open |
| R-20 | Docker-first pressure hides clone-ready package failures. | Medium | Medium | Run PR-1 clean venv before any Docker/devcontainer promotion; Docker can be a later convenience layer. | Clean venv logs; no Docker-only pass claims. | package/release lane | Mitigated-by-gate |
| R-21 | release/supply-chain evidence is incomplete: dependency pins, lock snapshot, artifact provenance, or package integrity are missing. | High | Medium | PR-7 dry-run packet now includes dependency snapshot and manifest; production distribution still needs CI release job output, package integrity/provenance, and promoted release-candidate approval. | `reports/release/release-test/dependency_snapshot.txt`, `reports/release/release-test/release_manifest.json`, package install logs, release tag, artifact checksums/provenance note, CI release job output. | release/CI lane | Open |

## Gate ownership summary

| Gate | Primary owner lane | Risk IDs covered |
|---|---|---|
| PR-1 clean clone package baseline | package/CI lane | R-01, R-02, R-14, R-20 (R-02 mitigated by current PR-1 packet; R-14 remains open until CI logs) |
| PR-2 optional local HTTP adapter | HTTP-adapter/observability lane | R-03, R-04, R-15, R-17 |
| PR-3 MCP + safe runtime | MCP/registry lane | R-04, R-05, R-13 |
| PR-4 DB fixture/read-only evidence | DB lane | R-06, R-09, R-10, R-11 |
| PR-5 retrieval/Weaviate optional evidence | retrieval lane | R-06, R-07, R-08 |
| PR-6 n8n workflow smoke | n8n lane | R-12 (local/live runtime smoke present; release packet must preserve limitations) |
| PR-7 CI/observability/release packet | CI/release/verifier lane | R-01, R-14, R-15, R-16, R-19, R-21 (R-16 mitigated by dry-run packet; CI/approval evidence still open) |

## Minimum verification packet for risk closure

A future risk can be marked closed only when its evidence includes:

1. exact command(s) run,
2. pass/fail/skip output,
3. artifact path(s),
4. explicit unsupported/unavailable reason where applicable,
5. owner lane and date,
6. confirmation that no production `execute_query`, BI/SaaS claim, or silent fallback was introduced.

## Next recommended PR-7 follow-up

```text
$team 3:executor "Execute PR-7 release evidence only for semantic-data-context: attach live CI run logs for setup/test/security/packaging jobs, rerun make release-test, refresh the release packet, and record signed/promoted release-candidate approval or an explicit not-approved blocker. Do not add production execute_query, BI/SaaS/dashboard scope, production credentials, or silent fallback support."
```
