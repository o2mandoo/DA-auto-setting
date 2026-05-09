from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry import PackStore  # noqa: E402
from semantic_registry.retrieval import (  # noqa: E402
    KeywordSearchBackend,
    SearchDocument,
    WeaviateSearchBackend,
    WeaviateUnavailableError,
)


class SearchBackendTest(unittest.TestCase):
    def test_keyword_backend_searches_text_and_applies_metadata_filters(self) -> None:
        backend = KeywordSearchBackend([
            SearchDocument(
                doc_id="metric.net_revenue",
                title="순매출",
                text="Gross payment amount minus refunds and discounts.",
                metadata={"card_type": "metric", "space_id": "revenue", "roles": ["finance"]},
            ),
            SearchDocument(
                doc_id="term.new_customer",
                title="신규 고객",
                text="A user whose first successful payment timestamp falls within the analysis period.",
                metadata={"card_type": "business_term", "space_id": "revenue", "roles": ["marketing"]},
            ),
        ])

        metric_results = backend.search("refunds", filters={"card_type": "metric"})
        self.assertEqual([result.doc_id for result in metric_results], ["metric.net_revenue"])

        role_results = backend.search("payment", filters={"roles": "marketing"})
        self.assertEqual([result.doc_id for result in role_results], ["term.new_customer"])

    def test_keyword_backend_does_not_search_metadata_values(self) -> None:
        backend = KeywordSearchBackend([
            SearchDocument(
                doc_id="policy.safe",
                title="Safe policy",
                text="Aggregated revenue analysis is allowed.",
                metadata={"blocked_columns": ["users.email", "users.phone", "users.name"]},
            )
        ])

        # Metadata supports filters but is intentionally not part of the keyword
        # haystack; blocked-column names should not become accidental search hits.
        self.assertEqual(backend.search("users.email"), [])
        self.assertEqual(
            [result.doc_id for result in backend.search("revenue", filters={"blocked_columns": "users.email"})],
            ["policy.safe"],
        )

    def test_keyword_backend_indexes_pack_and_supports_required_filters(self) -> None:
        pack = PackStore(ROOT / "semantic_packs").load_pack("demo_company.revenue")
        backend = KeywordSearchBackend()
        backend.index_pack(pack)

        metric_results = backend.search(
            "순매출",
            card_types=["metrics"],
            filters={"pack_id": "demo_company.revenue", "space_id": "revenue", "status": "draft"},
        )
        self.assertEqual(metric_results[0].doc_id, "metric.net_revenue")
        self.assertEqual(metric_results[0].metadata["card_type"], "metric")
        self.assertEqual(metric_results[0].metadata["source_path"], "semantic_pack.metric.metric.net_revenue")

        role_results = backend.search(
            "revenue",
            card_types=["policy"],
            filters={"allowed_role": "marketing_analyst"},
        )
        self.assertEqual([result.doc_id for result in role_results], ["policy.marketing_safe_revenue"])

    def test_keyword_backend_applies_extended_metadata_filters(self) -> None:
        backend = KeywordSearchBackend([
            SearchDocument(
                doc_id="policy.marketing_safe_revenue",
                title="Revenue policy",
                text="Aggregated revenue analysis is allowed.",
                metadata={
                    "dataset_id": "demo_company.revenue",
                    "domain": "revenue",
                    "pack_id": "demo_company.revenue",
                    "space_id": "revenue",
                    "card_type": "policy",
                    "source_path": "semantic_pack.policy.policy.marketing_safe_revenue",
                    "status": "approved",
                    "allowed_roles": ["marketing_analyst"],
                    "blocked_columns": ["users.email"],
                },
            ),
            SearchDocument(
                doc_id="metric.net_revenue",
                title="순매출",
                text="Gross payment amount minus refunds.",
                metadata={
                    "dataset_id": "demo_company.revenue",
                    "domain": "revenue",
                    "pack_id": "demo_company.revenue",
                    "space_id": "revenue",
                    "card_type": "metric",
                    "source_path": "semantic_pack.metric.metric.net_revenue",
                    "status": "draft",
                },
            ),
        ])

        results = backend.search(
            "revenue",
            filters={
                "dataset_id": "demo_company.revenue",
                "domain": "revenue",
                "pack_id": "demo_company.revenue",
                "space_id": "revenue",
                "card_type": "policy",
                "source_path": "semantic_pack.policy.policy.marketing_safe_revenue",
                "status": "approved",
                "allowed_roles": "marketing_analyst",
                "blocked_columns": "users.email",
            },
        )

        self.assertEqual([result.doc_id for result in results], ["policy.marketing_safe_revenue"])
        self.assertEqual(results[0].metadata["space_id"], "revenue")
        self.assertEqual(results[0].metadata["status"], "approved")

    def test_search_document_rejects_raw_pii_text_and_metadata(self) -> None:
        with self.assertRaisesRegex(ValueError, "raw PII-like"):
            SearchDocument(doc_id="bad.email", text="customer jane@example.com")

        with self.assertRaisesRegex(ValueError, "must not store raw values"):
            SearchDocument(doc_id="bad.raw", text="safe", metadata={"raw_value": "secret"})

    def test_weaviate_backend_requires_explicit_backend_without_keyword_fallback(self) -> None:
        with self.assertRaisesRegex(WeaviateUnavailableError, "keyword fallback is not performed"):
            WeaviateSearchBackend()

    def test_weaviate_backend_uses_collection_and_metadata_filters(self) -> None:
        collection = FakeCollection()
        backend = WeaviateSearchBackend(collection=collection)
        backend.index_documents([
            SearchDocument(
                doc_id="metric.net_revenue",
                title="순매출",
                text="Gross payment amount minus refunds.",
                metadata={"card_type": "metric", "space_id": "revenue"},
            )
        ])

        results = backend.search("refunds", filters={"card_type": "metric"}, limit=3)

        self.assertEqual(collection.inserted[0]["uuid"], "metric.net_revenue")
        self.assertEqual(collection.last_query["query"], "refunds")
        self.assertEqual(collection.last_query["limit"], 3)
        self.assertEqual(collection.last_query["mode"], "hybrid")
        self.assertIn("filters", collection.last_query)
        self.assertEqual(results[0].doc_id, "metric.net_revenue")
        self.assertEqual(results[0].metadata["card_type"], "metric")

    def test_weaviate_backend_rejects_missing_insert_surface_explicitly(self) -> None:
        class NoInsertCollection:
            def __init__(self) -> None:
                self.data = object()

        backend = WeaviateSearchBackend(collection=NoInsertCollection())

        with self.assertRaisesRegex(WeaviateUnavailableError, "data.insert"):
            backend.index_documents([
                SearchDocument(
                    doc_id="metric.net_revenue",
                    title="순매출",
                    text="Gross payment amount minus refunds.",
                    metadata={"card_type": "metric"},
                )
            ])

    def test_weaviate_backend_rejects_missing_query_modes_explicitly(self) -> None:
        class NoHybridCollection:
            def __init__(self) -> None:
                self.query = type("Query", (), {"bm25": lambda self, **kwargs: object()})()

        class NoBm25Collection:
            def __init__(self) -> None:
                self.query = type("Query", (), {"hybrid": lambda self, **kwargs: object()})()

        class NoNearVectorCollection:
            def __init__(self) -> None:
                self.query = type(
                    "Query",
                    (),
                    {
                        "hybrid": lambda self, **kwargs: object(),
                        "bm25": lambda self, **kwargs: object(),
                    },
                )()

        with self.assertRaisesRegex(WeaviateUnavailableError, "query.hybrid"):
            WeaviateSearchBackend(collection=NoHybridCollection()).search("refunds")

        with self.assertRaisesRegex(WeaviateUnavailableError, "query.bm25"):
            WeaviateSearchBackend(collection=NoBm25Collection()).search("refunds", query_mode="bm25")

        with self.assertRaisesRegex(WeaviateUnavailableError, "query.near_vector"):
            WeaviateSearchBackend(collection=NoNearVectorCollection()).search(
                "refunds",
                query_mode="near_vector",
                query_vector=[0.1, 0.2, 0.3],
            )

        with self.assertRaisesRegex(WeaviateUnavailableError, "near_vector search requires an explicit query_vector"):
            WeaviateSearchBackend(collection=NoNearVectorCollection()).search("refunds", query_mode="near_vector")

    def test_weaviate_backend_rejects_unsupported_query_mode_explicitly(self) -> None:
        collection = FakeCollection()
        backend = WeaviateSearchBackend(collection=collection)

        with self.assertRaisesRegex(WeaviateUnavailableError, "Unsupported Weaviate query mode"):
            backend.search("refunds", query_mode="vector_search")

    def test_weaviate_backend_supports_all_query_modes_and_metadata_filters(self) -> None:
        cases = (
            ("hybrid", {}, None),
            ("bm25", {}, None),
            ("near_vector", {"query_vector": [0.1, 0.2, 0.3]}, [0.1, 0.2, 0.3]),
        )

        for query_mode, extra_kwargs, expected_vector in cases:
            with self.subTest(query_mode=query_mode):
                collection = FakeCollection()
                backend = WeaviateSearchBackend(collection=collection)

                results = backend.search(
                    "refunds",
                    filters={"card_type": "metric", "space_id": "revenue"},
                    limit=2,
                    query_mode=query_mode,
                    **extra_kwargs,
                )

                self.assertEqual(collection.last_query["mode"], query_mode)
                self.assertEqual(collection.last_query["limit"], 2)
                self.assertIn("filters", collection.last_query)
                self.assertEqual(collection.last_query["filters"]["conditions"]["card_type"], "metric")
                self.assertEqual(collection.last_query["filters"]["conditions"]["space_id"], "revenue")
                self.assertEqual(results[0].doc_id, "metric.net_revenue")
                self.assertEqual(results[0].metadata["card_type"], "metric")
                if expected_vector is None:
                    self.assertEqual(collection.last_query["query"], "refunds")
                    self.assertNotIn("near_vector", collection.last_query)
                else:
                    self.assertEqual(collection.last_query["near_vector"], expected_vector)


