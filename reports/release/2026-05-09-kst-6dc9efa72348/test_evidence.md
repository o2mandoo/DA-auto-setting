# Test Evidence

## Reference set

This release packet does not re-run the suite. It points at already-verified command outputs from the source evidence reports:

| Source report | Command | Observed output |
|---|---|---|
| `reports/productization/PR1_FINAL_VERIFIER_EVIDENCE.md` | `make env-check` | `environment ok: 3.14.4` |
| `reports/productization/PR1_FINAL_VERIFIER_EVIDENCE.md` | `PYTHONDONTWRITEBYTECODE=1 make test` | `337 passed, 2 skipped in 58.87s` |
| `reports/productization/mysql_db_target_test_report.md` | focused pytest evidence | `21 passed in 0.13s` |
| `reports/productization/mysql_db_target_readiness_report.md` | `make test` | `336 passed, 2 skipped on 2026-05-09` |
| `reports/final/final_integration_report.md` | `python3 scripts/demo/run_local_demo.py` | `ok=true; eval_summary.passed=10; eval_summary.failed=0` |

## Why this is sufficient for the release packet

- The packet is an evidence index, not a re-run harness.
- The packet keeps the original command/output references intact for auditability.
- Missing or optional live evidence remains explicit in the source reports.
