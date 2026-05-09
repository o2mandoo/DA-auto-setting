# Setup and Local Run Guide

This repository is a local, validation-first Semantic Data Context system.
It is not a dashboard, SaaS BI product, or production SQL execution engine.

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
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 -m semantic_builder.cli scan --source examples/demo_data --out runtime/phase12_demo/scan_report.json
```

## User configuration rules

User-provided configuration must stay explicit and safe:

- No silent fallback. If a requested backend or adapter is missing or misconfigured, the command must fail loudly with an explicit configuration error.
- No raw PII in configuration values, prompts, or demo inputs. Use safe placeholders in examples and keep secrets out of the repo.
- Backend selection must be explicit. For example, a Weaviate request should only run when that backend is intentionally configured; it must not fall back to keyword search without telling the user.

See also:

- `docs/execution/SECURITY_CHECKLIST.md`
- `docs/execution/RETRIEVAL_LAYER.md`
- `README.md`
