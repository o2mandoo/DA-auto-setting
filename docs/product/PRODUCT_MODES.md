# Product Modes

Semantic Data Context System exposes four product modes. These modes are deliberately contracts first: every mode uses the Semantic Pack as source of truth and every SQL surface is validation-first.

## Mode A — Onboarding / Builder

- Purpose: scan files or approved test database fixtures and create draft Semantic Pack proposals.
- Inputs: file scans, safe PostgreSQL fixture metadata, column profiles, reverse questions.
- Outputs: `semantic_pack.draft.yaml`, proposal records, confirmation questions.
- Guardrails: no raw PII values, no automatic promotion to approved packs, no hidden LLM/provider fallback.

## Mode B — Registry / Confirmation

- Purpose: manage packs, terms, metrics, policies, verified queries, proposals, confirmations, and feedback.
- Inputs: approved or draft Semantic Packs plus human confirmation records.
- Outputs: pack search, term resolution, promotion evidence, feedback JSONL.
- Guardrails: Semantic Pack remains source of truth; confirmations create auditable records and do not silently mutate approved packs.

## Mode C — Query Runtime / Answer Comparison

- Purpose: compare a generic physical-schema-only baseline SQL draft with a Semantic Pack powered system SQL draft.
- Inputs: user question, role, semantic space, physical schema snapshot.
- Outputs: side-by-side SQL panels, semantic differences, policy/safety verdicts, optional safe preview status.
- Guardrails: baseline is never executed; system SQL is validated before any local preview; production execution is absent.

## Mode D — Benchmark / Evidence

- Purpose: run repeatable evidence across the demo pack and domain datasets.
- Inputs: golden questions, red-team cases, dataset manifests, retrieval backend configuration including Weaviate when explicitly enabled.
- Outputs: domain evidence summaries, capability matrix, failure patterns, readiness narrative.
- Guardrails: missing evidence is reported as missing, not inferred; retrieval backend errors are explicit and not silently downgraded.

## Cross-mode invariants

- No production SQL execution path.
- No raw PII values in prompts, logs, preview artifacts, or reports.
- No silent fallback after an explicit provider/backend is selected.
- n8n may orchestrate demos, but core validation, planning, comparison, promotion, and safety rules remain in this repo.
