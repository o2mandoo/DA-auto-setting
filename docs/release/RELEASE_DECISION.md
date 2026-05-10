# Release Decision Gate

Date: 2026-05-10 KST  
Candidate base commit: `0eb4ad8`  
Candidate label: `rc-0.1-internal-candidate`
Decision gate commit: current repository `HEAD` after this file is committed  
Production release status: **not approved**

## Decision

- [x] Approve as internal release candidate
- [ ] Hold production release

## Evidence snapshot

| Gate | Status | Evidence |
|---|---|---|
| Local CI-equivalent | PASS | `make ci` |
| Hosted CI | PASS | latest `packaging-clean-clone.yml` run on `main`; verify in GitHub Actions |
| Release packet | PASS / dry-run | `reports/release/release-test/` |
| Release artifact safety scan | PASS | `make release-verify RELEASE_ID=release-test RELEASE_OUT=reports/release` |
| Production `execute_query` | FORBIDDEN | Product boundary docs and release scan |
| Raw PII / secrets in release packet | BLOCKED/REDACTED | Release scan and redaction report |
| Test datasets in git | BLOCKED | `make dataset-guard` |
| Signed/promoted release approval | PRESENT for internal RC | `docs/release/RELEASE_APPROVAL.md` |

## Current known limitations

- This is an internal release-candidate state, not a production release approval.
- PostgreSQL/MySQL support remains fixture/read-only metadata validation only.
- Weaviate remains optional and evidence-gated.
- n8n remains orchestration/demo wrapper only.
- Oracle remains unsupported.
- Production SQL execution remains forbidden.

## Current control decision

Internal RC is approved. Production release remains not approved.

Next work should be limited to the first-user onboarding blocker milestone, and direct product code changes should use team mode with narrow worker lanes.
