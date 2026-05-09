from __future__ import annotations

from pathlib import Path
import unittest

from semantic_builder.eval import load_benchmark_manifest, render_benchmark_json, run_benchmark_manifest


class FileCorpusBenchmarkRunnerTests(unittest.TestCase):
    def test_non_demo_file_corpus_manifests_run_deterministically(self) -> None:
        superstore_manifest = load_benchmark_manifest(Path("eval/datasets/tableau_superstore.yaml"))
        superstore_run_one = run_benchmark_manifest(superstore_manifest)
        superstore_run_two = run_benchmark_manifest(superstore_manifest)

        self.assertEqual(superstore_run_one.as_dict(), superstore_run_two.as_dict(), superstore_manifest.dataset_id)
        self.assertEqual(render_benchmark_json(superstore_run_one), render_benchmark_json(superstore_run_two), superstore_manifest.dataset_id)
        self.assertEqual(superstore_run_one.summary["failed"], 0, superstore_run_one.as_dict())
        self.assertGreater(superstore_run_one.summary["passed"], 0, superstore_run_one.as_dict())
        self.assertEqual(superstore_run_one.manifest.dataset_id, superstore_manifest.dataset_id)

        sinagong_manifest = load_benchmark_manifest(Path("eval/datasets/sinagong_tableau_2026.yaml"))
        sinagong_run_one = run_benchmark_manifest(sinagong_manifest)
        sinagong_run_two = run_benchmark_manifest(sinagong_manifest)

        self.assertEqual(sinagong_run_one.as_dict(), sinagong_run_two.as_dict(), sinagong_manifest.dataset_id)
        self.assertEqual(render_benchmark_json(sinagong_run_one), render_benchmark_json(sinagong_run_two), sinagong_manifest.dataset_id)
        self.assertEqual(sinagong_run_one.manifest.dataset_id, sinagong_manifest.dataset_id)
        self.assertEqual(len([result for result in sinagong_run_one.results if result.category == "file_source"]), 20, sinagong_run_one.as_dict())
        self.assertTrue(any(result.category == "support_artifact" for result in sinagong_run_one.results), sinagong_run_one.as_dict())
        self.assertTrue(any(result.category == "semantic_gold" for result in sinagong_run_one.results))
        self.assertTrue(all(not result.skipped for result in sinagong_run_one.results if result.category == "semantic_gold"), sinagong_run_one.as_dict())
        self.assertTrue(all(result.reason for result in sinagong_run_one.results if result.category == "semantic_gold"), sinagong_run_one.as_dict())
        self.assertGreater(sinagong_run_one.summary["passed"], 0, sinagong_run_one.as_dict())
        self.assertGreater(sinagong_run_one.summary["total"], 20, sinagong_run_one.as_dict())
        self.assertEqual(sinagong_run_one.summary["failed"], 0, sinagong_run_one.as_dict())
        self.assertTrue(all(result.passed for result in sinagong_run_one.results if result.category == "semantic_gold"), sinagong_run_one.as_dict())
        self.assertTrue(
            any(result.category == "draft_pack" and result.case_id.endswith("draft_pack_missing") for result in sinagong_run_one.results),
            sinagong_run_one.as_dict(),
        )
        self.assertTrue(
            any(result.category == "draft_pack" and result.skipped for result in sinagong_run_one.results),
            sinagong_run_one.as_dict(),
        )

    def test_sinagong_manifest_covers_all_recursive_workbooks_and_nested_sales_inputs(self) -> None:
        manifest = load_benchmark_manifest(Path("eval/datasets/sinagong_tableau_2026.yaml"))
        recursive_xlsx = [path for path in manifest.files if str(path).endswith(".xlsx")]

        self.assertEqual(len(recursive_xlsx), 20, recursive_xlsx)
        self.assertTrue(
            {
                "docs/reference/test_datasets/sinagong_tableau_2026/와일드카드유니온실습/SEILOneCompany_2022.xlsx",
                "docs/reference/test_datasets/sinagong_tableau_2026/와일드카드유니온실습/SEILOneCompany_2023.xlsx",
                "docs/reference/test_datasets/sinagong_tableau_2026/와일드카드유니온실습/SEILOneCompany_2024.xlsx",
                "docs/reference/test_datasets/sinagong_tableau_2026/와일드카드유니온실습/SEILOneCompany_2025.xlsx",
            }.issubset({str(path) for path in manifest.files}),
            manifest.files,
        )

        run = run_benchmark_manifest(manifest)
        self.assertEqual(run.manifest.dataset_id, "sinagong_tableau_2026")
        self.assertEqual(run.summary["failed"], 0, run.as_dict())
        self.assertGreater(run.summary["passed"], 0, run.as_dict())
        self.assertIn("file_source", {result.category for result in run.results})
        self.assertIn("semantic_gold", {result.category for result in run.results})


if __name__ == "__main__":
    unittest.main()
