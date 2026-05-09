# PR-5 Semantic Retrieval Evidence

## Verdict

PASS. PR-5 was executed after verifying that both local live database fixture targets contain the same 20-dataset Sinagong corpus with test-only synthetic table/column metadata.

## Precheck: PostgreSQL/MySQL 20-dataset fixture corpus

Command rerun before retrieval hardening:

```bash
export SEMANTIC_CONTEXT_FIXTURE_DB=1
PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_mcp/src:packages/semantic_builder/src:. .venv/bin/python -m experiments.db_fixtures.scripts.sinagong_corpus_live_evidence \
  --postgres-dsn postgresql://sdc_fixture:<FIXTURE_PASSWORD>@localhost:55432/semantic_fixture_postgres_scope_c \
  --mysql-dsn mysql://sdc_fixture:<FIXTURE_PASSWORD>@localhost:33306/semantic_fixture_mysql_scope_c \
  --output reports/reality/sinagong_20_live_db_fixture_evidence.json
```

Evidence file: `reports/reality/sinagong_20_live_db_fixture_evidence.json`.

| Check | PostgreSQL | MySQL |
| --- | ---: | ---: |
| Status | loaded | loaded |
| Dataset count | 20 | 20 |
| Sheet/table count | 89 | 89 |
| Row count | 103,980 | 103,980 |
| Manifest rows | 89 | 89 |
| Table comments verified | 89 | 89 |
| Column comments verified | 1,519 | 1,519 |
| Metadata verified | true | true |
| Fallback used | false | false |

Important boundary: this fixture metadata is `TEST_ONLY_SYNTHETIC_METADATA` and `synthetic_truth_blocked=true`; it is not product truth and cannot be treated as approved semantic context without pack review/promotion.

## Implemented PR-5 retrieval hardening

- Added deterministic Semantic Pack query-understanding helpers.
- MCP `search_semantic_context` now returns `query_understanding` with matched terms, metrics, aliases, verified-query patterns, reverse-question candidates, ambiguity-rule candidates, unknown terms, and warnings.
- Demo pack now contains Korean aliases for `new_customer` and `net_revenue` plus persisted ambiguity rules for new-customer date basis and net-revenue refund timing.
- Keyword and backend scoring now blocks broad Korean generic-token overmatch, e.g. `휴면 고객` no longer matches `신규 고객` just because both contain `고객`.
- MCP ranking promotes real backend hits that are exact Semantic Pack matches. It does not fabricate retrieval results.
- Evaluation runner now records retrieval metrics (`recall_at_k`, `mrr`, first hit rank, missing ids) for semantic-gold retrieval cases.
- Weaviate explicit-failure behavior remains typed and visible; no keyword fallback occurs after explicit Weaviate selection failure.

## Spot-check payloads

`search_semantic_context("demo_company.revenue", "첫 결제 고객의 net revenue", backend=keyword)` returns:

- matched terms: `term.new_customer`, `term.net_revenue`
- matched metric: `metric.net_revenue`
- verified-query pattern: `verified_query.monthly_new_customer_revenue`
- reverse questions: `rq.new_customer.date_basis`, `rq.net_revenue.refund_timing`
- ambiguity rules: `ambiguity.new_customer.date_basis`, `ambiguity.net_revenue.refund_timing`
- fallback: `false`
- error: `null`

`search_semantic_context("demo_company.revenue", "휴면 고객", backend=keyword)` returns:

- results: `[]`
- warnings: `unknown_or_low_confidence_domain_term`, `no_semantic_pack_match`
- unknown terms: `휴면 고객`
- fallback: `false`

## Tests run

```bash
make env-check
# environment ok: 3.14.4

PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_mcp/src:packages/semantic_builder/src .venv/bin/python -m pytest -q \
  tests/fixtures/test_sinagong_corpus_live_evidence.py \
  tests/fixtures/test_db_fixture_comment_modes.py \
  tests/fixtures/test_mysql_fixture_loader.py \
  tests/fixtures/test_postgres_live_evidence.py \
  tests/fixtures/test_mysql_live_evidence.py
# 24 passed

PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_mcp/src:packages/semantic_builder/src .venv/bin/python -m pytest -q \
  tests/registry/test_semantic_query.py \
  tests/registry/test_search_index.py \
  tests/mcp/test_search_context.py \
  tests/eval/test_eval_runner.py \
  tests/registry/test_vdb_backend.py \
  tests/integration/test_weaviate_live_optional.py
# 44 passed, 2 skipped

PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_mcp/src:packages/semantic_builder/src .venv/bin/python -m pytest -q
# 363 passed, 2 skipped
```

