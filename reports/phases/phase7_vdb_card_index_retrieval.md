# Phase 7 — Weaviate / Card Index / Retrieval Layer Verification

**Verifier:** worker-5  
**Final status:** PASS for Phase 7 code/acceptance checks in the current filesystem snapshot.  
**Timestamp:** 2026-05-09 00:02 KST

## Verdict

Phase 7 retrieval is now verified: card flattening, deterministic embeddings, keyword backend, explicit Weaviate error behavior, MCP structured search results, PII safety, and forbidden-surface checks pass with fresh evidence.

**Phase 8 may start after the leader records normal team lifecycle/bookkeeping.** Code-level acceptance is green; some worker task files may still be non-terminal until the leader/workers complete orchestration cleanup.

## Verification environment

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=/tmp/semantic-data-context-deps:packages/semantic_contracts:packages/semantic_registry:packages/semantic_mcp/src:packages/semantic_builder/src
```

No dependencies were vendored into the repo. The `/tmp/semantic-data-context-deps` path follows the repository verification convention.

## Tests and checks run

| Check | Command | Result | Evidence |
| --- | --- | --- | --- |
| Contracts | `python3 -m unittest discover -s tests/contracts -v` | PASS, 20 tests | `runtime/phase7_verifier/unittest_contracts_final.log` |
| Registry suite | `python3 -m unittest discover -s tests/registry -v` | PASS, 53 tests | `runtime/phase7_verifier/unittest_registry_stop_hook_latest.log` |
| MCP suite | `python3 -m unittest discover -s tests/mcp -v` | PASS, 22 tests | `runtime/phase7_verifier/unittest_mcp_stop_hook_latest.log` |
| Phase 7 targeted | `python3 -m unittest tests.registry.test_card_flattening tests.registry.test_embedding_provider tests.registry.test_vdb_backend tests.mcp.test_search_context -v` | PASS, 18 tests | `runtime/phase7_verifier/unittest_phase7_targeted_stop_hook_latest.log` |
| Compile/static syntax | `python3 -m compileall packages/semantic_registry packages/semantic_mcp/src packages/semantic_contracts -q` | PASS | `runtime/phase7_verifier/compileall_final.log` |
| Forbidden surface scan | grep for `execute_query`, `preview_query`, UI frameworks, SaaS/network defaults, LanceDB | PASS for package implementation; docs-only roadmap hits | `runtime/phase7_verifier/forbidden_surface_scan_final.log` |

## Backend behavior

### Keyword backend

PASS. `KeywordSearchBackend` indexes Semantic Pack card documents and supports required filters. Registry tests confirm:

- text search works;
- metadata values are not accidentally searched as text;
- `pack_id`, `space_id`, `card_type`, `status`, and role filters are supported;
- pack indexing works through `index_pack(pack)`.

### Weaviate backend

PASS for Phase 7 seam behavior. The Weaviate backend is explicit and does **not** silently fall back to keyword:

- `search_semantic_context(..., backend="weaviate")` without config returns `backend_configuration_error` and empty results.
- Direct `WeaviateSearchBackend()` without collection/client raises `WeaviateUnavailableError` with “keyword fallback is not performed.”
- Offline fake-collection tests pass without requiring network or a running Weaviate service.

### Embedding provider

PASS. Deterministic embeddings are stable/offline and raw PII-like strings are rejected before embedding. Optional local embeddings are behind explicit config and missing dependency/model errors are explicit.

## Retrieval examples / acceptance probes

Evidence: `runtime/phase7_verifier/edge_retrieval_final.json` and `runtime/phase7_verifier/synthetic_ambiguity_probe_final.json`.

| Case | Status | Evidence summary |
| --- | --- | --- |
| `신규 고객 순매출` retrieves `term.new_customer` and `metric.net_revenue` | PASS | MCP keyword results include both `term.new_customer` and `metric.net_revenue`, plus verified query. |
| `휴면 고객` retrieves `users.status = S` if present | DOCUMENTED FIXTURE LIMITATION | Approved demo pack has no `users.status` value dictionary; probe returns nearby customer/new-customer cards. No raw PII issue observed. |
| `email` does not expose raw email values | PASS | `raw_email_hits_in_documents=[]`; MCP email results expose safe column/policy metadata only, no email literal. |
| Draft metric retrieved with draft warning | PASS | `metric.net_revenue` result has `status=draft` and `warnings=["draft_card"]`. |
| Ambiguous revenue / ambiguity rule | PASS with synthetic minimal fixture | Approved pack has reverse questions but no `ambiguity_rules`; synthetic probe adds `ambiguity.new_customer.period_basis` and keyword backend retrieves it first. |
| `backend=weaviate` without dependency/config | PASS | Structured explicit `backend_configuration_error`; no keyword fallback results. |
| Metadata filter `card_type=metric` only returns metrics | PASS | MCP `metric_filter` result set contains only `metric.net_revenue`. |
| Deprecated cards excluded/marked according to config | NOT APPLICABLE IN FIXTURE | No deprecated cards were found in the approved demo pack during verification. |

## PII index safety

PASS with current evidence:

- Contract tests confirm PII candidates (`users.email`, `users.phone`, `users.name`) are policy-blocked and absent from value dictionaries.
- Card flattening tests confirm synthetic unsafe email dictionary values are not indexed in text or metadata.
- Embedding tests reject raw email/phone-like strings before vectorization.
- `SearchDocument` rejects raw PII-like text/metadata and raw-value payload keys.
- Final retrieval probe found no raw email literals in indexed documents.

## No silent fallback log

1. **Inbox path**
   - Attempted first: `.omx/state/team/execute-phase-7-only-63d0350b/workers/worker-5/inbox.md`.
   - Why unavailable: local `.omx/state` worker directory lacked `inbox.md`.
   - Fallback used: canonical `OMX_TEAM_STATE_ROOT=/Users/jtm427/.omx-runs/run-20260508104302-7a25/.omx/state`.
   - Evidence: startup shell output and team API claim/message logs.

2. **Pack id probe**
   - Attempted first: `PackStore.load_pack("revenue")`.
   - Why unavailable: actual ids are `demo_company.revenue_draft` and `demo_company.revenue`.
   - Fallback used: corrected final probes to approved pack id `demo_company.revenue`.
   - Evidence: `runtime/phase7_verifier/retrieval_probe.json`, `runtime/phase7_verifier/edge_retrieval_final.json`.

3. **Backend probe signature**
   - Attempted first: `KeywordSearchBackend.index_pack(pack, source_path=...)`.
   - Why unavailable: implemented signature is `index_pack(pack)`.
   - Fallback used: reran final probe with `index_pack(pack)`.
   - Evidence: `runtime/phase7_verifier/edge_retrieval_final.json`.

4. **Git commit requirement**
   - Attempted first: `git status --short` before task completion.
   - Why unavailable: this workspace is not a git repository.
   - Fallback used: no commit was created; evidence and report remain in filesystem and task result.
   - Evidence: `runtime/phase7_verifier/git_status_final.log`.

## Changed files / artifacts

Verifier-owned artifacts:

- `reports/phases/phase7_vdb_card_index_retrieval.md`
- `runtime/phase7_verifier/**`

Observed Phase 7 implementation/test surface verified:

- `packages/semantic_registry/semantic_registry/cards.py`
- `packages/semantic_registry/semantic_registry/search.py`
- `packages/semantic_registry/semantic_registry/retrieval/__init__.py`
- `packages/semantic_registry/semantic_registry/retrieval/embeddings.py`
- `packages/semantic_registry/semantic_registry/retrieval/backends.py`
- `packages/semantic_mcp/src/semantic_mcp/tools/search_context.py`
- `packages/semantic_mcp/src/semantic_mcp/tools/__init__.py`
- `tests/registry/test_card_flattening.py`
- `tests/registry/test_embedding_provider.py`
- `tests/registry/test_vdb_backend.py`
- `tests/mcp/test_search_context.py`

## Remaining risks

- The approved demo pack lacks an actual `users.status = S` dormant-customer dictionary and lacks persisted `ambiguity_rule` cards; both are covered/documented via fixture limitation and synthetic ambiguity test rather than approved-pack data.
- Weaviate behavior is verified through explicit seam/fake collection tests, not a live Weaviate service.
- This non-git workspace prevented committing worker-5 artifacts.

## Phase 8 readiness

**Yes, after team lifecycle bookkeeping.** Phase 7 code-level verification is green, and no query execution/UI/SaaS/raw-PII indexing boundary violation was found.