class FakeCollection:
    def __init__(self) -> None:
        self.inserted: list[dict[str, object]] = []
        self.last_query: dict[str, object] = {}
        self.data = self
        self.query = self

    def insert(self, *, properties: dict[str, object], uuid: str) -> None:
        self.inserted.append({"properties": properties, "uuid": uuid})

    def hybrid(self, **kwargs: object) -> object:
        self.last_query = {"mode": "hybrid", **kwargs}
        return self._response()

    def bm25(self, **kwargs: object) -> object:
        self.last_query = {"mode": "bm25", **kwargs}
        return self._response()

    def near_vector(self, **kwargs: object) -> object:
        self.last_query = {"mode": "near_vector", **kwargs}
        return self._response()

    def _response(self) -> object:
        return type(
            "FakeResponse",
            (),
            {
                "objects": [
                    type(
                        "FakeObject",
                        (),
                        {
                            "uuid": "metric.net_revenue",
                            "properties": {
                                "doc_id": "metric.net_revenue",
                                "title": "순매출",
                                "text": "Gross payment amount minus refunds.",
                                "card_type": "metric",
                            },
                            "metadata": type("FakeMetadata", (), {"score": 0.75})(),
                        },
                    )()
                ]
            },
        )()


if __name__ == "__main__":
    unittest.main()