The two skips are optional live/config-dependent paths. They were explicit skips, not fallback.

## 2026-05-09 recheck

Focused regression and runtime smoke were rerun after tightening explicit no-fallback coverage:

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_mcp/src \
  .venv/bin/python -m pytest -q \
  tests/registry/test_semantic_query.py \
  tests/registry/test_search_index.py \
  tests/registry/test_vdb_backend.py \
  tests/mcp/test_search_context.py
# 35 passed, 1 skipped

PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_mcp/src \
  .venv/bin/python - <<'PY'
from semantic_mcp import search_semantic_context
resp = search_semantic_context('demo_company.revenue', '휴면 고객', filters={'backend': 'keyword', 'limit': 5})
print(resp['fallback_used'])
print(resp['query_understanding']['unknown_terms'])
print(resp['query_understanding']['recommended_card_types'])
print(resp['query_understanding']['expanded_query'])
print(resp['results'])
print(resp['error'])
PY
# False
# ['휴면 고객']
# ['reverse_question', 'business_term']
# 휴면 고객
# []
# None
```

This recheck makes the explicit no-silent-fallback boundary visible in both tests and a live payload: unknown terms stay explicit, `fallback_used` remains `false`, and no keyword fallback is hidden behind a backend error.

## No-silent-fallback log

- Live DB corpus precheck was rerun successfully. The earlier PostgreSQL/MySQL fixture issues were fixed before PR-5 and did not recur.
- Team decomposition drift was corrected by lane-specific inbox instructions, and the missing context snapshot was copied into the worker worktrees. When the worktree `.venv` was missing, verification used the absolute repo venv as instructed.
- Team-state/process failures in tasks 1 and 11 remain terminal fallbacks and are acknowledged as non-product issues rather than product behavior regressions.
- PR-5 was completed through team workers plus leader verification, with the final reporting and bookkeeping carried in the worker lane.
- Full test execution regenerated final benchmark summary artifacts as a side effect; those unrelated generated reports were restored to avoid silently broadening PR-5 scope.

## Remaining risks

- Live Weaviate remains optional unless `SEMANTIC_WEAVIATE_*` is configured; fake backend coverage proves mode/filter forwarding but not live recall quality.
- Domain-specific synonym coverage is currently pack-driven. Other domains will need generated or confirmed pack aliases/terms before retrieval can behave as richly as the demo revenue pack.
- The 20-dataset DB fixture metadata is intentionally synthetic and test-only; it validates environment readiness, not semantic truth quality.

## 2026-05-09 final coverage update

Final semantic-gold coverage for the Sinagong benchmark pack is now explicit in the regression suite:

- 20 business terms
- 20 metrics
- 20 ambiguity rules
- 20 reverse questions
- manifest references 20 `.xlsx` source files plus 1 YAML benchmark-only support pack

Final verification run set:

```bash
PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src /Users/jtm427/Desktop/workplace/data/semantic-data-context/.venv/bin/python -m pytest -q tests/eval/test_dataset_manifests.py
# 5 passed

PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src /Users/jtm427/Desktop/workplace/data/semantic-data-context/.venv/bin/python -m pytest -q tests/eval/test_file_corpus_benchmarks.py
# 6 passed in 40.61s

PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src /Users/jtm427/Desktop/workplace/data/semantic-data-context/.venv/bin/python -m pytest -q tests/mcp/test_tools.py
# 6 passed in 0.81s

PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src /Users/jtm427/Desktop/workplace/data/semantic-data-context/.venv/bin/python -m pytest -q tests/mcp/test_search_context.py tests/eval/test_eval_runner.py
# 24 passed, 1 skipped in 10.52s

PYTHONPATH=packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src /Users/jtm427/Desktop/workplace/data/semantic-data-context/.venv/bin/python -m pytest -q tests/mcp/test_search_context.py tests/registry/test_vdb_backend.py
# 22 passed, 1 skipped in 0.95s
```

No-silent-fallback status remains unchanged:

- `query_understanding` is still returned for semantic-gold retrieval cases.
- Explicit Weaviate failure remains explicit and does not silently downgrade to keyword search.
- Unknown or low-confidence domain phrases continue to surface warnings instead of fabricated hits.

Remaining risk summary:

- live Weaviate recall quality still depends on optional external configuration
- other domains remain pack-driven and need their own verified alias/term/metric coverage
- fixture metadata is test-only synthetic data and not approved product truth
