# Baseline Comparison Specification

## Objective

Compare generic LLM SQL generation against the Semantic Data Context runtime without giving the generic baseline access to Semantic Pack context.

This is the canonical contract for the baseline-vs-system comparison flow exposed by `compare_baseline_vs_system_sql` and `POST /api/product/compare-sql`.
The baseline side must stay physical-schema-only; if Semantic Pack context is used, that draft is system output and must be compared as such.

## Baseline input contract

Allowed baseline context:

- user question,
- physical table names,
- physical column names,
- physical data types when available,
- dialect label.

Forbidden baseline context:

- business terms,
- metric formulas,
- value dictionaries,
- policies,
- verified queries,
- human confirmations,
- reverse questions,
- Semantic Pack card text.

## Comparison dimensions

- semantic coverage: selected terms, metrics, date basis, filters, join recipes, value dictionaries;
- safety: non-SELECT, multi-statement, blocked PII columns, allowed table policy;
- correctness risk: wrong metric basis, wrong cohort/date basis, missing refund/discount handling, missing business-term conditions;
- product readiness: whether a user-facing state and next action are available.

## Execution boundary

The comparison engine profiles SQL text only. It does not execute baseline SQL and does not bypass SQL Guard for system SQL. Any unknown parser result is a warning or failure, never a quiet pass.
