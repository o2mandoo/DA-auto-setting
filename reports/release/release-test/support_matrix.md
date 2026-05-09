## Support matrix

| Surface | v1 support level | Current evidence | Production caveat |
|---|---|---|---|
| Packages (`semantic_contracts`, `semantic_builder`, `semantic_registry`, `semantic_mcp`) | **Supported for local validation** | Package pyprojects, Makefile, Phase 12 install/test evidence. | Needs PR-1 clean-venv proof without temp dependency cache. |
| MCP stdio | **Supported with official SDK installed** | `semantic_mcp.server` registration surface and tests. | Missing SDK must fail explicitly; no fake stdio runtime. |
| HTTP adapter | **Planned optional local adapter** | API docs and pure Python handlers only. | Not production server ready until PR-2. |
| Weaviate | **Optional explicit backend** | Backend seam, docs, deterministic tests, optional live test path. | Live service not mandatory; selected backend must fail explicitly if unavailable. |
| PostgreSQL | **Read-only fixture/demo metadata validation** | Scanner/docs/tests. | No production execution; fixture schema/environment gated. |
| MySQL | **Fixture/demo validation; live evidence pending unless provided** | Connector/docs/tests and explicit n8n requirements. | No fallback to other DBs; production MySQL not supported. |
| Oracle | **Unsupported** | Docs state unsupported/no fake behavior. | Must fail explicitly until real connector and tests exist. |
| n8n | **Demo orchestration only** | Requirements/templates/product tests. | Not source of truth; must not execute SQL or hide failures. |
| CI | **Required for release, not proven here** | Local commands defined. | PR-7 must attach CI evidence. |
| Observability | **Local audit artifacts only** | Product API audit writes and safety reports. | Needs correlation ID/error taxonomy evidence in PR-2/PR-7. |
| Release | **Not production release ready** | Clone-ready docs and final integration report. | Needs signed release packet and support-level sign-off. |

## Non-negotiable safety gates

- No production `execute_query` route, MCP tool, handler, or documented requirement.
- No BI/SaaS/dashboard claim for v1.
- No silent fallback after an explicit backend/provider/DB is selected.
- Missing live DB/VDB evidence is a visible gap, not a pass.
- PostgreSQL is metadata scan/profile/demo validation only.
- MySQL is fixture/demo until live read-only evidence is attached.
- Oracle remains unsupported.
