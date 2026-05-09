# Phase 8 Leader Evaluation — Domain-Aware Query Runtime

## Evaluation method

Ouroboros MCP evaluate was not directly available via ToolSearch in this tool list, so I used the explicit fallback: local mechanical verification plus semantic acceptance review.

Two initial leader probes failed due to MCP function signature assumptions, not code behavior:
- `validate_sql` does not accept `pack_id`; it uses `space_id`/legacy positional style.
- `validate_sql` requires SQL as the first positional argument or `(space_id, sql)` positional form.
The probe was corrected to `validate_sql('demo_company.revenue', 'SELECT users.email FROM users', ...)` and passed.

## Verdict

PASS.

## Stage 1 — Mechanical verification

Evidence under `runtime/phase8_leader_eval/`:

- targeted Phase 8/MCP tests: PASS, 36 tests.
- full pytest suite: PASS, 160 tests.
- contracts unittest: PASS, 20 tests.
- compileall: PASS.
- fixed Phase 8 probe: PASS.
- forbidden scan: PASS, no execute_query/preview_query definitions or calls.

## Stage 2 — Semantic acceptance review

PASS against Phase 8 requirements:

1. Runtime pipeline models exist.
2. Ambiguity gate blocks hard ambiguity and keeps `execution_allowed=false`.
3. Query planner uses Semantic Pack cards.
4. Verified/template path is represented and tested.
5. Draft metrics generate warnings.
6. Policy verifier blocks forbidden columns such as `users.email` for `marketing_analyst`.
7. Semantic verifier checks date basis/business-term consistency.
8. MCP runtime tools return structured outputs.
9. No SQL execution or preview execution was introduced.
10. Tests cover golden/red-team-like cases through registry/MCP test suites.

## Whether Phase 9 may start

Yes. Phase 9 may start after team shutdown.
