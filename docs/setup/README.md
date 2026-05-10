# Setup and Local Run Guide

This repository is a local, validation-first Semantic Data Context system.
It is not a dashboard, SaaS BI product, or production SQL execution engine.

For a first-time clone, start with:

1. `python3 scripts/setup/bootstrap.py --check-only`
2. `cp .env.example .env` or `python3 scripts/setup/bootstrap.py --copy-env`
3. `make setup`
4. `make env-check`
5. `make demo`


## Verified Python baseline

Current release-readiness evidence is verified on Python 3.14. Use another
Python version only after running the full test suite and recording the result;
do not treat unverified interpreter fallback as release evidence.

## Quick start

```bash
make setup
make env-check
make test
make demo
```

The top-level `Makefile` keeps the common flows short:

- `make setup` installs the editable local packages
- `make env-check` verifies the core packages import cleanly
- `make test` runs the repository test suite
- `make demo` runs the local file-only builder path and writes artifacts to `runtime/phase12_demo/`
- `make clean-runtime` removes generated runtime artifacts

If you prefer manual commands, the same demo path is available through the builder CLI:

```bash
python3 -m semantic_builder.cli scan --source examples/demo_data --out runtime/phase12_demo/scan_report.json
```

## User configuration rules

User-provided configuration must stay explicit and safe:

- No silent fallback. If a requested backend or adapter is missing or misconfigured, the command must fail loudly with an explicit configuration error.
- No raw PII in configuration values, prompts, or demo inputs. Use safe placeholders in examples and keep secrets out of the repo.
- Backend selection must be explicit. For example, a Weaviate request should only run when that backend is intentionally configured; it must not fall back to keyword search without telling the user.
- MySQL fixture/demo validation is opt-in only via `SEMANTIC_MYSQL_ENABLED=1`, `SEMANTIC_MYSQL_DSN`, `SEMANTIC_MYSQL_DATABASE`, and `SEMANTIC_MYSQL_TABLES`. If MySQL config, driver, fixture schema/database, or live server is unavailable, report the MySQL evidence as pending/unavailable; do not reroute to PostgreSQL, DuckDB, SQLite, cached JSON, or synthetic comments.

See also:

- `docs/execution/SECURITY_CHECKLIST.md`
- `docs/execution/RETRIEVAL_LAYER.md`
- `README.md`
