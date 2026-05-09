# Setup Scripts

Small, repo-local helpers for clone-ready setup and cleanup.

## Available helpers

- `env_check.sh` — verify the expected local setup files and placeholder env contract
- `clean_runtime.sh` — remove generated local runtime artifacts

## Usage

Run them with `bash` from the repo root:

```bash
bash scripts/setup/env_check.sh
bash scripts/setup/clean_runtime.sh
```

These helpers are intentionally conservative:

- they do not fetch dependencies
- they do not contact external services
- they do not write secrets
