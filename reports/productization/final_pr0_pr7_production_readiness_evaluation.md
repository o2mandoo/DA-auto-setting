# Final PR-0 through PR-7 Production-Readiness Evaluation

Date: 2026-05-10 KST  
Evaluation command intent: `ooo evaluate` final PR-0 through PR-7 production-readiness sequence.  
Final verdict: `PARTIAL`

## Executive verdict

The repo is **locally repeatable and release-packet ready**, but it is not fully production-release ready yet.

Reason: all local/repo evidence, tests, release packet, safety scans, n8n live-smoke evidence, DB fixture/read-only evidence, retrieval evidence, baseline-vs-system SQL evidence, and metadata provenance rules are represented. The remaining blockers are external release-governance evidence:

1. hosted CI run URL/logs are not attached;
2. signed/promoted release-candidate approval is not attached.

These blockers are intentionally not faked or silently converted into a pass.

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
missing gate evidence: PR-7 live CI run log; signed/promoted release candidate approval
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
| Hosted CI initially failed at `make env-check` | RESOLVED / RERUN REQUIRED | Root cause: workflow used Makefile default `.venv/bin/python` on GitHub runner. Fix: workflow-level `PYTHON=python`; rerun evidence must be attached after push |
| External CI pass logs absent | OPEN BLOCKER | Must be produced by hosted CI rerun; not safe to fake locally |
| Signed/promoted release-candidate approval absent | OPEN BLOCKER | Requires release governance action; not safe to fake locally |

## New issues found in this final evaluation

A locally fixable gap was found and resolved: release artifact/n8n/execute-query safety scans were previously manual `rg` commands, so they have been codified as a fail-closed script and wired into local CI-equivalent and GitHub Actions. No additional locally fixable issue remained after regeneration and verification.

The only remaining issues after this fallback hardening are the external production-release blockers:

1. hosted CI pass log/URL still pending after workflow fix;
2. signed or promoted release candidate approval missing.

## Blocking issues

For production release readiness:

1. **Hosted CI pass evidence pending** — local `make ci` passed and the first hosted run exposed/fixed a workflow interpreter issue, but a passing hosted CI log/URL still must be attached.
2. **Signed/promoted release-candidate approval missing** — the release packet is dry-run/local validation only.

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

The system is ready for an external release-candidate verification pass, but not for production release claims until CI and approval evidence are attached.

## Next recommended milestone

Run the GitHub/hosted CI pipeline against the workflow-interpreter fix, attach the passing CI run URL/logs to the release packet, then create a signed/promoted release-candidate approval artifact. After that, regenerate the release packet and rerun this final evaluation.
