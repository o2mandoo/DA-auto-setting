# Release Packet: release-worker1-20260509T140254Z

- generated_at: 2026-05-09T14:02:54.876911+00:00
- git_commit: 6162a2a36e54ccdab52d053b0e1d368e0d08ecae
- status: dry-run release packet

## Evidence snapshot

- Production readiness matrix included.
- Risk register included.
- Known limitations included.
- Support matrix included.
- Secret-like and PII-like values are redacted before writing packet files.

## Missing evidence

- none

## Missing gate evidence

- PR-1 clean clone package baseline: Clean-venv install log, make env-check output, make test output, dependency snapshot.
- PR-2 optional local HTTP adapter: Adapter smoke output, /healthz and /readyz proof, OpenAPI, typed error payloads.
- PR-3 MCP + safe query runtime hardening: Registration-surface proof and SQL red-team blocking outputs.
- PR-4 DB fixture/read-only evidence: Read-only fixture evidence and explicit live-service unavailable artifacts where relevant.
- PR-5 retrieval/Weaviate optional evidence: Explicit live/skip/failure evidence for selected Weaviate backend.
- PR-6 n8n workflow smoke: Workflow smoke against local APIs and visible backend/comment warnings.
- PR-7 CI, observability, release packet: CI logs, release candidate identifier, dependency snapshot, and signed release packet.

## Redaction summary

- worker_id: 3
