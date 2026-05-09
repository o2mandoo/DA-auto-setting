from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from semantic_mcp.resources import (
    SEMANTIC_PACK_BY_ID_URI_PREFIX,
    SEMANTIC_PACK_RESOURCE_URI,
    SEMANTIC_PACK_TERMS_URI_SUFFIX,
    SEMANTIC_PACK_METRICS_URI_SUFFIX,
    SEMANTIC_PACK_POLICIES_URI_SUFFIX,
    SEMANTIC_PACK_VERIFIED_QUERIES_URI_SUFFIX,
    build_pack_resource,
    build_packs_resource,
    build_pack_metrics_resource,
    build_pack_terms_resource,
    get_pack_policies,
    get_pack_verified_queries,
    semantic_pack_resource_uris,
    semantic_pack_metrics_resource_uris,
    semantic_pack_terms_resource_uris,
    semantic_pack_resources,
)
from semantic_registry.store import DEFAULT_PACK_ROOT, PackStore


def _make_temp_root_with_demo_pack(tmp_root: Path) -> None:
    source_pack = Path(DEFAULT_PACK_ROOT) / "demo_company" / "revenue.v0_1.yaml"
    assert source_pack.exists()
    target_root = tmp_root / "semantic_packs" / "demo_company"
    target_root.mkdir(parents=True)
    target_file = target_root / "revenue.v0_1.yaml"
    target_file.write_text(source_pack.read_text(encoding="utf-8"), encoding="utf-8")


