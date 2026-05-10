# Final PR-0 through PR-7 Production-Readiness Evaluation

Date: 2026-05-10 KST  
Evaluation command intent: `ooo evaluate` final PR-0 through PR-7 production-readiness sequence.  
Final verdict: `PARTIAL`

## Executive verdict

The repo is **locally repeatable and release-packet ready**, but it is not fully production-release ready yet.

Reason: all local/repo evidence, tests, release packet, safety scans, n8n live-smoke evidence, DB fixture/read-only evidence, retrieval evidence, baseline-vs-system SQL evidence, hosted CI pass evidence, and metadata provenance rules are represented. The remaining blocker is external release-governance evidence:

1. signed/promoted release-candidate approval is not attached.

This blocker is intentionally not faked or silently converted into a pass. Hosted CI pass URL is attached in `reports/productization/hosted_ci_evidence.*`.

## Commands run in this final evaluation

```bash
make env-check
make release-test
.venv/bin/python -m pytest -q tests/security tests/packaging tests/e2e tests/product
make ci
make release-pack RELEASE_ID=release-test RELEASE_OUT=reports/release
make release-scan RELEASE_ID=release-test RELEASE_OUT=reports/release
make release-verify RELEASE_ID=release-test RELEASE_OUT=reports/release
.venv/bin/python scripts/release/scan_release_artifacts.py --release-dir reports/release/release-test --json
```

## Mechanical verification results

```text
make env-check
=> environment ok: 3.14.4

make release-test
=> 5 passed

pytest tests/security tests/packaging tests/e2e tests/product
=> 80 passed

make ci
=> make env-check PASS
=> make test: 384 passed, 2 skipped
=> ruff: All checks passed
=> clone-ready setup checks: PASS
=> scripts/setup/env_check.sh: PASS
=> packaging unittest: 10 tests OK
```

## Release packet

Release packet path:

```text
reports/release/release-test
```

Release manifest:

```text
reports/release/release-test/release_manifest.json
```

Manifest summary after regeneration:

```text
status: dry-run
coverage: present=7, partial=1, missing=0
missing tracked source evidence: []
missing gate evidence: PR-7 signed/promoted release candidate approval
n8n: pr6_completed_live_runtime_smoke_present / demo_orchestration_only_not_production
baseline/system SQL evidence entries: 8
```

## Final criteria checklist

| # | Criterion | Result | Evidence |
|---:|---|---|---|
| 1 | Clean clone install path exists | PASS | `docs/setup/DEVELOPMENT.md`, `scripts/setup/clone_ready_setup.py`, `make ci`, packaging tests |
| 2 | Core tests pass or failures are explicit | PASS | `make ci` -> `384 passed, 2 skipped` |
| 3 | Product API is thin and safe | PASS | PR-2 evidence, product tests, route inventory, no execute_query scan |
| 4 | MCP surface is safe and scoped | PASS | PR-3 evidence, MCP tests, no production execute_query tool |
| 5 | DB fixture/read-only evidence exists or missing explicit | PASS | `PR4_DB_FIXTURE_READONLY_EVIDENCE.md`, Postgres/MySQL reality artifacts |
| 6 | `real_db_comment` is product-usable context | PASS | `METADATA_PROVENANCE_RULES.md`, release manifest provenance rules |
| 7 | `no_comment` creates gaps/reverse questions | PASS | release manifest comment-mode rules, metadata provenance docs |
| 8 | synthetic comments are fixture-only | PASS | release manifest `test_only_synthetic_comment`, known limitations |
| 9 | retrieval backend selection is explicit | PASS | PR-5 retrieval evidence, support matrix Weaviate optional evidence-gated |
| 10 | no silent fallback | PASS | risk register, release manifest safety checks, PR-5 evidence |
| 11 | no production `execute_query` | PASS | implementation scan clean; support matrix marks forbidden |
| 12 | raw PII not stored/indexed/logged/released | PASS | release artifact PII/secret scan clean; security tests pass |
| 13 | n8n is orchestration wrapper only | PASS | PR-6 local/live smoke evidence, release manifest n8n status |
| 14 | n8n does not execute SQL directly | PASS | workflow scan clean; n8n support matrix demo-only |
| 15 | baseline SQL vs system SQL represented if implemented | PASS | 8 manifest evidence entries, profile-only/not-executed semantics |
| 16 | release packet exists | PASS | `reports/release/release-test/**` |
| 17 | support matrix is evidence-based | PASS | `support_matrix.md`, structured support levels in manifest |
| 18 | known limitations explicit | PASS | `known_limitations.md`, release summary missing gates |
| 19 | risk register current | PASS | `PRODUCTION_RISK_REGISTER.md`, release packet `risk_register.md` |
| 20 | final readiness classification exists | PASS | this report and `pr7_ci_observability_release_packet.md` |

