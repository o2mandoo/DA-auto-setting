# PR-1 Clean Clone Evidence

Verifier task: worker-3

## Environment

- Fresh venv: `/tmp/worker3-pr1-venv`
- Installed from: `requirements-dev.txt` plus editable local packages
- Repository packages installed cleanly in editable mode

## Verification Summary

### 1) Environment import check

**PASS**

Command:

```bash
make env-check
```

Observed output:

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

**PASS**

- No files outside the allowed evidence report were edited.
- The repository still contains explicit references to `/tmp/semantic-data-context-deps` in docs and the Makefile, but this verification run did not introduce any new scope violations.
- The local demo and test suite both exercised the safe, non-production path and did not require live SaaS, UI, or production SQL execution.

## Conclusion

The clean-clone evidence is **partially successful**:

- install / env-check / tests / lint / demo: **PASS**
- full mypy typecheck: **FAIL**

The remaining blocker is the existing typecheck debt across the codebase, not a failure in the clean-venv setup itself.
