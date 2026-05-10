# PR-7 CI, Observability, Release Packet Evidence

Date: 2026-05-10 KST  
Status: PASS for local repeatable release-readiness evidence; PARTIAL for production release readiness.  
Readiness classification: `PARTIAL_WITH_ACCEPTED_LIMITATIONS`

## Scope

PR-7 creates and verifies a repeatable, externally reviewable release-readiness packet. It does not add new product features and it does not change the product boundary:

- no production `execute_query`;
- no BI/SaaS/dashboard claim;
- no silent fallback;
- no raw PII/secrets/DSNs in release artifacts;
- Oracle remains unsupported;
- PostgreSQL/MySQL remain read-only fixture/demo metadata validation only;
- n8n remains orchestration/demo wrapper only.

## Team execution evidence

OMX team run:

```text
team: execute-pr-7-ci-obser-550fd840
workers: 6
tasks: 15 total, 15 completed, 0 failed
shutdown: complete
```

Operational notes:

- Initial direct `omx team 6:executor` launch failed with `no space for new pane` in the attached tmux window.
- This was not hidden: a larger dedicated tmux session (`pr7_launch`) was created, the same 6-worker team was started there, and shutdown was verified.
- Worker-6 initially required one explicit manual submit because it had not ACKed; the intervention was visible and worker-6 later completed tasks 9 and 14.
- A leader-to-worker-4 dispatch used a runtime fallback (`hook_timeout_fallback_confirmed:tmux_send_keys_sent`) to resolve a lifecycle transition issue; this is recorded as explicit operational fallback, not silent behavior.

## Changed evidence surfaces

Key changed/added files:

- `.github/workflows/packaging-clean-clone.yml` already existed and is now covered by packaging regression tests.
- `Makefile` exposes `test`, `lint`, `ci`, `release-pack`, `release-test`, `release-scan`, `release-verify`, and `n8n-live-smoke`.
- `docs/observability/OBSERVABILITY_SAMPLES.md`
- `docs/observability/product_api_audit_sample.jsonl`
- `reports/productization/PRODUCTION_READINESS_MATRIX.md`
- `reports/productization/PRODUCTION_RISK_REGISTER.md`
- `reports/productization/pr7_ci_observability_release_packet.md`
- `reports/release/release-test/release_manifest.json`
- `reports/release/release-test/release_summary.md`
- `reports/release/release-test/support_matrix.md`
- `reports/release/release-test/known_limitations.md`
- `scripts/release/build_release_packet.py`
- `scripts/release/scan_release_artifacts.py`
- `tests/packaging/test_entrypoints.py`
- `tests/product/test_observability_samples.py`
- `tests/release/test_build_release_packet.py`
- `tests/release/test_scan_release_artifacts.py`

## Release command and packet path

Release command:

```bash
make release-pack RELEASE_ID=release-test RELEASE_OUT=reports/release
```

Release packet path:

```text
reports/release/release-test
```

Release candidate ID:

```text
release-test
```

Manifest:

```text
reports/release/release-test/release_manifest.json
```

Human-readable summary:

```text
reports/release/release-test/release_summary.md
```

## Verification commands run

```bash
make env-check
make release-test
.venv/bin/python -m pytest -q tests/security tests/packaging tests/e2e tests/product
make test
make ci
make release-pack RELEASE_ID=release-test RELEASE_OUT=reports/release
make release-scan RELEASE_ID=release-test RELEASE_OUT=reports/release
make release-verify RELEASE_ID=release-test RELEASE_OUT=reports/release
.venv/bin/python scripts/release/scan_release_artifacts.py --release-dir reports/release/release-test --json
```

## Test results

```text
make env-check
=> environment ok: 3.14.4

make release-test
=> 5 passed

.venv/bin/python -m pytest -q tests/security tests/packaging tests/e2e tests/product
=> 80 passed

make test
=> 386 passed, 2 skipped

make ci
=> make env-check PASS
=> make test: 384 passed, 2 skipped
=> ruff: All checks passed
=> clone-ready setup checks: PASS
=> scripts/setup/env_check.sh: PASS
=> packaging unittest: 10 tests OK
```

