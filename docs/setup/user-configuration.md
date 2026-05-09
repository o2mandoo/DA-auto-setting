# User Configuration Guardrails

This project intentionally keeps user configuration narrow and explicit.

## Required rules

1. **No silent fallback**
   - If a backend, adapter, or runtime dependency is requested but unavailable, fail with an explicit configuration/dependency error.
   - Do not hide the failure by switching to another backend automatically.

2. **No raw PII in configuration**
   - Do not place raw email addresses, phone numbers, customer names, or other identifying values into config files, examples, or prompts.
   - If an example needs a value, use a safe placeholder like `user@example.com` only when the surrounding doc makes it clear the value is illustrative and not real data.

3. **Explicit backend selection**
   - Users must choose the backend they want.
   - A Weaviate request should only run when Weaviate is explicitly configured and available.

## Practical examples

- Good: `backend: keyword`
- Good: `backend: weaviate` with a fully configured Weaviate endpoint
- Bad: asking for Weaviate and then silently using keyword search instead
- Bad: pasting real customer data into a config sample

## Related docs

- `docs/setup/README.md`
- `docs/execution/SECURITY_CHECKLIST.md`
- `docs/execution/RETRIEVAL_LAYER.md`
