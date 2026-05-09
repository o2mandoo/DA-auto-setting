# Clone-Ready Usage Summary

Use this repository clone-ready path when you want the fastest safe local start.

## Quick start

1. Create and activate a virtual environment.
2. Install the editable local packages.
3. Copy `.env.example` to `.env`.
4. Run the local env check.
5. Choose a provider mode:
   - `mock` for offline/default demo runs
   - `local` for an explicit OpenAI-compatible local endpoint
   - `openai-compatible` for a remote or local compatible service

## Core commands

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
bash scripts/setup/env_check.sh
python3 scripts/demo/run_local_demo.py
```

## Recommended verification

```bash
python3 -m unittest discover -s tests/security -v

python3 -m unittest discover -s tests/registry -v

python3 -m unittest discover -s tests/mcp -v
```

## Optional paths

- Weaviate: gated by `SEMANTIC_WEAVIATE_ENABLED`
- PostgreSQL fixture scanning: read-only and gated by `SEMANTIC_POSTGRES_ENABLED`

## Safety reminders

- No production `execute_query`
- No silent fallback after explicit backend selection
- No raw PII in prompts, logs, or generated artifacts
- The editable install path is repo-native through `requirements-dev.txt`; no temporary dependency cache is required
