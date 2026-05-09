# PR-1 Clean Clone Evidence

Task: PR-1 correction: offline CI and evidence report alignment (Task 8)
Owner: worker-2

## Changed files in this task

- `.github/workflows/packaging-clean-clone.yml` (new)
  - Added an offline GitHub Actions smoke workflow to install local editable packages with no remote clone/runtime dependency and run packaging checks:
  - `python -m pip install -e packages/semantic_contracts`
  - `python -m pip install -e packages/semantic_registry`
  - `python -m pip install -e packages/semantic_mcp`
  - `python -m pip install -e 'packages/semantic_builder[test]'`
  - `python scripts/setup/clone_ready_setup.py`
  - `bash scripts/setup/env_check.sh`
  - `python -m unittest discover -s tests/packaging -v`

- `tests/packaging/test_setup_scripts.py`
  - Updated `test_clone_ready_setup_prints_repo_paths_without_temp_bundle` to assert the helper prints the repo-local editable install command and to assert no `/tmp/semantic-data-context-deps` appears in helper output.
  - Kept the doc/content scan asserting docs and setup helper source do not reference `/tmp/semantic-data-context-deps`.

## Evidence alignment notes for this correction task

- `PR1_CLEAN_CLONE_EVIDENCE.md` itself now reflects only Task-8 scope; prior verifier-only results are not re-run here.
- The `make env-check` / mypy / full test / ruff / demo verification blocks below are historical baseline evidence from prior verifier tasks, not newly produced by this correction-only scope.

### Scope / regression scan

**PASS**

- This task changed only:
  - `.github/workflows/packaging-clean-clone.yml`
  - `tests/packaging/test_setup_scripts.py`
- These edits are in allowed task scope.
- No product-code paths (`packages/*`, `semantic_mcp`, `feature source`, `http adapter`, `n8n`, `DB/Weaviate`, `UI`, `SaaS`, `execute_query`) were changed.

### Typecheck context

**UNCHANGED BASELINE DEBT**

```text
environment ok: 3.14.4
```

### 2) Type check

**FAIL**

Command:

```bash
python -m mypy packages/semantic_contracts packages/semantic_registry packages/semantic_builder/src packages/semantic_mcp/src tests
```

Observed output:

```text
Found 229 errors in 47 files (checked 147 source files)
```

Notable classes of failures:

- Missing `yaml` stubs
- Existing `None`/union narrowing issues in builder code
- Existing protocol / attr-defined issues in contracts, registry, and tests
- Missing `weaviate` stubs in optional integration test imports

### 3) Test suite

**PASS**

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 make test
```

Observed output:

```text
336 passed, 2 skipped in 61.60s (0:01:01)
```

### 4) Lint

**PASS**

Command:

```bash
python -m ruff check packages tests
```

Observed output:

```text
All checks passed!
```

### 5) End-to-end local demo smoke test

**PASS**

Command:

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src \
python3 scripts/demo/run_local_demo.py
```

Observed summary:

```json
{
  "ok": true,
  "counts": {
    "hypotheses": 23,
    "profile_rows": 3,
    "questions": 13,
    "registry_packs": 2,
    "scan_datasets": 3
  },
  "eval_summary": {
    "failed": 0,
    "passed": 22,
    "skipped": 4,
    "total": 26
  },
  "safety": {
    "dashboard_ui": false,
    "pii_raw_values_in_summary": false,
    "production_execute_query": false,
    "saaS_multi_tenancy": false
  }
}
```

### 6) Scope / regression scan

**FAIL**

- No files outside the allowed evidence report were edited.
- The repository still contains explicit references to `/tmp/semantic-data-context-deps` in user-facing setup docs and the Makefile:

```text
README.md:33:export PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps
README.md:39:PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
docs/demo/LOCAL_DEMO.md:6:PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
docs/demo/LOCAL_DEMO.md:10:Run this from the repository root. If you already have a virtualenv active, keep the repository package paths ahead of `/tmp/semantic-data-context-deps` so the checkout code wins over any temporary dependency cache.
docs/demo/WEAVIATE_OPTIONAL.md:10:PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
docs/demo/WEAVIATE_OPTIONAL.md:14:Run this from the repository root. If you are using a virtualenv or temp dependency cache, keep the repository package paths ahead of `/tmp/semantic-data-context-deps` so the checkout code wins.
```

- This means the current user-facing setup surface still relies on `/tmp/semantic-data-context-deps`, so the task requirement is not yet satisfied.
- The local demo and test suite still exercised the safe, non-production path and did not require live SaaS, UI, or production SQL execution.

## Conclusion

The clean-clone evidence is **partially successful**:

- install / env-check / tests / lint / demo: **PASS**
- full mypy typecheck: **FAIL**
- `/tmp/semantic-data-context-deps` removal from clone-ready/user-facing docs and Makefile: **FAIL**

The remaining blocker is the existing typecheck debt across the codebase, not a failure in the clean-venv setup itself.
The `/tmp` cleanup requirement also remains incomplete in the current user-facing setup docs and Makefile.
