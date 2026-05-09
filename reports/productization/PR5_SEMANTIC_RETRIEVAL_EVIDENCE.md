# PR-5 Semantic Retrieval Evidence

## Verdict

PASS. PR-5 was executed after verifying that both local live database fixture targets contain the same 20-dataset Sinagong corpus with test-only synthetic table/column metadata.

## Precheck: PostgreSQL/MySQL 20-dataset fixture corpus

Command rerun before retrieval hardening:

```bash
export SEMANTIC_CONTEXT_FIXTURE_DB=1
PYTHONPATH=packages/semantic_contracts:packages/semantic_registry:packages/semantic_mcp/src:packages/semantic_builder/src:. .venv/bin/python -m experiments.db_fixtures.scripts.sinagong_corpus_live_evidence \
  --postgres-dsn postgresql://sdc_fixture:sdc_fixture_pw@localhost:55432/semantic_fixture_postgres_scope_c \
  --mysql-dsn mysql://sdc_fixture:sdc_fixture_pw@localhost:33306/semantic_fixture_mysql_scope_c \
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

## No-silent-fallback log

- Live DB corpus precheck was rerun successfully. The earlier PostgreSQL/MySQL fixture issues were fixed before PR-5 and did not recur.
- A team-mode attempt for PR-5 drifted into a generic decomposition. It was explicitly stopped, and only aligned no-silent-fallback/team changes already merged in the repo were kept. Retrieval hardening was completed under direct leader control.
- Full test execution regenerated final benchmark summary artifacts as a side effect; those unrelated generated reports were restored to avoid silently broadening PR-5 scope.

## Remaining risks

- Live Weaviate remains optional unless `SEMANTIC_WEAVIATE_*` is configured; fake backend coverage proves mode/filter forwarding but not live recall quality.
- Domain-specific synonym coverage is currently pack-driven. Other domains will need generated or confirmed pack aliases/terms before retrieval can behave as richly as the demo revenue pack.
- The 20-dataset DB fixture metadata is intentionally synthetic and test-only; it validates environment readiness, not semantic truth quality.
