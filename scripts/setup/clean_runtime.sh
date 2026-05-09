#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

targets=(
  "runtime/phase12_demo"
  "runtime/benchmarks"
  ".runtime"
  ".runtime_tmp"
  "logs"
)

removed=()
for target in "${targets[@]}"; do
  if [[ -e "$target" ]]; then
    rm -rf "$target"
    removed+=("$target")
  fi
done

if [[ ${#removed[@]} -eq 0 ]]; then
  echo "No generated runtime directories found."
else
  printf 'Removed:%s\n' " ${removed[*]}"
fi
