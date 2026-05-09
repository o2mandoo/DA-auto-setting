from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry.retrieval import WeaviateSearchBackend, WeaviateUnavailableError  # noqa: E402


class WeaviateLiveOptionalTest(unittest.TestCase):
    def test_explicit_live_weaviate_selection_remains_optional_but_non_fallback(self) -> None:
        enabled = os.environ.get("SEMANTIC_WEAVIATE_ENABLED")
        url = os.environ.get("SEMANTIC_WEAVIATE_URL")
        collection_name = os.environ.get("SEMANTIC_WEAVIATE_COLLECTION")
        api_key = os.environ.get("SEMANTIC_WEAVIATE_API_KEY")
        if enabled != "1" or not url or not collection_name or not api_key:
            self.skipTest("SEMANTIC_WEAVIATE_ENABLED/URL/COLLECTION/API_KEY are not set; live Weaviate test is optional")

        try:
            import weaviate
            from weaviate.classes.init import Auth
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on the optional live env.
            self.skipTest(f"weaviate client is unavailable: {exc}")

        query_mode = str(os.environ.get("SEMANTIC_WEAVIATE_QUERY_MODE", "hybrid")).strip().casefold()
        query_vector_raw = os.environ.get("SEMANTIC_WEAVIATE_QUERY_VECTOR")
        query_vector = json.loads(query_vector_raw) if query_vector_raw else None
        if query_mode == "near_vector" and query_vector is None:
            self.skipTest("SEMANTIC_WEAVIATE_QUERY_VECTOR is required for near_vector live tests")

        client = weaviate.connect_to_weaviate_cloud(
            cluster_url=url,
            auth_credentials=Auth.api_key(api_key),
        )
        try:
            collection = client.collections.use(collection_name)
            backend = WeaviateSearchBackend(collection=collection)
            results = backend.search(
                "순매출",
                filters={"card_type": "metric"},
                limit=3,
                query_mode=query_mode,
                query_vector=query_vector,
            )
        except WeaviateUnavailableError as exc:
            self.fail(f"Live Weaviate selection failed explicitly: {exc}")
        finally:
            client.close()

        self.assertGreater(len(results), 0)
        self.assertTrue(all(result.doc_id for result in results))
        self.assertTrue(any(result.metadata.get("card_type") == "metric" for result in results))


if __name__ == "__main__":
    unittest.main()
