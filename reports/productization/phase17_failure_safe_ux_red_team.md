# Phase 17 — Failure-Safe UX + Red-Team Product Scenarios

Passed: 10/10

- PASS `scenario.ambiguity.generic_revenue`: expected `clarification_required`, observed `clarification_required`
- PASS `scenario.pii.email`: expected `pii_blocked`, observed `pii_blocked`
- PASS `scenario.baseline.wrong_new_customer_date`: expected `clarification_required`, observed `clarification_required`
- PASS `scenario.baseline.misses_net_revenue_deductions`: expected `clarification_required`, observed `clarification_required`
- PASS `scenario.unsafe.delete`: expected `unsafe_sql_blocked`, observed `unsafe_sql_blocked`
- PASS `scenario.unsafe.multi_statement`: expected `unsafe_sql_blocked`, observed `unsafe_sql_blocked`
- PASS `scenario.missing.business_term`: expected `missing_semantic_context`, observed `missing_semantic_context`
- PASS `scenario.draft.metric`: expected `draft_metric_warning`, observed `draft_metric_warning`
- PASS `scenario.conflicting.metrics`: expected `clarification_required`, observed `clarification_required`
- PASS `scenario.preview.unavailable`: expected `unsafe_sql_blocked`, observed `unsafe_sql_blocked`
