# Support matrix

| Surface | Support level | Current evidence | Production caveat |
|---|---|---|---|
| Packages (semantic_contracts, semantic_builder, semantic_registry, semantic_mcp) | Supported for local validation | Editable local packages and Makefile setup/test targets. | Needs clean-venv proof and dependency snapshot for release promotion. |
| MCP stdio | Supported with official SDK installed | semantic_mcp registration surface and tests. | SDK/runtime absence must fail explicitly; no fake stdio runtime. |
| HTTP adapter | Planned optional local adapter | Pure Python handlers and API docs only. | Not production server ready until the adapter PR lands. |
| Weaviate | Optional explicit backend | Backend seam and deterministic tests. | Selected Weaviate must fail explicitly if unavailable; no silent fallback. |
| PostgreSQL | Read-only fixture/demo metadata validation | Scanner/docs/tests only. | No production execution; fixture/environment gated. |
| MySQL | Fixture/demo validation; live evidence pending | Connector/docs/tests and explicit n8n requirements. | No fallback to other DBs; production MySQL is not supported by default. |
| Oracle | Unsupported | Docs state unsupported/no fake behavior. | Must fail explicitly until a real connector and tests exist. |
| n8n | Demo orchestration only | Requirements/templates/product tests. | Not source of truth; must not execute SQL or hide failures. |
| CI | Required for release, not proven here | Local commands defined. | CI logs must be attached before a production release claim. |
| Observability | Local audit artifacts only | Product API audit paths and safety reports. | Needs correlation ID/error taxonomy evidence in PR-2/PR-7. |
| Release | Not production release ready | Clone-ready docs and final integration report. | Needs signed release packet and support-level sign-off. |
