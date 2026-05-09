# Development setup

This repo is designed to run locally from a fresh clone with no production
credentials.

## 1) Install dependencies

Use the project’s preferred Python environment and install the repo’s local
requirements in editable mode if needed.

Example:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e packages/semantic_contracts
pip install -e packages/semantic_builder
pip install -e packages/semantic_registry
pip install -e packages/semantic_mcp
```

## 2) Copy the example environment file

Create a local `.env` from `.env.example` and fill in only the provider you
intend to use.

```bash
cp .env.example .env
```

You can also use the repo helper:

```bash
python3 scripts/setup/bootstrap.py --copy-env
```

## 3) Choose an LLM provider

The Builder supports three practical modes:

- `mock` — deterministic, offline-safe, and the default for tests/demos.
- `local` — explicit local/OpenAI-compatible provider seam when you want to
  wire your own endpoint.
- `OpenAI-compatible` — use the `SDC_LLM_*` fields to point at a compatible
  endpoint, model, and API key.

Recommended local env fields:

```bash
SDC_LLM_ENABLED=1
SDC_LLM_PROVIDER=openai-compatible
SDC_LLM_ENDPOINT=http://localhost:11434/v1
SDC_LLM_MODEL=qwen2.5:7b
SDC_LLM_API_KEY=local-dev-token
SDC_LLM_TIMEOUT=30
SDC_LLM_MAX_TOKENS=1024
SDC_LLM_TEMPERATURE=0.2
```

## 4) Run the local demo

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 scripts/demo/run_local_demo.py
```

## 5) Run the main tests

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 -m unittest discover -s tests -v
```

## 6) Optional integrations

### Weaviate

Use the optional live Weaviate path only when you have an explicit service
configured. If the service is unavailable, the repo should fail explicitly
rather than silently falling back.

See:

- `docs/demo/WEAVIATE_OPTIONAL.md`
- `docs/execution/RETRIEVAL_LAYER.md`
- `tests/integration/test_weaviate_live_optional.py`

### PostgreSQL

Read-only PostgreSQL scanning is available through the safe scanner/config path
only. Use it for local fixtures or verified test databases, not production
credentials.

See:

- `docs/execution/SECURITY_CHECKLIST.md`
- `tests/builder/test_db_scanner_cli.py`
- `tests/builder/test_db_connector_contract.py`

## 7) If you are cloning the repo for the first time

Start with the mock provider, run the demo, then opt into local or external
provider settings only after the baseline tests pass.
