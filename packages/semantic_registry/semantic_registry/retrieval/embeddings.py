"""Embedding provider seams for Semantic Registry retrieval.

Phase 7 keeps embeddings local and deterministic by default: providers in this
module do not contact SaaS APIs and reject obvious raw PII before any vector is
computed. Higher layers should pass policy-filtered card text, but the guard is
kept here as a final safety boundary for future VDB indexing.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib
import math
import re
from typing import Iterable, Protocol, Sequence, runtime_checkable


_EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
# Conservative phone-like pattern: catches explicit long digit strings with
# phone separators while avoiding ordinary short ids/status codes.
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-\s().]{7,}\d)(?!\d)")


class EmbeddingSafetyError(ValueError):
    """Raised when text appears to contain raw PII that must not be embedded."""


class LocalEmbeddingProviderUnavailable(RuntimeError):
    """Raised when the optional local embedding dependency is not configured."""


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol shared by deterministic tests and optional local embeddings."""

    @property
    def dimensions(self) -> int:
        """Return the vector length emitted by this provider."""

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed already policy-filtered text without external network calls."""

    def embed_query(self, query: str) -> list[float]:
        """Embed a query using the same local policy checks as card text."""


@dataclass(frozen=True)
class DeterministicEmbeddingProvider:
    """Stable hashing-based provider for tests and offline smoke checks.

    This intentionally is not semantic ML. It gives deterministic, normalized
    vectors so retrieval plumbing can be tested without network, model downloads,
    or a local model server.
    """

    dimensions: int = 32
    salt: str = "semantic-registry-deterministic-v1"

    def __post_init__(self) -> None:
        if self.dimensions <= 0:
            raise ValueError("dimensions must be positive")

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return self._embed_one(query)

    def _embed_one(self, text: str) -> list[float]:
        assert_embedding_safe_text(text)
        vector = [0.0] * self.dimensions
        tokens = _tokens(text)
        if not tokens:
            return vector
        for index, token in enumerate(tokens):
            digest = hashlib.sha256(f"{self.salt}:{index}:{token}".encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            # The weight is stable but not content-revealing; token values never
            # leave this local process or get stored by the provider.
            weight = 0.5 + digest[5] / 255.0
            vector[slot] += sign * weight
        return _l2_normalize(vector)


@dataclass(frozen=True)
class LocalEmbeddingConfig:
    """Configuration for an explicitly enabled local sentence-transformer model."""

    model_name: str
    dimensions: int | None = None
    trust_remote_code: bool = False


class LocalEmbeddingProvider:
    """Optional local-only provider backed by an installed sentence-transformer.

    The class imports ``sentence_transformers`` only when constructed. Missing
    dependency or model files are explicit configuration errors; callers must not
    silently fall back to deterministic embeddings for production indexing.
    """

    def __init__(self, config: LocalEmbeddingConfig) -> None:
        if not config.model_name.strip():
            raise ValueError("local embedding model_name is required")
        try:
            module = importlib.import_module("sentence_transformers")
        except ModuleNotFoundError as exc:  # pragma: no cover - exercised without optional dependency.
            raise LocalEmbeddingProviderUnavailable(
                "sentence_transformers is not installed; configure the deterministic provider for tests "
                "or install a local model dependency explicitly"
            ) from exc
        try:
            self._model = module.SentenceTransformer(
                config.model_name,
                trust_remote_code=config.trust_remote_code,
                local_files_only=True,
            )
        except Exception as exc:  # pragma: no cover - depends on local model availability.
            raise LocalEmbeddingProviderUnavailable(
                f"local embedding model {config.model_name!r} is unavailable locally"
            ) from exc
        self._dimensions = config.dimensions or int(self._model.get_sentence_embedding_dimension())

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        for text in texts:
            assert_embedding_safe_text(text)
        vectors = self._model.encode(list(texts), normalize_embeddings=True)
        return [_coerce_vector(vector, expected_dimensions=self._dimensions) for vector in vectors]

    def embed_query(self, query: str) -> list[float]:
        return self.embed_texts([query])[0]


def assert_embedding_safe_text(text: str) -> None:
    """Reject raw PII-like values before local embedding/indexing."""

    if _EMAIL_RE.search(text):
        raise EmbeddingSafetyError("raw email-like values must not be embedded")
    if _PHONE_RE.search(text):
        raise EmbeddingSafetyError("raw phone-like values must not be embedded")


def _tokens(text: str) -> list[str]:
    return [token for token in re.split(r"\W+", text.casefold()) if token]


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _coerce_vector(vector: Iterable[float], *, expected_dimensions: int) -> list[float]:
    coerced = [float(value) for value in vector]
    if len(coerced) != expected_dimensions:
        raise LocalEmbeddingProviderUnavailable(
            f"local embedding dimension mismatch: expected {expected_dimensions}, got {len(coerced)}"
        )
    return coerced