Earlier failure and fix:

```text
make release-test initially failed with NameError: baseline_system_sql_evidence is not defined.
Fix: pass baseline_system_sql_evidence into release summary/manifest generation and regenerate the release packet.
Reverification: make release-test => 5 passed.
```

## CI status

CI-equivalent local command exists and passed:

```bash
make ci
```

The CI-equivalent command now includes release packet generation and the fail-closed release scan through `release-verify`. The GitHub Actions workflow also generates `ci-smoke`, scans it, and uploads it as an artifact. A first hosted CI run was triggered after pushing commit `05c6e93`; it failed at `make env-check` because the GitHub runner uses `python` while the repo Makefile defaults to `.venv/bin/python`. This was a real workflow bug, not hidden as a warning. The workflow now sets `PYTHON=python` at workflow scope so hosted CI uses the runner-installed interpreter while local development can keep the `.venv` default.

A second hosted CI run was triggered after pushing commit `8f1f3fa`; it passed `make env-check` and then failed in the full test step. Because the current verified local evidence is Python 3.14 and there is no attached passing Python 3.11 evidence, the workflow and setup docs now use Python 3.14 as the explicit verified baseline instead of silently treating Python 3.11 as supported release evidence.

A third hosted CI run after commit `b357f88` still failed in the full test step. Public GitHub job metadata did not expose the private step log body, but the workflow previously did not force optional live integrations off. To avoid environment-variable leakage from repository/organization configuration and to keep CI clone-only, the workflow now explicitly sets `SDC_LLM_ENABLED=0`, `SEMANTIC_WEAVIATE_ENABLED=0`, `SEMANTIC_POSTGRES_ENABLED=0`, `SEMANTIC_MYSQL_ENABLED=0`, and `SEMANTIC_CONTEXT_FIXTURE_DB=0`.

A fourth hosted CI run after commit `9b6a87b` still failed in the single aggregated full-test step. Because unauthenticated GitHub metadata only exposed the failing step name and not the private step log body, the workflow now runs the same test tree as explicit suite-level pytest steps and uploads per-suite diagnostic logs.

A fifth hosted CI run after commit `3fc6acf` narrowed the failure to the `tests/product` suite. The workflow now splits product tests by file so the next hosted run identifies the exact product contract file if the failure persists.

A sixth hosted CI run after commit `641886a` narrowed the failure to `tests/product/test_phase18_evidence_console.py`. Root cause: the evidence-console assertion depended on an untracked local aggregate benchmark artifact, so clean hosted CI saw a missing benchmark artifact and the test did not prove the “do not invent per-file scores” rule. Fix: missing benchmark artifacts now carry the same explicit “per-file score is not invented” note, and a regression test covers a missing benchmark root. This preserves fail-closed evidence behavior instead of silently treating missing benchmark data as pass evidence.

A seventh hosted CI run after commit `279f6b2` passed product tests and narrowed the next failure to the `tests/eval` suite. The workflow now splits eval tests by file so the next hosted run identifies the exact eval contract if the failure persists.

An eighth hosted CI run after commit `491f4db` narrowed the failure to `tests/eval/test_dataset_manifests.py`. Root cause: the Sinagong manifest and eval assertions contained decomposed Korean path strings that passed on the local macOS filesystem but did not match the NFC filenames committed to git on Linux. Fix: normalize the Sinagong eval manifest and eval path assertions to NFC, and verify manifest paths against the git index. This is a cross-platform path correction, not a silent file fallback. The rerun passed as hosted CI run `25621898578`, and the release manifest now treats hosted CI as attached evidence rather than a missing gate.

## Observability samples

Observability evidence now includes:

