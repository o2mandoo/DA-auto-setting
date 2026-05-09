from __future__ import annotations

import unittest
from pathlib import Path

import yaml
from semantic_contracts import BenchmarkManifest

ROOT = Path(__file__).resolve().parents[2]
SINAGONG_ROOT = "docs/reference/test_datasets/sinagong_tableau_2026"
SINAGONG_WILDCARD = "와일드카드유니온실습"


class DatasetManifestTests(unittest.TestCase):
    def test_demo_dataset_manifest_covers_available_repo_assets_only(self) -> None:
        manifest_path = ROOT / "eval" / "datasets" / "demo_company_revenue.yaml"
        self.assertTrue(manifest_path.exists(), manifest_path)

        manifest = yaml.safe_load(manifest_path.read_text())
        self.assertEqual(manifest["dataset_id"], "demo_company.revenue")
        self.assertEqual(manifest["domain"], "revenue")
        self.assertEqual(manifest["tables"], ["users", "payments"])

        for rel_path in manifest["files"]:
            self.assertTrue((ROOT / rel_path).exists(), rel_path)

        self.assertTrue(manifest["must_generate_questions"])
        self.assertIn("users.email", manifest["must_block"])
        self.assertIn("verified_query.monthly_new_customer_revenue", manifest["expected_semantic_findings"])
        self.assertGreaterEqual(len(manifest["golden_questions"]), 1)
        self.assertGreaterEqual(len(manifest["red_team_cases"]), 1)

    def test_dataset_manifests_remain_pii_safe(self) -> None:
        manifest_path = ROOT / "eval" / "datasets" / "demo_company_revenue.yaml"
        text = manifest_path.read_text()
        self.assertNotIn("alice@example.com", text)
        self.assertNotIn("+8210", text)
        self.assertIn("Any external or missing benchmark dataset must be documented separately and must not be invented here.", text)

    def test_sinagong_manifest_includes_recursive_xlsx_corpus(self) -> None:
        manifest_path = ROOT / "eval" / "datasets" / "sinagong_tableau_2026.yaml"
        self.assertTrue(manifest_path.exists(), manifest_path)

        manifest = yaml.safe_load(manifest_path.read_text())
        self.assertEqual(manifest["dataset_id"], "sinagong_tableau_2026")
        self.assertEqual(manifest["domain"], "korean_business_and_public_data")
        self.assertEqual(len([rel_path for rel_path in manifest["files"] if rel_path.endswith(".xlsx")]), 20)

        expected_recursive = {
            f"{SINAGONG_ROOT}/{name}"
            for name in (
                "2008_2024_연령별인구현황.xlsx",
                "SEILOneCompany_HR데이터.xlsx",
                "SEILOneCompany_Sales데이터.xlsx",
                "경제활동인구_2013_2024.xlsx",
                "경제활동인구_2019_2024.xlsx",
                "배달앱이용현황.xlsx",
                "서울날씨_최고기온.xlsx",
                "서울지하철승하차인원.xlsx",
                "스타벅스_구매목록.xlsx",
                "스타벅스매장데이터.xlsx",
                "시도별연간인구수.xlsx",
                "에버랜드입장객데이터.xlsx",
                "여름가전종목.xlsx",
                "온라인쇼핑몰_판매매체별_상품군별거래액_2017_2024.xlsx",
                "와일드카드유니온실습/SEILOneCompany_2022.xlsx",
                "와일드카드유니온실습/SEILOneCompany_2023.xlsx",
                "와일드카드유니온실습/SEILOneCompany_2024.xlsx",
                "와일드카드유니온실습/SEILOneCompany_2025.xlsx",
                "우리나라인구수_2021_2024.xlsx",
                "인구동태건수_2019_2023.xlsx",
            )
        }
        self.assertTrue(expected_recursive.issubset(set(manifest["files"])), manifest["files"])

        for rel_path in manifest["files"]:
            self.assertTrue((ROOT / rel_path).exists(), rel_path)

        expected_nested_tables = {
            f"{SINAGONG_WILDCARD}/SEILOneCompany_2022.xlsx/결제내역",
            f"{SINAGONG_WILDCARD}/SEILOneCompany_2023.xlsx/결제내역",
            f"{SINAGONG_WILDCARD}/SEILOneCompany_2024.xlsx/결제내역",
            f"{SINAGONG_WILDCARD}/SEILOneCompany_2025.xlsx/결제내역",
        }
        self.assertTrue(expected_nested_tables.issubset(set(manifest["tables"])), manifest["tables"])
        self.assertGreaterEqual(len(manifest["golden_questions"]), 1)
        self.assertGreaterEqual(len(manifest["red_team_cases"]), 1)
        self.assertTrue(any("semantic-gold" in note.casefold() for note in manifest["notes"]), manifest["notes"])

    def test_current_benchmark_manifests_are_semantic_gold(self) -> None:
        cases = (
            (
                ROOT / "eval" / "datasets" / "tableau_superstore.yaml",
                "tableau_superstore",
                "sales_order_management",
                ("sales", "profit", "customer segment", "product category", "regional geography", "returned orders"),
                "Sample - Superstore.xls",
            ),
            (
                ROOT / "eval" / "datasets" / "sinagong_tableau_2026.yaml",
                "sinagong_tableau_2026",
                "korean_business_and_public_data",
                ("Korean table and column naming", "HR/person-name PII candidates", "sales and payment metrics"),
                "SEILOneCompany_HR",
            ),
        )

        for manifest_path, dataset_id, domain, expected_findings, expected_file_suffix in cases:
            self.assertTrue(manifest_path.exists(), manifest_path)
            manifest = BenchmarkManifest.model_validate(yaml.safe_load(manifest_path.read_text()))
            self.assertEqual(manifest.dataset_id, dataset_id)
            self.assertEqual(manifest.domain, domain)
            self.assertTrue(manifest.must_generate_questions)
            self.assertGreaterEqual(len(manifest.golden_questions), 1)
            self.assertGreaterEqual(len(manifest.red_team_cases), 1)
            self.assertTrue(any("semantic-gold" in note.casefold() for note in manifest.notes), manifest.notes)
            if manifest.dataset_id == "sinagong_tableau_2026":
                self.assertTrue(
                    any("benchmark-only support pack" in note.casefold() for note in manifest.notes),
                    manifest.notes,
                )
            for finding in expected_findings:
                self.assertIn(finding, manifest.expected_semantic_findings)
            self.assertTrue(any(expected_file_suffix in path for path in manifest.files), manifest.files)
            for rel_path in manifest.files:
                self.assertTrue((ROOT / rel_path).exists(), rel_path)

    def test_sinagong_support_pack_has_one_term_metric_and_reverse_question_per_domain(self) -> None:
        pack_path = ROOT / "semantic_packs" / "sinagong_tableau_2026" / "semantic_gold.v0_1.yaml"
        self.assertTrue(pack_path.exists(), pack_path)

        pack = yaml.safe_load(pack_path.read_text())["semantic_pack"]

        business_terms = pack["business_terms"]
        metrics = pack["metrics"]
        reverse_questions = pack["reverse_questions"]
        policy_notes = pack["policies"][0]["notes"]

        self.assertEqual(len(business_terms), 20, business_terms)
        self.assertEqual(len(metrics), 20, metrics)
        self.assertEqual(len(reverse_questions), 20, reverse_questions)
        self.assertTrue(
            any("benchmark-only support pack" in note.casefold() for note in policy_notes),
            policy_notes,
        )

        metric_ids = {metric["id"] for metric in metrics}
        reverse_targets = {rq["target"] for rq in reverse_questions}
        reverse_ids = {rq["id"] for rq in reverse_questions}

        self.assertEqual(len(metric_ids), 20, metrics)
        self.assertEqual(len(reverse_ids), 20, reverse_questions)

        for term in business_terms:
            with self.subTest(term=term["id"]):
                self.assertTrue(term["term"], term)
                self.assertGreaterEqual(len(term["aliases"]), 1, term)
                self.assertEqual(len(term["ambiguity_rules"]), 1, term)
                self.assertEqual(len(term["related_metrics"]), 1, term)
                self.assertIn(term["related_metrics"][0], metric_ids, term)
                self.assertIn(term["id"], reverse_targets, term)

        for metric in metrics:
            with self.subTest(metric=metric["id"]):
                self.assertTrue(metric["label"], metric)
                self.assertTrue(metric["description"].startswith("Semantic-gold benchmark metric"), metric)
                self.assertTrue(metric["formula_sql"].startswith("VALIDATION_ONLY_NO_SQL"), metric)

        for rq in reverse_questions:
            with self.subTest(reverse_question=rq["id"]):
                self.assertTrue(rq["question"], rq)
                self.assertTrue(rq["reason"].startswith("Benchmark support pack must expose"), rq)


if __name__ == "__main__":
    unittest.main()
