# PR-2 HTTP Adapter Evidence (Verifier)

Status: **FAIL**

Canonical verifier task: `task-65`

## Scope

Verifier-only report for the PR-2 HTTP adapter lane after task-61 and task-64
completed. No product code edits were made in this task.

## Changed files

- `reports/productization/PR2_HTTP_ADAPTER_EVIDENCE.md`

## Commands and results

### PASS: environment check

Command:

```bash
source .venv/bin/activate && make env-check
```

Result:

```text
environment ok: 3.14.4
```

### FAIL: product/packaging regression sweep

Command:

```bash
source .venv/bin/activate && python -m pytest -q tests/product tests/packaging
```

Result:

```text
1 failed, 33 passed in 2.51s
```

Failure:

- `tests/product/test_phase18_evidence_console.py::test_twenty_domain_evidence_uses_manifest_without_inventing_scores`
- Assertion failed because no domain summary note contained the expected `"per-file score is not invented"` phrase.

### PASS: security hardening/scope checks

Command:

```bash
source .venv/bin/activate && python -m unittest tests.security.test_phase12_hardening tests.security.test_phase12_scope -v
```

Result:

```text
Ran 12 tests in 0.274s

OK
```

### FAIL: HTTP adapter smoke

Command:

```bash
source .venv/bin/activate && python -m semantic_registry.product.http_adapter --check --pack-root semantic_packs --audit-root runtime/product_http_adapter_verifier
```

Result:

```text
KeyError: 'status'
```

Failure point:

- `packages/semantic_registry/semantic_registry/product/http_adapter.py`
- `run_check()` expects `health.body["status"]`, but the current health response shape does not provide that key in the smoke path.

### PASS: static audit for production `execute_query` route/handler

Command:

```bash
python3 - <<'PY'
from pathlib import Path
import re
root = Path('packages')
def_hits = []
call_hits = []
for p in root.rglob('*.py'):
    text = p.read_text(encoding='utf-8')
    if re.search(r'\\bdef\\s+execute_query\\b', text):
        def_hits.append(str(p))
    if 'execute_query(' in text or 'execute_query ' in text:
        call_hits.append(str(p))
print(def_hits)
print(call_hits)
PY
```

Result:

```text
[]
[]
```

### PASS: static audit for forbidden web framework/UI/SaaS imports in package code

Command:

```bash
python3 - <<'PY'
from pathlib import Path
root = Path('.')
forbidden = ['fastapi', 'flask', 'django', 'streamlit', 'gradio', 'dash']
hits = []
for p in (root/'packages').rglob('*.py'):
    text = p.read_text(encoding='utf-8').lower()
    if any(f'import {name}' in text or f'from {name} import' in text for name in forbidden):
        hits.append(str(p))
print(hits)
PY
```

Result:

```text
[]
```

## Scope audit

- No production `execute_query` route or handler was found in `packages/`.
- No forbidden web framework/UI/SaaS imports were found in package code.
- The verifier report only changed this evidence file.

## Remaining risks

- The product/packaging sweep still contains one unrelated pre-existing failure in
  `tests/product/test_phase18_evidence_console.py`.
- The adapter smoke check still fails in the current code path with
  `KeyError: 'status'` during `run_check()`.

## Next PR-3 recommendation

- Stabilize the product readiness evidence path so `run_check()` reads the
  adapter health payload shape correctly.
- Re-run the product/packaging sweep after the unrelated phase-18 regression is
  resolved.
