# Known Limitations

- The repository is clone-ready for local validation and demo operation, but not production ready.
- The HTTP adapter is optional/local and remains transport-only around repo-owned handlers.
- MCP stdio launch requires the official SDK.
- n8n is orchestration-only and depends on the documented Product API routes.
- Release claims remain evidence-based; missing evidence must be reported explicitly.
- No production `execute_query` surface exists.
- No silent fallback or raw PII release artifact should be introduced.
