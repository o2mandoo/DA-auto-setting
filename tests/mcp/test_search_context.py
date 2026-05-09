from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_mcp" / "src"))

from semantic_mcp import search_semantic_context  # noqa: E402


class SearchContextToolTests(unittest.TestCase):
    def test_keyword_backend_returns_structured_results_and_marks_drafts(self) -> None:
        response = search_semantic_context(
            "demo_company.revenue",
            "revenue",
            filters={
                "backend": "keyword",
                "limit": 5,
                "pack_id": "demo_company.revenue",
                "space_id": "revenue",
                "card_type": "policy",
                "status": "approved",
                "source_path": "semantic_pack.policy.policy.marketing_safe_revenue",
            },
            root=ROOT / "semantic_packs",
        )

        self.assertEqual(response["backend"], "keyword")
        self.assertEqual(response["query_mode"], "keyword")
        self.assertEqual(
            response["filters_applied"],
            {
                "pack_id": "demo_company.revenue",
                "space_id": "revenue",
                "card_type": "policy",
                "status": "approved",
                "source_path": "semantic_pack.policy.policy.marketing_safe_revenue",
            },
        )
        self.assertFalse(response["fallback_used"])
        by_id = {item["card_id"]: item for item in response["results"]}
        self.assertEqual(list(by_id), ["policy.marketing_safe_revenue"])
        result = by_id["policy.marketing_safe_revenue"]
        self.assertIn("summary", result)
        self.assertIn("source_uri", result)
        self.assertEqual(result["status"], "approved")
        self.assertNotIn("draft_card", result["warnings"])
        self.assertLessEqual(result["score"], 1.0)
        self.assertIsNone(response["error"])

    def test_weaviate_backend_without_config_is_explicit_error_not_keyword_fallback(self) -> None:
        response = search_semantic_context(
            "demo_company.revenue",
            "순매출",
            filters={"backend": "weaviate", "limit": 3},
            root=ROOT / "semantic_packs",
        )

        self.assertEqual(response["backend"], "weaviate")
        self.assertEqual(response["query_mode"], "hybrid")
        self.assertEqual(response["filters_applied"], {})
        self.assertFalse(response["fallback_used"])
        self.assertEqual(response["results"], [])
        self.assertEqual(response["error"]["code"], "backend_configuration_error")
        self.assertEqual(response["error"]["backend"], "weaviate")
        self.assertEqual(response["error"]["query_mode"], "hybrid")
        self.assertEqual(response["error"]["filters_applied"], {})
        self.assertTrue(any("no keyword fallback" in warning for warning in response["warnings"]))
        self.assertFalse(response["fallback_used"])

    def test_keyword_backend_without_adapter_fails_closed_instead_of_falling_back(self) -> None:
        with patch("semantic_mcp.tools.search_context._optional_keyword_backend", return_value=None):
            response = search_semantic_context(
                "demo_company.revenue",
                "순매출",
                filters={"backend": "keyword", "limit": 3},
                root=ROOT / "semantic_packs",
            )

        self.assertEqual(response["backend"], "keyword")
        self.assertEqual(response["query_mode"], "keyword")
        self.assertFalse(response["fallback_used"])
        self.assertEqual(response["results"], [])
        self.assertEqual(response["error"]["code"], "backend_configuration_error")
        self.assertTrue(any("no keyword fallback" in warning for warning in response["warnings"]))

    def test_email_query_does_not_expose_raw_email_values(self) -> None:
        response = search_semantic_context(
            "demo_company.revenue",
            "email",
            filters={"backend": "keyword", "limit": 10},
            root=ROOT / "semantic_packs",
        )

        rendered = repr(response)
        self.assertNotIn("@", rendered)
        self.assertTrue(all("warnings" in item for item in response["results"]))

    def test_weaviate_live_env_is_optional_but_explicit_when_configured(self) -> None:
        enabled = os.environ.get("SEMANTIC_WEAVIATE_ENABLED")
        url = os.environ.get("SEMANTIC_WEAVIATE_URL")
        collection = os.environ.get("SEMANTIC_WEAVIATE_COLLECTION")
        if enabled != "1" or not url or not collection:
            self.skipTest("SEMANTIC_WEAVIATE_ENABLED/URL/COLLECTION are not set; live Weaviate test is optional")

        backend_config = {
            "url": url,
            "collection_name": collection,
            "query_mode": os.environ.get("SEMANTIC_WEAVIATE_QUERY_MODE", "hybrid"),
        }
        api_key = os.environ.get("SEMANTIC_WEAVIATE_API_KEY")
        if api_key:
            backend_config["api_key"] = api_key

        response = search_semantic_context(
            "demo_company.revenue",
            "순매출",
            filters={"backend": "weaviate", "backend_config": backend_config, "limit": 3},
            root=ROOT / "semantic_packs",
        )

        self.assertFalse(response["fallback_used"])
        if response.get("error"):
            self.fail(f"Live Weaviate selection failed explicitly: {response['error']['message']}")
        self.assertEqual(response["backend"], "weaviate")
        self.assertEqual(response["query_mode"], str(backend_config["query_mode"]).lower())
        self.assertGreater(len(response["results"]), 0)
        self.assertTrue(all("source_uri" in item for item in response["results"]))
        self.assertIsNone(response["error"])

    def test_weaviate_query_mode_and_filters_are_forwarded_when_supported(self) -> None:
        seen: dict[str, object] = {}

        class FakeWeaviateBackend:
            def __init__(self, collection_name: str = "SemanticCards", **kwargs: object) -> None:
                seen["collection_name"] = collection_name
                seen["init_kwargs"] = kwargs

            def index_pack(self, pack: object) -> None:
                seen.setdefault("indexed_packs", 0)
                seen["indexed_packs"] = int(seen["indexed_packs"]) + 1

            def search(
                self,
                query: str,
                *,
                card_types: list[str],
                limit: int,
                filters: dict[str, object],
                query_mode: str | None = None,
                query_vector: list[float] | None = None,
            ) -> list[dict[str, object]]:
                seen["query"] = query
                seen["card_types"] = card_types
                seen["limit"] = limit
                seen["filters"] = dict(filters)
                seen["query_mode"] = query_mode
                seen["query_vector"] = query_vector
                return [
                    {
                        "card_id": "metric.net_revenue",
                        "card_type": "metric",
                        "score": 0.9,
                        "summary": "Net revenue metric",
                        "status": "draft",
                    }
                ]

        with patch("semantic_mcp.tools.search_context._optional_weaviate_backend", return_value=FakeWeaviateBackend):
            response = search_semantic_context(
                "demo_company.revenue",
                "순매출",
                filters={
                    "backend": "weaviate",
                    "backend_config": {"collection_name": "SemanticCardsTest", "query_mode": "bm25"},
                    "dataset_id": "demo_company.revenue",
                    "domain": "revenue",
                    "pack_id": "demo_company.revenue",
                    "space_id": "revenue",
                    "card_type": "policy",
                    "source_path": "semantic_pack.policy.policy.marketing_safe_revenue",
                    "status": "approved",
                    "limit": 1,
                },
                root=ROOT / "semantic_packs",
            )

        self.assertEqual(response["backend"], "weaviate")
        self.assertEqual(response["query_mode"], "bm25")
        self.assertEqual(
            response["filters_applied"],
            {
                "dataset_id": "demo_company.revenue",
                "domain": "revenue",
                "pack_id": "demo_company.revenue",
                "space_id": "revenue",
                "card_type": "policy",
                "source_path": "semantic_pack.policy.policy.marketing_safe_revenue",
                "status": "approved",
            },
        )
        self.assertFalse(response["fallback_used"])
        self.assertIsNone(response["error"])
        self.assertEqual(seen["collection_name"], "SemanticCardsTest")
        self.assertEqual(seen["query_mode"], "bm25")
        self.assertEqual(
            seen["filters"],
            {
                "dataset_id": "demo_company.revenue",
                "domain": "revenue",
                "pack_id": "demo_company.revenue",
                "space_id": "revenue",
                "card_type": "policy",
                "source_path": "semantic_pack.policy.policy.marketing_safe_revenue",
                "status": "approved",
            },
        )
        self.assertEqual(seen["limit"], 1)
        self.assertIsNone(seen["query_vector"])
        self.assertEqual(response["results"][0]["card_id"], "metric.net_revenue")
        self.assertIn("source_uri", response["results"][0])

    def test_weaviate_hybrid_mode_and_filters_are_forwarded_when_supported(self) -> None:
        seen: dict[str, object] = {}

        class FakeWeaviateBackend:
            def __init__(self, collection_name: str = "SemanticCards", **kwargs: object) -> None:
                seen["collection_name"] = collection_name
                seen["init_kwargs"] = kwargs

            def index_pack(self, pack: object) -> None:
                seen.setdefault("indexed_packs", 0)
                seen["indexed_packs"] = int(seen["indexed_packs"]) + 1

            def search(
                self,
                query: str,
                *,
                card_types: list[str],
                limit: int,
                filters: dict[str, object],
                query_mode: str | None = None,
                query_vector: list[float] | None = None,
            ) -> list[dict[str, object]]:
                seen["query"] = query
                seen["card_types"] = card_types
                seen["limit"] = limit
                seen["filters"] = dict(filters)
                seen["query_mode"] = query_mode
                seen["query_vector"] = query_vector
                return [
                    {
                        "card_id": "metric.net_revenue",
                        "card_type": "metric",
                        "score": 0.9,
                        "summary": "Net revenue metric",
                        "status": "draft",
                    }
                ]

        with patch("semantic_mcp.tools.search_context._optional_weaviate_backend", return_value=FakeWeaviateBackend):
            response = search_semantic_context(
                "demo_company.revenue",
                "순매출",
                filters={
                    "backend": "weaviate",
                    "backend_config": {"collection_name": "SemanticCardsTest", "query_mode": "hybrid"},
                    "domain": "sales",
                    "limit": 1,
                },
                root=ROOT / "semantic_packs",
            )

        self.assertEqual(response["backend"], "weaviate")
        self.assertEqual(response["query_mode"], "hybrid")
        self.assertEqual(response["filters_applied"], {"domain": "sales"})
        self.assertFalse(response["fallback_used"])
        self.assertEqual(seen["collection_name"], "SemanticCardsTest")
        self.assertEqual(seen["query_mode"], "hybrid")
        self.assertEqual(seen["filters"], {"domain": "sales"})
        self.assertEqual(seen["limit"], 1)
        self.assertIsNone(seen["query_vector"])
        self.assertEqual(response["results"][0]["card_id"], "metric.net_revenue")
        self.assertIn("source_uri", response["results"][0])

    def test_weaviate_near_vector_mode_and_query_vector_are_forwarded_when_supported(self) -> None:
        seen: dict[str, object] = {}

        class FakeWeaviateBackend:
            def __init__(self, collection_name: str = "SemanticCards", **kwargs: object) -> None:
                seen["collection_name"] = collection_name
                seen["init_kwargs"] = kwargs

            def index_pack(self, pack: object) -> None:
                seen.setdefault("indexed_packs", 0)
                seen["indexed_packs"] = int(seen["indexed_packs"]) + 1

            def search(
                self,
                query: str,
                *,
                card_types: list[str],
                limit: int,
                filters: dict[str, object],
                query_mode: str | None = None,
                query_vector: list[float] | None = None,
            ) -> list[dict[str, object]]:
                seen["query"] = query
                seen["card_types"] = card_types
                seen["limit"] = limit
                seen["filters"] = dict(filters)
                seen["query_mode"] = query_mode
                seen["query_vector"] = query_vector
                return [
                    {
                        "card_id": "metric.net_revenue",
                        "card_type": "metric",
                        "score": 0.9,
                        "summary": "Net revenue metric",
                        "status": "draft",
                    }
                ]

        with patch("semantic_mcp.tools.search_context._optional_weaviate_backend", return_value=FakeWeaviateBackend):
            response = search_semantic_context(
                "demo_company.revenue",
                "순매출",
                filters={
                    "backend": "weaviate",
                    "backend_config": {
                        "collection_name": "SemanticCardsTest",
                        "query_mode": "near_vector",
                        "query_vector": [0.12, 0.34, 0.56],
                    },
                    "domain": "sales",
                    "limit": 1,
                },
                root=ROOT / "semantic_packs",
            )

        self.assertEqual(response["backend"], "weaviate")
        self.assertEqual(response["query_mode"], "near_vector")
        self.assertEqual(response["filters_applied"], {"domain": "sales"})
        self.assertFalse(response["fallback_used"])
        self.assertIsNone(response["error"])
        self.assertEqual(seen["collection_name"], "SemanticCardsTest")
        self.assertEqual(seen["query_mode"], "near_vector")
        self.assertEqual(seen["query_vector"], [0.12, 0.34, 0.56])
        self.assertEqual(seen["filters"], {"domain": "sales"})
        self.assertEqual(seen["limit"], 1)
        self.assertEqual(response["results"][0]["card_id"], "metric.net_revenue")
        self.assertIn("source_uri", response["results"][0])

    def test_weaviate_mode_comparison_report_lists_all_three_modes(self) -> None:
        report_path = ROOT / "reports" / "benchmarks" / "weaviate_mode_comparison_report.md"
        text = report_path.read_text()
        self.assertIn("`bm25`", text)
        self.assertIn("`hybrid`", text)
        self.assertIn("`near_vector`", text)
        self.assertIn("Deterministic fake backend", text)
        self.assertIn("Live skip path", text)
        self.assertIn("dataset_id", text)
        self.assertIn("allowed_roles", text)


if __name__ == "__main__":
    unittest.main()
