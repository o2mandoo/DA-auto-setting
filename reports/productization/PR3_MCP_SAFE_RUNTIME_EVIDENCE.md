# PR-3 MCP Safe Runtime Evidence

Status: **FAIL / STALE WORKTREE**

Canonical verifier task: `task-6`

## Scope

Verifier report for the PR-3 safe runtime lane. This worker worktree is
stale relative to the leader/main acceptance target: the combined PR-3 test
sweep still fails during registry collection in this detached worktree, even
though the registration-surface inspection shows the expected safe tool set.

## Changed files

- `reports/productization/PR3_MCP_SAFE_RUNTIME_EVIDENCE.md`

## Commands and results

### FAIL: bare environment check in this worker worktree

Command:

```bash
make env-check
```

Result:

```text
ModuleNotFoundError: No module named 'semantic_contracts'
make: *** [env-check] Error 1
```

Interpretation:

- The detached worker shell does not have the repo packages on `sys.path`.
- This is a workspace setup issue in the worker pane, not a product behavior
  change.

### PASS: environment check in the verified venv

Command:

```bash
export PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src
/tmp/pr1-manager-final-venv/bin/python -c 'import importlib, sys; [importlib.import_module(name) for name in ("semantic_contracts", "semantic_builder", "semantic_registry", "semantic_mcp")]; print(f"environment ok: {sys.version.split()[0]}")'
```

Result:

```text
environment ok: 3.14.4
```

### FAIL: combined PR-3 acceptance sweep in this worker worktree

Command:

```bash
export PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src
/tmp/pr1-manager-final-venv/bin/python -m pytest -q tests/mcp tests/registry tests/security
```

Result:

```text
ERROR collecting tests/registry/test_ambiguity_gate.py
ModuleNotFoundError: No module named 'semantic_registry.runtime.ambiguity'; 'semantic_registry.runtime' is not a package
ERROR collecting tests/registry/test_domain_query_planner.py
ImportError: cannot import name 'DomainQueryPlanner' from 'semantic_registry.runtime' (unknown location)
ERROR collecting tests/registry/test_runtime_models.py
ModuleNotFoundError: No module named 'semantic_registry.runtime.models'; 'semantic_registry.runtime' is not a package
ERROR collecting tests/registry/test_sql_generation.py
ImportError: cannot import name 'DomainQueryPlanner' from 'semantic_registry.runtime' (unknown location)
4 errors in 0.18s
```

Interpretation:

- The worker worktree still exhibits the registry-collection failure that the
  PR-3 lane was meant to isolate or fix.
- Because this verification ran in the detached worker worktree, the failure
  is reported here as stale / not-yet-integrated verifier evidence rather than
  a confirmed leader/main regression.

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
{'tools': ['list_semantic_spaces', 'search_semantic_context', 'resolve_business_terms', 'plan_data_query', 'validate_sql', 'preview_query', 'record_feedback', 'compare_baseline_vs_system_sql'], 'resources': ['semantic://packs', 'semantic://packs/{pack_id}', 'semantic://packs/{pack_id}/terms', 'semantic://packs/{pack_id}/metrics', 'semantic://packs/{pack_id}/policies', 'semantic://packs/{pack_id}/verified-queries'], 'prompts': ['answer_with_semantic_pack'], 'execution_allowed': False, 'mcp_sdk_required_for_stdio': True}
```

## Scope audit

- Registered tools are metadata / planning / validation / preview oriented.
- No `execute_query` tool appears in the registration surface.
- `execution_allowed` is `False`.
- `mcp_sdk_required_for_stdio` is `True`.
- The report changes only this evidence file.

## Remaining risks

- The detached worker worktree still fails registry collection in the combined
  PR-3 sweep because `semantic_registry.runtime` is not a package there.
- This report cannot claim a full PR-3 green state until the leader/main
  integration is verified in the canonical workspace.

## Next PR-4 recommendation

- Re-run the combined PR-3 acceptance sweep from the canonical leader/main
  workspace after the lane-4 and lane-5 changes are fully integrated.
- If the registry-collection failure persists there, the runtime-stub isolation
  change still needs to be applied before PR-4 proceeds.
