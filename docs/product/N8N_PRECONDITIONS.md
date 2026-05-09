# n8n Preconditions

n8n is an orchestration/demo layer. It must call stable local product APIs and must not duplicate core product logic.

## Required before importing n8n workflows

- Product API endpoint contracts are documented under `docs/api/`.
- Demo auth/header strategy is documented and uses placeholders only.
- Onboarding, confirmation, pack promotion, query answer, comparison, evaluation, and failure review endpoints have example payloads.
- Safety gates are visible in every workflow that can reach SQL text.
- Workflow JSON contains no credentials, no raw PII samples, and no production connection strings.

## n8n boundaries

- n8n may trigger scans, confirmations, benchmark runs, and demos.
- n8n must not be source of truth for Semantic Packs.
- n8n must not execute SQL directly.
- n8n must not implement fallback routing that hides backend/provider failures.
