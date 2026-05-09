# Weaviate + Multi-domain Benchmark Pre-implementation Alignment

Date: 2026-05-09 KST

## Scope

This is a docs-only pre-implementation alignment pass for optional live Weaviate integration and Superstore/Sinagong benchmark mapping expansion.

No product code, benchmark runner code, Weaviate client code, UI, SaaS, production database credential, or `execute_query` path was implemented in this pass.

## Ouroboros query evaluation

The previous request was clear on product direction: expand beyond Superstore into optional live Weaviate and multi-domain benchmark mappings for the Sinagong Tableau 2026 corpus.

The current request was clear on execution mode: add a forward rule that fallbacks must be remediated when feasible, evaluate the prior/current asks with Ouroboros, and execute pre-implementation markdown alignment.

Remaining ambiguities to resolve during implementation planning:

1. Whether every Sinagong domain should become a fully semantic-gold benchmark immediately or whether some domains may remain scanner/profile/retrieval/safety benchmarks first.
2. Whether live Weaviate should be tested with `bm25`, `hybrid`, or `near_vector` by default on the user's local service.
3. Whether the nested yearly `와일드카드유니온실습/SEILOneCompany_*.xlsx` files should be part of the first executable sales benchmark or a second bounded corpus benchmark.

Decision for this pass: keep this as docs-only alignment and leave implementation to the next team execution.

## Alignment changes made

- Added repository-wide fallback remediation rule to `AGENTS.md`.
- Clarified Sinagong inventory as 20 `.xlsx` files recursively: 16 top-level plus 4 nested yearly files.
- Added recommended Sinagong benchmark family split to `docs/execution/VALIDATION_DATASETS.md`.
- Updated `docs/execution/DATASET_BENCHMARKS.md` so it no longer implies only the demo fixture exists locally.
- Updated `docs/execution/WEAVIATE_AND_MULTI_DOMAIN_BENCHMARK_PLAN.md` with current-state matrix and fallback remediation rules.
- Updated `docs/execution/RETRIEVAL_LAYER.md` to state that keyword search is not a recovery path for failed explicit Weaviate requests.
- Added count summary to `docs/reference/test_datasets/DATASET_MANIFEST.md`.

## Fallback/remediation rule now locked

If a preferred path fails and the cause is fixable within the current task scope, the agent/worker must fix it and rerun the preferred path before accepting a fallback. If it cannot be fixed safely, the report must include:

- first attempted path,
- failure reason,
- remediation attempted or rejected,
- fallback/skip path,
- evidence.

## Dataset inventory evidence

A recursive local inventory check found:

- Sinagong recursive `.xlsx` count: 20
- Sinagong top-level `.xlsx` count: 16
- Sinagong nested `.xlsx` count: 4

This aligns the plan with `docs/reference/test_datasets/DATASET_MANIFEST.md`.

## Next implementation gate

Implementation may start with the team prompt in `docs/execution/WEAVIATE_AND_MULTI_DOMAIN_BENCHMARK_PLAN.md` only after workers treat this document and `AGENTS.md` as governing rules.

## Verification evidence

Commands run:

```bash
python3 - <<'PY'
# checked Sinagong recursive/top-level/nested workbook counts and required doc strings
PY
```

Result:

```text
doc_alignment_checks=PASS
sinagong_recursive_xlsx_count= 20
sinagong_top_level_xlsx_count= 16
sinagong_nested_xlsx_count= 4
```

```bash
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps \
python3 -m unittest discover -s tests/eval -v
```

Result:

```text
Ran 12 tests in 2.646s
OK
```

```bash
grep -RIn '<stale Sinagong count or old demo-only benchmark wording>' docs/execution docs/reference/test_datasets AGENTS.md reports/final reports/phases
```

Result: no stale matches.

## Fallback/remediation evidence from this pass

- `omx explore` was invoked with the corrected `--prompt` syntax and returned an Ouroboros-style clarity/ambiguity assessment.
- The first eval test command used an import path that allowed `/tmp/semantic-data-context-deps` to shadow local packages. This was resolved by putting local package paths before `/tmp/semantic-data-context-deps` in `PYTHONPATH`, then rerunning the eval suite successfully.
- One stale-count grep validation command had shell quoting that interpreted markdown backticks. This was corrected with single-quoted grep patterns and rerun successfully.
