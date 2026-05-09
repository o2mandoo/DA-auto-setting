# Phase 7 Leader Evaluation — Weaviate / Card Index / Retrieval Layer

## Evaluation method

Ouroboros MCP evaluate tool was not directly available in this tool list via ToolSearch, so I used the documented fallback: local mechanical verification plus semantic acceptance review. This fallback is explicit and logged here.

A first leader probe failed because the probe expected a top-level `status` field for Weaviate errors, while the implemented MCP tool correctly returns `error.code=backend_configuration_error`. I corrected the probe and reran it successfully.

## Verdict

PASS.

## Stage 1 — Mechanical verification

Evidence under `runtime/phase7_leader_eval/`:

- contracts: PASS, 20 tests.
- registry: PASS, 55 tests.
- mcp: PASS, 22 tests.
- builder: PASS, 40 tests.
- phase7 targeted: PASS, 20 tests.
- fixed phase7 probe: PASS.
- forbidden scan: PASS.

## Stage 2 — Semantic acceptance review

PASS against Phase 7 requirements:

1. Card flattening exists for major Semantic Pack card types.
2. Search backend interface exists.
3. Keyword backend works.
4. Weaviate backend is explicit and has no silent fallback.
5. Deterministic embedding provider works offline.
6. `search_semantic_context` returns structured card results.
7. Raw PII values are not indexed or returned in email probe.
8. Draft status/warnings are preserved.
9. Retrieval tests cover term, metric, value dictionary fixture, policy/filtering, and ambiguity-rule fixture.
10. No query execution, dashboard UI, SaaS feature, LanceDB dependency, or external network default was introduced.

## Known fixture limitations

- Approved demo pack does not contain a real `users.status=S` dormant-customer value dictionary; Phase 7 covers it with a minimal test fixture.
- Approved demo pack does not contain persisted ambiguity-rule cards; Phase 7 covers ambiguity retrieval with a synthetic fixture.
- Weaviate is verified by explicit seam/fake collection tests, not live Weaviate service.

## Whether Phase 8 may start

Yes. Phase 8 may start after team shutdown.
