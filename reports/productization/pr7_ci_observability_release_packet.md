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
- `Makefile` exposes `test`, `lint`, `ci`, `release-pack`, `release-test`, and `n8n-live-smoke`.
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
- `tests/packaging/test_entrypoints.py`
- `tests/product/test_observability_samples.py`
- `tests/release/test_build_release_packet.py`

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
rg -n --hidden -i "sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|password@|client_secret|Bearer [A-Za-z0-9._~+/=-]+|postgres://|mysql://|/Users/|worker-[0-9]+|leader-fixed|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}" reports/release/release-test
rg -n -i "postgres://|mysql://|mongodb://|password|secret|token|api_key|apikey|authorization|bearer |n8n-nodes-base\.(postgres|mysql|mssql|sqlite|mariadb|oracledb|snowflake)" n8n/workflows
rg -n "def execute_query|execute_query\(|/api/execute_query" packages scripts n8n tests
```

## Test results

```text
make env-check
=> environment ok: 3.14.4

make release-test
=> 3 passed

.venv/bin/python -m pytest -q tests/security tests/packaging tests/e2e tests/product
=> 80 passed

make test
=> 384 passed, 2 skipped

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
Reverification: make release-test => 3 passed.
```

## CI status

CI-equivalent local command exists and passed:

```bash
make ci
```

External hosted CI run logs are not attached in this local environment. The release manifest lists this as missing gate evidence instead of treating it as a pass.

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
- external CI logs and signed/promoted release-candidate approval remain missing.

## Missing evidence

`release_manifest.json` reports:

```json
[
  {
    "gate": "PR-7 CI, observability, release packet",
    "status": "partial",
    "evidence_needed": "missing external/live evidence: live CI run log, signed or promoted release candidate approval"
  }
]
```

There is no missing tracked source evidence in the generated packet.

## Safety checks

Static/release scans returned no hits for:

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

1. hosted CI run URL/logs are not attached;
2. signed/promoted release-candidate approval is not attached.

## Readiness classification

```text
PARTIAL_WITH_ACCEPTED_LIMITATIONS
```

Reason: local CI-equivalent verification, release packet, safety scans, observability samples, n8n live smoke evidence, DB fixture evidence, retrieval evidence, baseline/system SQL comparison evidence, and comment provenance rules are represented. Production release readiness is still partial until external CI logs and signed/promoted release-candidate approval are attached.
