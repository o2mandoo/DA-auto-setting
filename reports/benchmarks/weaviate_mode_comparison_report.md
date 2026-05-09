# Weaviate mode comparison report

Scope: MCP search integration over the explicit `weaviate` and `keyword`
selection paths.

## Evidence summary

| Evidence lane | Mode | Query mode | Filters forwarded | Fallback used | Result |
| --- | --- | --- | --- | --- | --- |
| Deterministic fake backend | `keyword` | `keyword` | yes | false | `tests/mcp/test_search_context.py` covers structured keyword response fields and no fallback. |
| Deterministic fake backend | `weaviate` | `bm25` | yes | false | `tests/mcp/test_search_context.py` covers backend_config forwarding and explicit mode selection. |
| Deterministic fake backend | `weaviate` | `hybrid` | yes | false | `tests/mcp/test_search_context.py` covers explicit hybrid forwarding. |
| Deterministic fake backend | `weaviate` | `near_vector` | yes | false | `tests/mcp/test_search_context.py` covers explicit vector forwarding. |
| No-config path | `weaviate` | `hybrid` default | yes | false | explicit `backend_configuration_error` with no keyword fallback. |
| No-adapter path | `keyword` | `keyword` | yes | false | explicit `backend_configuration_error` when the keyword adapter is missing. |
| Live skip path | `weaviate` | env-selected | yes | false | `tests/integration/test_weaviate_live_optional.py` skips cleanly when `SEMANTIC_WEAVIATE_*` is absent. |

## Notes

- The report is intentionally local-first and does not require a live Weaviate
  server.
- `fallback_used` is expected to remain `false` on all explicit selection
  paths; unsupported configurations return structured `error` details instead.
- If a live environment is configured, the integration test should exercise the
  real backend and fail explicitly if the service is unreachable.
- The comparison evidence is pinned by `tests/mcp/test_search_context.py::test_weaviate_mode_comparison_report_lists_all_three_modes`.
- Metadata-filter evidence is pinned by the retrieval/MCP tests covering
  `dataset_id`, `domain`, `pack_id`, `space_id`, `card_type`, `source_path`,
  `status`, `allowed_roles`, and `blocked_columns`.