## Previously discovered issues and resolution status

| Issue | Status | Resolution |
|---|---|---|
| n8n live runtime was previously only template/local smoke | RESOLVED | Docker `n8nio/n8n:2.19.5` live smoke added and evidenced in PR-6 |
| `npx n8n` failed on local Node v25 native dependency install | RESOLVED BY EXPLICIT PATH | Docker live runtime path documented; no silent fallback |
| Release packer failed with `NameError: baseline_system_sql_evidence is not defined` | RESOLVED | Release packer now passes baseline/system SQL evidence into summary/manifest generation; `make release-test` passes |
| Release generated markdown had trailing whitespace | RESOLVED | Release packer strips trailing whitespace for markdown artifacts |
| Manual release safety scans were not codified | RESOLVED | Added `scripts/release/scan_release_artifacts.py`, `make release-scan`, `make release-verify`, release tests, and GitHub Actions release packet scan/upload steps |
| Hosted CI initially failed at `make env-check` | RESOLVED | Root cause: workflow used Makefile default `.venv/bin/python` on GitHub runner. Fix: workflow-level `PYTHON=python` |
| Hosted CI then failed in full test step on unverified Python 3.11 baseline | RESOLVED | Current release evidence is Python 3.14. Fix: GitHub Actions and setup docs now use Python 3.14 as the verified baseline; unverified interpreter fallback is not release evidence |
| Hosted CI full-test step may inherit optional live integration env | RESOLVED | Workflow now forces clone-only/offline gates: `SDC_LLM_ENABLED=0`, `SEMANTIC_WEAVIATE_ENABLED=0`, `SEMANTIC_POSTGRES_ENABLED=0`, `SEMANTIC_MYSQL_ENABLED=0`, `SEMANTIC_CONTEXT_FIXTURE_DB=0` |
| Hosted CI aggregated full-test step remained opaque without authenticated log download | RESOLVED | Workflow now runs suite-level pytest steps and uploads per-suite `reports/ci/*.log` diagnostics with `if: always()` |
| Hosted CI product-suite step failed but log body remained unavailable without artifact auth | RESOLVED | Workflow now splits `tests/product` into file-level pytest steps so the next run identifies the exact failing product contract |
| Hosted CI `test_phase18_evidence_console` failed from untracked local benchmark artifact dependency | RESOLVED | Evidence console now marks missing benchmark artifacts with `per-file score is not invented`; regression test covers missing benchmark root |
| Hosted CI eval-suite step failed but exact eval file was not identified | RESOLVED | Workflow now splits `tests/eval` into file-level pytest steps while preserving fail-fast semantics |
| Hosted CI `test_dataset_manifests` failed from macOS-only decomposed Korean path normalization | RESOLVED | Sinagong eval manifest and eval path assertions are normalized to NFC to match git-index filenames on Linux |
| Hosted CI pass logs absent | RESOLVED | Public GitHub Actions run `25621898578` on commit `3a3a3774b7671c1d29b629746c5b655939791951` is attached in `reports/productization/hosted_ci_evidence.*` |
| Signed/promoted release-candidate approval absent | OPEN BLOCKER | Requires release governance action; not safe to fake locally |

## New issues found in this final evaluation

A locally fixable gap was found and resolved: release artifact/n8n/execute-query safety scans were previously manual `rg` commands, so they have been codified as a fail-closed script and wired into local CI-equivalent and GitHub Actions. No additional locally fixable issue remained after regeneration and verification.

The only remaining issue after this fallback hardening is the release-governance blocker:

1. signed or promoted release candidate approval missing.

## Blocking issues

For production release readiness:

1. **Signed/promoted release-candidate approval missing** — hosted CI now passes, but release promotion approval has not been created or signed. The release packet remains dry-run/local validation only.

## Non-blocking limitations

- PostgreSQL/MySQL support is fixture/read-only metadata validation only, not production SQL execution.
- Weaviate remains optional evidence-gated; explicit backend selection must fail visibly if unavailable.
- n8n is demo orchestration only, never Semantic Pack source of truth.
- Oracle remains unsupported.
- Production `execute_query` remains forbidden.
- No Prometheus/Grafana/Jaeger/OpenTelemetry production observability stack is claimed.

## Final readiness classification

```text
PARTIAL
```

The system has hosted CI pass evidence and is ready for release-candidate approval review, but not for production release claims until signed/promoted approval evidence is attached.

## Next recommended milestone

Create a signed/promoted release-candidate approval artifact, regenerate the release packet, and rerun this final evaluation. Hosted CI pass evidence is already attached via run 25621898578.
