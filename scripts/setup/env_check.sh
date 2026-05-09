#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

errors=0

if [[ ! -f .env.example ]]; then
  echo "ERROR: .env.example is missing" >&2
  errors=1
else
  echo "PASS: .env.example present"
fi

if [[ -f .env ]]; then
  echo "INFO: .env exists locally; confirm it is not committed"
else
  echo "PASS: .env is not present in the repo checkout"
fi

required_markers=(
  "SDC_LLM_PROVIDER"
  "SDC_LLM_ENABLED"
  "SEMANTIC_WEAVIATE_ENABLED"
  "SEMANTIC_POSTGRES_ENABLED"
  "SEMANTIC_RUNTIME_DIR"
)

for marker in "${required_markers[@]}"; do
  if grep -q "^${marker}=" .env.example; then
    echo "PASS: $marker declared in .env.example"
  else
    echo "ERROR: $marker missing from .env.example" >&2
    errors=1
  fi
done

if grep -qE '(^|[^A-Z0-9_])(secret|sk-|password=)' .env.example; then
  echo "ERROR: .env.example appears to contain secret-like content" >&2
  errors=1
else
  echo "PASS: .env.example remains placeholder-only"
fi

if grep -q '^PYTHONPATH=' docs/execution/SECURITY_CHECKLIST.md; then
  echo "PASS: documented PYTHONPATH examples exist"
fi

exit "$errors"
