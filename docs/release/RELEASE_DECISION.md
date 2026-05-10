# Release Decision Gate

Date: 2026-05-10 KST  
Candidate base commit: `0eb4ad8`  
Candidate label: `rc-0.1-internal-candidate`
Decision gate commit: current repository `HEAD` after this file is committed  
Production release status: **not approved**

## Decision

- [ ] Approve as internal release candidate
- [x] Hold production release

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
| Signed/promoted release approval | MISSING | Must be created by release owner |

## Current known limitations

- This is an internal release-candidate state, not a production release approval.
- Signed or promoted release-candidate approval is still missing.
- PostgreSQL/MySQL support remains fixture/read-only metadata validation only.
- Weaviate remains optional and evidence-gated.
- n8n remains orchestration/demo wrapper only.
- Oracle remains unsupported.
- Production SQL execution remains forbidden.

## Required next decision

A release owner must explicitly choose one of the following:

1. **Approve internal RC**: create signed/promoted approval evidence and regenerate the release packet.
2. **Hold**: record the reason and open a scoped blocker milestone.

No new product feature work should start until this decision is recorded.
