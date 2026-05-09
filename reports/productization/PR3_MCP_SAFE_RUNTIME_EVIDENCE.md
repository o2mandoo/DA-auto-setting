# PR-3 MCP Safe Runtime Evidence

Status: **PASS**

Canonical verifier task: `task-6`

## Scope

Verifier report for the PR-3 safe runtime lane. This refresh uses the
canonical leader/main checkout at `/Users/jtm427/Desktop/workplace/data/semantic-data-context`
after the env-check correction requested by the leader.

## Changed files

- `reports/productization/PR3_MCP_SAFE_RUNTIME_EVIDENCE.md`

## Commands and results

### PASS: environment check in canonical leader/main checkout

Command:

```bash
make env-check
```

Result:

```text
environment ok: 3.14.4
```

### PASS: combined PR-3 acceptance sweep in canonical leader/main checkout

Command:

```bash
export PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src
/tmp/pr1-manager-final-venv/bin/python -m pytest -q tests/mcp tests/registry tests/security
```

Result:

```text
145 passed, 1 skipped in 3.38s
```

### PASS: registration-surface inspection

Command:

```bash
export PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src
/tmp/pr1-manager-final-venv/bin/python - <<'PY'
from semantic_mcp.server import inspect_registration_surface
print(inspect_registration_surface())
PY
```

Result:

```text
{'tools': ['list_semantic_spaces', 'search_semantic_context', 'resolve_business_terms', 'plan_data_query', 'validate_sql', 'preview_query', 'record_feedback', 'compare_baseline_vs_system_sql'], 'resources': ['semantic://packs', 'semantic://packs/{pack_id}', 'semantic://packs/{pack_id}/terms', 'semantic://packs/{pack_id}/metrics', 'semantic://packs/{pack_id}/policies', 'semantic://packs/{pack_id}/verified-queries'], 'prompts': ['answer_with_semantic_pack'], 'registered_tools': ['list_semantic_spaces', 'search_semantic_context', 'resolve_business_terms', 'plan_data_query', 'validate_sql', 'preview_query', 'record_feedback', 'compare_baseline_vs_system_sql'], 'registered_resources': ['semantic://packs', 'semantic://packs/{pack_id}', 'semantic://packs/{pack_id}/terms', 'semantic://packs/{pack_id}/metrics', 'semantic://packs/{pack_id}/policies', 'semantic://packs/{pack_id}/verified-queries'], 'registered_prompts': ['answer_with_semantic_pack'], 'execution_allowed': False, 'production_execution_allowed': False, 'mcp_sdk_required_for_stdio': True, 'stdio_requires_official_mcp_sdk': True, 'no_execute_query_tool': True, 'preview_scope': 'local/demo/test'}
```

## Scope audit

- Registered tools are metadata / planning / validation / preview oriented.
- No `execute_query` tool appears in the registration surface.
- `execution_allowed` is `False`.
- `production_execution_allowed` is `False`.
- `mcp_sdk_required_for_stdio` is `True`.
- `stdio_requires_official_mcp_sdk` is `True`.
- `no_execute_query_tool` is `True`.
- `preview_scope` is `local/demo/test`.
- The report changes only this evidence file.

## Remaining risks

- The canonical leader/main acceptance sweep is green.
- No remaining runtime-surface concerns were observed in the refreshed checks.

## Next PR-4 recommendation

- Proceed to PR-4 only if a new leader task requests follow-up work; this
  verifier refresh is complete.
