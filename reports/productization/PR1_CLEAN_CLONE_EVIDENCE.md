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

- `mypy` failures remain pre-existing baseline debt and were not introduced by Task 8.

## Conclusion

Task 8 is focused on **offline CI and evidence report alignment** and is complete once this report reflects exactly the two files changed by worker-2 for this task.
