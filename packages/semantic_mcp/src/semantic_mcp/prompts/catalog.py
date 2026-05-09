"""Small deterministic prompt catalog for MCP prompt registration.

Prompt text is intentionally static and transparent: tools/resources supply the
Semantic Pack facts, while the prompt only states safe answer boundaries.
"""

from __future__ import annotations

PROMPTS = {
    "answer_with_semantic_pack": {
        "name": "answer_with_semantic_pack",
        "description": "Answer using only supplied Semantic Pack context and validation-only SQL planning.",
        "template": (
            "Use the provided Semantic Pack context as the source of truth. "
            "Do not expose blocked PII columns, do not execute SQL, and state any ambiguity before answering."
        ),
    }
}


def get_prompt(name: str) -> dict[str, str]:
    """Return a named prompt definition without hidden dynamic behavior."""

    try:
        return dict(PROMPTS[name])
    except KeyError as exc:
        raise ValueError(f"Unknown prompt: {name}") from exc
