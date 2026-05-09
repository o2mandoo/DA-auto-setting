# Failure-Safe UX Specification

Failure-safe UX means the product explains why it cannot safely answer and what the next action should be.

## Required states

- `clarification_required`: the question is semantically ambiguous.
- `policy_blocked`: the user's role is not allowed to access the requested context.
- `pii_blocked`: the SQL or requested output includes blocked PII columns.
- `unsafe_sql_blocked`: SQL is non-SELECT, multi-statement, or otherwise unsafe.
- `missing_semantic_context`: no pack card can define the requested term/metric.
- `draft_metric_warning`: only draft or unconfirmed semantic cards are available.
- `retrieval_miss`: retrieval backend returned no usable context.
- `parser_uncertain`: SQL profiling could not confidently identify tables/columns.
- `preview_unavailable`: safe local preview cannot be performed.

## No silent fallback rule

If a requested backend, provider, parser, preview target, or workflow step cannot run, the response must include the failing component, reason, and selected recovery action. Default offline mock behavior is allowed only when the caller did not explicitly request a concrete provider/backend.
