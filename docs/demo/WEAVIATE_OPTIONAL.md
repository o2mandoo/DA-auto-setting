# Optional Live Weaviate Demo

This demo exercises the explicit Weaviate backend only when the environment is
configured for it.

```bash
SEMANTIC_WEAVIATE_ENABLED=1 \
SEMANTIC_WEAVIATE_URL=http://localhost:8080 \
SEMANTIC_WEAVIATE_COLLECTION=SemanticCardsTest \
PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_mcp/src \
python3 -m unittest tests.integration.test_weaviate_live_optional -v
```

Run this from the repository root. If you are using a virtualenv or temp dependency cache, keep the repository package paths ahead of any temporary dependency cache so the checkout code wins.

Behavior:

- If `SEMANTIC_WEAVIATE_ENABLED`, `SEMANTIC_WEAVIATE_URL`, or
  `SEMANTIC_WEAVIATE_COLLECTION` is missing, the test skips explicitly.
- If the environment is present but Weaviate is unreachable or misconfigured,
  the test fails explicitly; there is no keyword fallback.
- If the live backend succeeds, it should index safe semantic cards and return
  results with no raw PII payloads.

Notes:

- This is an optional verification path, not a required offline dependency.
- The deterministic fake backend tests remain the default proof for CI and
  local runs without a live Weaviate service.
