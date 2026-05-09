from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry.retrieval import (  # noqa: E402
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
    EmbeddingSafetyError,
    LocalEmbeddingConfig,
    LocalEmbeddingProvider,
    LocalEmbeddingProviderUnavailable,
)


class EmbeddingProviderTest(unittest.TestCase):
    def test_deterministic_provider_is_stable_normalized_and_protocol_compatible(self) -> None:
        provider = DeterministicEmbeddingProvider(dimensions=12)

        first = provider.embed_query("metric.net_revenue 순매출")
        second = provider.embed_texts(["metric.net_revenue 순매출"])[0]

        self.assertIsInstance(provider, EmbeddingProvider)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 12)
        self.assertAlmostEqual(math.sqrt(sum(value * value for value in first)), 1.0, places=6)

    def test_blank_text_returns_zero_vector(self) -> None:
        provider = DeterministicEmbeddingProvider(dimensions=4)

        self.assertEqual(provider.embed_query("   "), [0.0, 0.0, 0.0, 0.0])

    def test_rejects_raw_pii_before_embedding(self) -> None:
        provider = DeterministicEmbeddingProvider()

        with self.assertRaisesRegex(EmbeddingSafetyError, "email"):
            provider.embed_query("customer alice@example.com")
        with self.assertRaisesRegex(EmbeddingSafetyError, "phone"):
            provider.embed_texts(["call +1-415-555-0100"])

    def test_local_provider_missing_dependency_or_model_is_explicit_not_fallback(self) -> None:
        try:
            provider = LocalEmbeddingProvider(LocalEmbeddingConfig(model_name="missing-local-model-for-contract-test"))
        except LocalEmbeddingProviderUnavailable as exc:
            self.assertIn("local", str(exc).casefold())
            return

        # If a developer happens to have a model with this name locally, the
        # provider must still behave as a local provider and keep the PII guard.
        with self.assertRaises(EmbeddingSafetyError):
            provider.embed_query("alice@example.com")

    def test_invalid_dimensions_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "dimensions"):
            DeterministicEmbeddingProvider(dimensions=0)


if __name__ == "__main__":
    unittest.main()
