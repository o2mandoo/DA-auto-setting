# Retrieval Layer

This document defines the Phase 7 retrieval boundary for the Semantic Data Context System.

## Purpose

The retrieval layer turns Semantic Pack cards into PII-safe search documents so the registry and MCP layers can return relevant context without exposing raw source values.

It is intentionally local-first:

- the default offline path is deterministic keyword/card search;
- Weaviate is an explicit backend seam, not a silent fallback;
- query execution is out of scope.

## What is retrievable

Retrieval operates on the same semantic card families used by the registry:

- tables
- columns
- value dictionaries
- metrics
- business terms
- join recipes
- policies
- verified queries
- ambiguity / reverse-question cards

## Safety rules

- Raw PII values must never be indexed, embedded, or surfaced in retrieval payloads.
- Blocked columns such as `users.email`, `users.phone`, and `users.name` stay out of raw-value dictionaries.
- Retrieval documents may carry safe identifiers, statuses, source references, and warnings, but not source rows or unredacted user values.
- If Weaviate is unavailable or unconfigured, the backend must report an explicit error instead of pretending keyword fallback is a successful VDB response.
- If a backend/configuration failure is resolvable within the current task
  scope, fix it and rerun the selected backend before using any fallback/skip
  path. If it is not safely resolvable, report the attempted remediation,
  reason, and evidence.

## Backend contract

The retrieval seam exposes two explicit paths:

1. **Keyword backend**
   - local, deterministic, and safe for offline use
   - used by tests and demo flows when no vector backend is configured

2. **Weaviate backend**
   - requires an explicit client / collection / config
   - may fail with a configuration or dependency error
   - must not auto-switch to keyword search after failure
   - supports explicit query modes: `hybrid`, `bm25`, and `near_vector`
   - metadata filters are passed through as backend-native filters when the caller selects Weaviate explicitly
   - supports explicit `bm25`, `hybrid`, and `near_vector` query modes
   - forwards metadata filters to the selected backend mode

Keyword search remains valid only when the caller explicitly selects the
keyword backend or a test/report labels the run as keyword-only. It is not a
recovery path for a failed explicit Weaviate request.

## Integration points

- `packages/semantic_registry/semantic_registry/cards.py` flattens cards into searchable documents.
- `packages/semantic_registry/semantic_registry/retrieval/**` owns backend seams and PII-safe document validation.
- `packages/semantic_mcp` can expose retrieval results, but does not own backend selection policy.

## Semantic query understanding

Before backend search, the MCP retrieval path now performs a deterministic
Semantic Pack understanding pass.  This is not an LLM call and does not read a
database.  It uses only approved local pack metadata to expose:

- matched business terms and metrics;
- aliases/synonyms that were used for the match;
- verified-query question-pattern matches;
- reverse-question and ambiguity-rule candidates;
- unknown or low-confidence domain phrases such as a customer segment that is
  not defined in the current pack.

The search backend still returns real backend hits only; semantic understanding
is used to explain and rank those hits, not to fabricate unavailable context.
If the domain phrase is unknown, retrieval returns explicit warnings instead of
quietly matching broad generic tokens like `고객`.

Semantic-gold evaluation cases record the same `query_understanding` payload
alongside retrieval metrics such as `recall_at_k`, `mrr`, first-hit rank, and
missing ids.  Those metrics describe retrieval quality; they do not change the
backend truth contract.

Benchmark-only support packs may improve understanding and scoring for curated
evaluation cases, but they are not approved product truth and must not be
treated as a source of operational customer facts.

## Verification reference

The retrieval boundary is verified in Phase 7 with local tests and the phase report:

- `reports/productization/PR5_SEMANTIC_RETRIEVAL_EVIDENCE.md`
- `reports/phases/phase7_vdb_card_index_retrieval.md`
- `reports/benchmarks/weaviate_mode_comparison_report.md`
- `tests/registry/test_card_flattening.py`
- `tests/registry/test_semantic_query.py`
- `tests/registry/test_vdb_backend.py`
- `tests/integration/test_weaviate_live_optional.py`
- `tests/mcp/test_search_context.py`