class SemanticPackResourceTests(unittest.TestCase):
    def test_semantic_packs_resource_uses_expected_uri(self) -> None:
        payload = build_packs_resource()
        self.assertEqual(payload["uri"], SEMANTIC_PACK_RESOURCE_URI)
        self.assertIn("count", payload)
        self.assertIn("spaces", payload)

    def test_semantic_pack_resources_returns_uri_map(self) -> None:
        mapping = semantic_pack_resources()
        self.assertIn(SEMANTIC_PACK_RESOURCE_URI, mapping)
        self.assertIsInstance(mapping[SEMANTIC_PACK_RESOURCE_URI], dict)

    def test_semantic_packs_resource_is_deterministic_for_temp_root(self) -> None:
        # Copy a fixture pack into a temp root and validate resource determinism.
        source_pack = Path(DEFAULT_PACK_ROOT) / "demo_company" / "revenue.v0_1.yaml"
        self.assertTrue(source_pack.exists())

        with TemporaryDirectory() as workspace:
            root = Path(workspace)
            _make_temp_root_with_demo_pack(root)

            payload = build_packs_resource(root / "semantic_packs")
            packs = PackStore(root / "semantic_packs").list_spaces()
            self.assertEqual(payload["count"], 1)
            self.assertEqual(payload["spaces"][0]["space_id"], packs[0].space_id)

    def test_pack_resource_can_load_a_specific_pack_by_id(self) -> None:
        with TemporaryDirectory() as workspace:
            root = Path(workspace)
            _make_temp_root_with_demo_pack(root)

            payload = build_pack_resource("demo_company.revenue", root / "semantic_packs")
            self.assertEqual(payload["id"], "demo_company.revenue")
            self.assertIn("uri", payload)
            self.assertEqual(payload["uri"], f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}demo_company.revenue")

    def test_pack_resource_uris_returns_all_pack_resources(self) -> None:
        with TemporaryDirectory() as workspace:
            root = Path(workspace)
            _make_temp_root_with_demo_pack(root)

            uris = semantic_pack_resource_uris(root / "semantic_packs")
            expected = f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}demo_company.revenue"
            self.assertIn(expected, uris)
            self.assertIsInstance(uris[expected], dict)

    def test_unknown_pack_id_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            build_pack_resource("missing.pack", Path("/tmp/does-not-matter"))

    def test_pack_terms_resource_can_load_business_terms(self) -> None:
        with TemporaryDirectory() as workspace:
            root = Path(workspace)
            _make_temp_root_with_demo_pack(root)

            payload = build_pack_terms_resource("demo_company.revenue", root / "semantic_packs")
            self.assertEqual(payload["pack_id"], "demo_company.revenue")
            self.assertIn("resource_uri", payload)
            self.assertEqual(payload["resource_uri"], f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}demo_company.revenue{SEMANTIC_PACK_TERMS_URI_SUFFIX}")
            self.assertIn("terms", payload)
            self.assertGreaterEqual(len(payload["terms"]), 1)
            self.assertEqual(payload["terms"][0]["id"], "term.new_customer")

    def test_pack_terms_resource_uris_contains_terms_endpoint(self) -> None:
        with TemporaryDirectory() as workspace:
            root = Path(workspace)
            _make_temp_root_with_demo_pack(root)

            uris = semantic_pack_terms_resource_uris(root / "semantic_packs")
            expected = f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}demo_company.revenue{SEMANTIC_PACK_TERMS_URI_SUFFIX}"
            self.assertIn(expected, uris)
            self.assertIsInstance(uris[expected], dict)

    def test_pack_terms_resource_unknown_pack_id_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            build_pack_terms_resource("missing.pack", Path("/tmp/does-not-matter"))

    def test_pack_metrics_resource_can_load_metrics(self) -> None:
        with TemporaryDirectory() as workspace:
            root = Path(workspace)
            _make_temp_root_with_demo_pack(root)

            payload = build_pack_metrics_resource("demo_company.revenue", root / "semantic_packs")
            self.assertEqual(payload["pack_id"], "demo_company.revenue")
            self.assertIn("resource_uri", payload)
            self.assertEqual(
                payload["resource_uri"],
                f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}demo_company.revenue{SEMANTIC_PACK_METRICS_URI_SUFFIX}",
            )
            self.assertIn("metrics", payload)
            self.assertGreaterEqual(len(payload["metrics"]), 2)
            self.assertEqual(payload["metrics"][0]["id"], "metric.net_revenue")

    def test_pack_metrics_resource_uris_contains_metrics_endpoint(self) -> None:
        with TemporaryDirectory() as workspace:
            root = Path(workspace)
            _make_temp_root_with_demo_pack(root)

            uris = semantic_pack_metrics_resource_uris(root / "semantic_packs")
            expected = f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}demo_company.revenue{SEMANTIC_PACK_METRICS_URI_SUFFIX}"
            self.assertIn(expected, uris)
            self.assertIsInstance(uris[expected], dict)

    def test_pack_metrics_resource_unknown_pack_id_raises_key_error(self) -> None:
        with self.assertRaises(KeyError):
            build_pack_metrics_resource("missing.pack", Path("/tmp/does-not-matter"))

    def test_pack_policy_and_verified_query_resources_cover_phase2_endpoints(self) -> None:
        with TemporaryDirectory() as workspace:
            root = Path(workspace)
            _make_temp_root_with_demo_pack(root)

            policies = get_pack_policies("demo_company.revenue", root / "semantic_packs")
            verified_queries = get_pack_verified_queries("demo_company.revenue", root / "semantic_packs")

            self.assertEqual(
                policies["resource_uri"],
                f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}demo_company.revenue{SEMANTIC_PACK_POLICIES_URI_SUFFIX}",
            )
            self.assertGreaterEqual(
                set(policies["policies"][0]["blocked_columns"]),
                {"users.email", "users.phone", "users.name"},
            )
            self.assertEqual(
                verified_queries["resource_uri"],
                f"{SEMANTIC_PACK_BY_ID_URI_PREFIX}demo_company.revenue{SEMANTIC_PACK_VERIFIED_QUERIES_URI_SUFFIX}",
            )
            self.assertEqual(
                verified_queries["verified_queries"][0]["id"],
                "verified_query.monthly_new_customer_revenue",
            )
