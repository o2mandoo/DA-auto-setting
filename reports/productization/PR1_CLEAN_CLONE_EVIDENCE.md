# PR-1 Clean Clone Evidence

Task: PR-1 correction: canonical evidence report alignment (Task 11)
Owner: worker-2

## Current leader/main truth

- Setup, docs, demo, Makefile, and `AGENTS.md` no longer rely on `/tmp/semantic-data-context-deps` in the current leader/main truth.
- Task 7 fixed the semantic-builder dependency and user-facing docs.
- Task 8 added the offline CI workflow and packaging test updates.
- Task 9’s earlier failure snapshot is stale relative to the current leader/main truth and is superseded by this correction.
- Task 13 fixed the last remaining current-surface `/tmp` reference in `AGENTS.md`.
- `mypy` remains existing typecheck debt and is **not** a PR-1 acceptance blocker.

## Changed files in this task

- `.github/workflows/packaging-clean-clone.yml`
  - Added an offline smoke workflow that installs editable local packages and runs:
    - `make env-check`
    - `PYTHONDONTWRITEBYTECODE=1 make test`
    - `python -m unittest discover -s tests/packaging -v`
    - `python scripts/setup/clone_ready_setup.py`
    - `bash scripts/setup/env_check.sh`

- `reports/productization/PR1_CLEAN_CLONE_EVIDENCE.md`
  - Re-aligned the report to the current leader/main truth.
  - Removed stale verifier-style framing that treated the earlier `/tmp` evidence snapshot as current.
  - Added the exact changed-file list and snapshot guidance below.
  - Added `AGENTS.md` to the current no-/tmp operational surface.

## Scope scan

**PASS**

- This task changed only:
  - `.github/workflows/packaging-clean-clone.yml`
  - `reports/productization/PR1_CLEAN_CLONE_EVIDENCE.md`
- No feature source, HTTP adapter, n8n, DB/Weaviate, UI, SaaS, or `execute_query` paths were changed.

## Verification context

- The workflow now covers:
  - editable local package install
  - `make env-check`
  - `make test`
  - packaging smoke tests
  - clone-ready setup helper validation
  - environment contract validation
- `mypy` remains existing debt; it is not being used as a PR-1 acceptance gate.
- `AGENTS.md` is now part of the current no-/tmp operational surface after task 13.

## Dependency snapshot target

If a snapshot file is needed for handoff/audit, write it to:

```text
reports/productization/PR1_PIP_FREEZE.txt
```

Suggested capture command:

```bash
. .venv-pr1-evidence/bin/activate
python -m pip freeze > reports/productization/PR1_PIP_FREEZE.txt
```

## Conclusion

The PR-1 evidence report now reflects the current leader/main truth:

- no user-facing `/tmp` dependency in the accepted setup path
- no current-surface `/tmp` reference in `AGENTS.md`
- Task 7 / Task 8 corrections incorporated
- Task 9 stale failure explicitly superseded
- Task 13 fixed the last remaining current-surface `/tmp` reference
- `mypy` documented as existing debt, not a blocker
