# Known limitations

- PR-1 clean clone package baseline: Clean-venv install log, make env-check output, make test output, dependency snapshot.
- PR-2 optional local HTTP adapter: Adapter smoke output, /healthz and /readyz proof, OpenAPI, typed error payloads.
- PR-3 MCP + safe query runtime hardening: Registration-surface proof and SQL red-team blocking outputs.
- PR-4 DB fixture/read-only evidence: Read-only fixture evidence and explicit live-service unavailable artifacts where relevant.
- PR-5 retrieval/Weaviate optional evidence: Explicit live/skip/failure evidence for selected Weaviate backend.
- PR-6 n8n workflow smoke: Workflow smoke against local APIs and visible backend/comment warnings.
- PR-7 CI, observability, release packet: CI logs, release candidate identifier, dependency snapshot, and signed release packet.

## Explicit constraints
- Release packet is evidence-first; missing evidence is reported, not inferred.
- Oracle remains unsupported unless a real connector and tests exist.
- MySQL stays fixture/demo until live read-only evidence is attached.