- `docs/observability/OBSERVABILITY_SAMPLES.md`
- `docs/observability/product_api_audit_sample.jsonl`
- `tests/product/test_observability_samples.py`
- Product/API evidence in `reports/productization/PR2_HTTP_ADAPTER_EVIDENCE.md`
- PR-6 live n8n audit evidence in `reports/productization/pr6_n8n_live_runtime_smoke.md`

The sample JSONL includes:

- `correlation_id`
- route/method/status fields
- structured error payload for validation failure
- `execution_allowed: false`
- no raw PII, secrets, or DSNs

No Prometheus/Grafana/Jaeger/OpenTelemetry production stack is claimed.

## Support matrix summary

The release packet includes both matrix-derived and structured support levels:

| Surface | Release status |
|---|---|
| Semantic Pack contracts | supported local validation |
| Local Registry + MCP | supported local validation |
| HTTP adapter | partial local adapter |
| PostgreSQL | fixture/read-only metadata validation |
| MySQL | fixture/read-only metadata validation |
| Weaviate | optional evidence-gated backend |
| n8n | demo orchestration only |
| Oracle | unsupported |
| Production `execute_query` | forbidden |

## Known limitations

Explicit limitations are included in `reports/release/release-test/known_limitations.md`:

- release status is dry-run/local validation, not production-ready;
- production SQL execution is forbidden;
- live external services are optional/evidence-gated;
- Oracle is unsupported;
- synthetic comments are fixture-only;
- n8n remains demo orchestration only;
- hosted CI pass evidence is attached; signed/promoted release-candidate approval remains missing.

## Missing evidence

`release_manifest.json` reports:

```json
[
  {
    "gate": "PR-7 CI, observability, release packet",
    "status": "partial",
    "evidence_needed": "missing external/live evidence: signed or promoted release candidate approval"
  }
]
```

There is no missing tracked source evidence in the generated packet.

## Safety checks

The manual `rg` release-scan fallback has been replaced by the CI-safe fail-closed command `scripts/release/scan_release_artifacts.py` / `make release-scan`. It returned no hits for:

- raw PII-like emails in release artifacts;
- secret/API-key/bearer-token patterns in release artifacts;
- production-looking DSNs in release artifacts;
- direct SQL connector nodes or credentials in n8n workflow JSON;
- production `execute_query` implementation/route surface.

Release manifest safety claims:

```text
no_production_execute_query_claim: true
no_silent_fallback_claim: true
no_raw_pii_claim: true
dependency_snapshot_present: true
```

## Baseline vs system SQL evidence

The release manifest includes baseline/system SQL comparison evidence with `profile_only_not_executed` semantics, including:

- `reports/productization/phase15_sql_comparison_engine.md`
- `docs/product/BASELINE_COMPARISON_SPEC.md`
- `docs/product/PRODUCT_MODES.md`
- `docs/api/examples/compare_sql_request.json`
- `packages/semantic_registry/semantic_registry/product/comparison.py`
- `reports/reality/db_fixture_comment_mode_comparison.json`
- `reports/reality/db_fixture_comment_mode_comparison_with_real_comments.json`

## Comment provenance rule evidence

The release manifest and summaries preserve these distinctions:

- `real_db_comment`: product-usable semantic context only with provenance/status;
- `no_comment`: metadata gap and reverse-question trigger;
- `test_only_synthetic_comment`: fixture-only, never product truth automatically;
- `sidecar_metadata`, `llm_hypothesis`, `human_confirmed`, and `verified_query` remain status-aware.

## Blockers

No local PR-7 blocker remains after the release-packer bug fix and re-verification.

External production-release blockers remain:

1. signed/promoted release-candidate approval is not attached.

## Readiness classification

```text
PARTIAL_WITH_ACCEPTED_LIMITATIONS
```

Reason: local CI-equivalent verification, release packet, safety scans, observability samples, n8n live smoke evidence, DB fixture evidence, retrieval evidence, baseline/system SQL comparison evidence, and comment provenance rules are represented. Production release readiness is still partial until signed/promoted release-candidate approval is attached.
