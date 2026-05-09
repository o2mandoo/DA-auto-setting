from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from semantic_builder.eval.cli import main as eval_main
from semantic_builder.eval import (
    build_demo_benchmark_manifest,
    load_benchmark_manifest,
    render_benchmark_json,
    render_benchmark_markdown,
    run_benchmark_manifest,
    run_builder_safety_cases,
    run_golden_questions,
    run_red_team_cases,
    run_retrieval_cases,
    run_runtime_cases,
    write_benchmark_report,
)

ROOT = Path(__file__).resolve().parents[2]


class EvalRunnerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = build_demo_benchmark_manifest()

    def test_demo_benchmark_runs_and_renders_reports(self) -> None:
        run = run_benchmark_manifest(self.manifest)
        self.assertEqual(run.summary["failed"], 0, run.as_dict())
        self.assertEqual(run.summary["skipped"], 0, run.as_dict())
        self.assertGreaterEqual(run.summary["passed"], 4, run.as_dict())

        json_report = render_benchmark_json(run)
        markdown_report = render_benchmark_markdown(run)

        parsed = json.loads(json_report)
        self.assertEqual(parsed["manifest"]["manifest_id"], self.manifest.manifest_id)
        self.assertIn("summary", parsed)
        self.assertIn("golden.monthly_new_customer_revenue", markdown_report)
        self.assertIn("PASS", markdown_report)

    def test_contract_manifest_yaml_can_drive_runner(self) -> None:
        manifest_path = Path("eval/datasets/tableau_superstore.yaml")
        manifest = load_benchmark_manifest(manifest_path)
        self.assertEqual(type(manifest).__name__, "FileCorpusBenchmarkManifest")
        self.assertEqual(manifest.dataset_id, "tableau_superstore")

        with TemporaryDirectory() as tmpdir:
            run = run_benchmark_manifest(manifest_path, out_dir=Path(tmpdir) / "runtime" / "benchmarks" / "tableau_superstore")

        self.assertEqual(run.summary["failed"], 0, run.as_dict())
        self.assertEqual(run.summary["skipped"], 0)
        self.assertEqual(run.manifest.dataset_id, "tableau_superstore")
        self.assertGreater(run.summary["passed"], 0, run.as_dict())
        self.assertTrue(any(result.category == "file_source" and result.passed for result in run.results), run.as_dict())
        self.assertTrue(any(result.category == "semantic_gold" and result.passed for result in run.results), run.as_dict())

    def test_cli_requires_explicit_manifest_or_corpus_mode(self) -> None:
        with self.assertRaises(SystemExit) as exc:
            eval_main([])

        self.assertEqual(exc.exception.code, 2)

    def test_load_benchmark_manifest_parses_generic_file_corpus_manifests(self) -> None:
        cases = (
            ("tableau_superstore.yaml", "tableau_superstore", ("docs/reference/test_datasets/tableau_superstore/Sample - Superstore.xls",), ("raw customer PII values",)),
            ("sinagong_tableau_2026.yaml", "sinagong_tableau_2026", None, ("raw employee name/phone/email values", "raw customer PII values")),
        )

        for manifest_name, dataset_id, expected_file_suffixes, expected_must_block in cases:
            with self.subTest(manifest_name=manifest_name):
                manifest = load_benchmark_manifest(Path("eval/datasets") / manifest_name)
                self.assertEqual(type(manifest).__name__, "FileCorpusBenchmarkManifest")
                self.assertEqual(manifest.dataset_id, dataset_id)
                self.assertTrue(manifest.files)
                for blocked in expected_must_block:
                    self.assertIn(blocked, manifest.must_block)
                if expected_file_suffixes is not None:
                    for suffix in expected_file_suffixes:
                        self.assertTrue(any(str(path).endswith(suffix) for path in manifest.files), manifest.files)

        with self.assertRaisesRegex(ValueError, "must list at least one local file input"):
            load_benchmark_manifest(Path("eval/datasets") / "postgresql_fixture_template.yaml")

    def test_missing_pack_root_skips_every_case_with_explicit_reason(self) -> None:
        with TemporaryDirectory() as tmpdir:
            run = run_benchmark_manifest(self.manifest, pack_root=Path(tmpdir))

        self.assertEqual(run.summary["passed"], 0, run.as_dict())
        self.assertEqual(run.summary["failed"], 0, run.as_dict())
        self.assertEqual(run.summary["skipped"], len(run.results), run.as_dict())
        self.assertTrue(all(result.skipped for result in run.results))
        self.assertTrue(all("demo benchmark unavailable" in result.reason for result in run.results))

    def test_file_corpus_benchmark_writes_runtime_benchmarks_outputs(self) -> None:
        manifest = load_benchmark_manifest(Path("eval/datasets") / "tableau_superstore.yaml")
        with TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "runtime" / "benchmarks" / manifest.dataset_id
            run = run_benchmark_manifest(manifest, out_dir=out_dir)

            self.assertEqual(run.summary["failed"], 0, run.as_dict())
            self.assertEqual(run.summary["skipped"], 0, run.as_dict())
            self.assertGreater(run.summary["passed"], 0, run.as_dict())
            self.assertTrue((out_dir / "scan_report.json").exists(), out_dir)
            self.assertTrue((out_dir / "column_profiles.jsonl").exists(), out_dir)
            self.assertTrue((out_dir / "semantic_hypotheses.jsonl").exists(), out_dir)
            self.assertTrue((out_dir / "onboarding_questions.jsonl").exists(), out_dir)
            self.assertTrue((out_dir / "semantic_pack.draft.yaml").exists(), out_dir)
            self.assertTrue((out_dir / "benchmark.json").exists(), out_dir)
            self.assertTrue((out_dir / "benchmark.md").exists(), out_dir)
            self.assertIn(manifest.dataset_id, (out_dir / "benchmark.md").read_text(encoding="utf-8"))

    def test_mismatched_expected_terms_surface_as_non_skipped_failures(self) -> None:
        bad_manifest = replace(
            self.manifest,
            golden_questions=(
                replace(
                    self.manifest.golden_questions[0],
                    expected_terms=("term.definitely_missing",),
                    pass_criteria="force a failure for regression coverage",
                ),
            ),
        )

        run = run_benchmark_manifest(bad_manifest)
        results = {result.case_id: result for result in run.results}
        golden = results["golden.monthly_new_customer_revenue"]

        self.assertFalse(golden.passed, golden.as_dict())
        self.assertFalse(golden.skipped, golden.as_dict())
        self.assertGreaterEqual(run.summary["failed"], 1, run.as_dict())
        self.assertIn("missing terms", golden.reason)
        self.assertIn("FAIL", render_benchmark_markdown(run))

    def test_write_benchmark_report_writes_runtime_benchmarks_outputs(self) -> None:
        run = run_benchmark_manifest(self.manifest)
        with TemporaryDirectory() as tmpdir:
            out_root = Path(tmpdir) / "runtime" / "benchmarks" / self.manifest.dataset_id
            json_path = out_root / "benchmark.json"
            markdown_path = out_root / "benchmark.md"

            write_benchmark_report(run, json_path, markdown_path)

            self.assertTrue(json_path.exists(), json_path)
            self.assertTrue(markdown_path.exists(), markdown_path)
            self.assertIn(self.manifest.manifest_id, json_path.read_text(encoding="utf-8"))
            self.assertIn(self.manifest.dataset_id, markdown_path.read_text(encoding="utf-8"))

    def test_cli_defaults_to_runtime_benchmarks_output_path(self) -> None:
        manifest = SimpleNamespace(dataset_id="tableau_superstore")
        fake_run = SimpleNamespace(summary={"failed": 0}, results=[], manifest=manifest)

        with (
            patch("semantic_builder.eval.cli.load_benchmark_manifest", return_value=manifest) as load_manifest,
            patch("semantic_builder.eval.cli.run_benchmark_manifest", return_value=fake_run) as run_manifest,
            patch("semantic_builder.eval.cli.render_benchmark_json", return_value="{}"),
            patch("semantic_builder.eval.cli.write_benchmark_report") as write_report,
        ):
            exit_code = eval_main(["--manifest", "eval/datasets/tableau_superstore.yaml"])

        self.assertEqual(exit_code, 0)
        load_manifest.assert_called_once()
        run_manifest.assert_called_once()
        write_report.assert_called_once()
        _, json_path, markdown_path = write_report.call_args.args
        self.assertEqual(Path(json_path), Path("runtime") / "benchmarks" / manifest.dataset_id / "benchmark.json")
        self.assertEqual(Path(markdown_path), Path("runtime") / "benchmarks" / manifest.dataset_id / "benchmark.md")

    def test_golden_questions_resolve_verified_query_context(self) -> None:
        results = run_golden_questions(self.manifest)
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertTrue(result.passed, result.as_dict())
        plan = result.evidence["plan"]
        runtime_plan = result.evidence["runtime_plan"]
        sql_draft = result.evidence["sql_draft"]
        self.assertIn("term.new_customer", plan["required_terms"])
        self.assertIn("metric.net_revenue", plan["required_metrics"])
        self.assertIn("join.users_payments", plan["join_recipes"])
        self.assertEqual(runtime_plan["selected_verified_query"], "verified_query.monthly_new_customer_revenue")
        self.assertEqual(sql_draft["source"], "verified_query_template")

    def test_red_team_questions_are_specific_and_evidence_based(self) -> None:
        results = run_red_team_cases(self.manifest)
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertTrue(result.passed, result.as_dict())
        questions = result.evidence["questions"]
        question_text = "\n".join(item["question"] for item in questions)
        self.assertIn("paid_at", question_text)
        self.assertIn("customer_id", question_text)
        self.assertIn("campaign_id", question_text)
        self.assertIn("revenue_amount", question_text)
        self.assertNotIn("what business meaning should", question_text.casefold())
        self.assertNotIn("additional sample-free documentation", question_text.casefold())
        self.assertTrue(all(item["evidence"] for item in questions))

    def test_retrieval_and_builder_safety_are_local_and_pii_safe(self) -> None:
        retrieval_results = run_retrieval_cases(self.manifest)
        builder_results = run_builder_safety_cases(self.manifest)

        self.assertEqual(len(retrieval_results), 4)
        retrieval_map = {result.case_id: result for result in retrieval_results}
        self.assertTrue(retrieval_map["retrieval.term_metric_and_ambiguity"].passed, retrieval_map["retrieval.term_metric_and_ambiguity"].as_dict())
        self.assertTrue(retrieval_map["retrieval.policy_marketing_analyst"].passed, retrieval_map["retrieval.policy_marketing_analyst"].as_dict())
        self.assertTrue(retrieval_map["retrieval.value_dictionary_segment"].passed, retrieval_map["retrieval.value_dictionary_segment"].as_dict())
        self.assertTrue(retrieval_map["retrieval.ambiguity_rule_refund_timing"].passed, retrieval_map["retrieval.ambiguity_rule_refund_timing"].as_dict())

        retrieved = retrieval_map["retrieval.term_metric_and_ambiguity"].evidence["results"]
        retrieved_ids = [item["card_id"] for item in retrieved]
        self.assertIn("term.new_customer", retrieved_ids)
        self.assertIn("metric.net_revenue", retrieved_ids)
        self.assertIn("verified_query.monthly_new_customer_revenue", retrieved_ids)
        self.assertIn("rq.net_revenue.refund_timing", retrieved_ids)

        policy_results = retrieval_map["retrieval.policy_marketing_analyst"].evidence["results"]
        policy_ids = [item["card_id"] for item in policy_results]
        self.assertIn("policy.marketing_safe_revenue", policy_ids)

        segment_results = retrieval_map["retrieval.value_dictionary_segment"].evidence["results"]
        segment_ids = [item["card_id"] for item in segment_results]
        self.assertIn("value_dict.users.segment", segment_ids)

        self.assertEqual(len(builder_results), 1)
        self.assertTrue(builder_results[0].passed, builder_results[0].as_dict())
        inference = builder_results[0].evidence["inference"]
        inference_text = json.dumps(inference, ensure_ascii=False)
        self.assertNotIn("alice@example.com", inference_text)
        self.assertNotIn("+821012345678", inference_text)
        self.assertNotIn("kim example", inference_text.casefold())

    def test_runtime_ambiguity_blocks_sql_and_prefers_verified_query(self) -> None:
        results = {result.case_id: result for result in run_runtime_cases(self.manifest)}

        generic = results["runtime.generic_revenue"]
        self.assertTrue(generic.passed, generic.as_dict())
        ambiguity_ids = [item["id"] for item in generic.evidence["ambiguity"]["ambiguities"]]
        self.assertIn("runtime.metric_choice_required", ambiguity_ids)

        draft_metric = results["runtime.draft_metric_warning"]
        self.assertTrue(draft_metric.passed, draft_metric.as_dict())
        self.assertEqual(draft_metric.evidence["plan"]["selected_verified_query"], "verified_query.monthly_new_customer_revenue")
        self.assertEqual(draft_metric.evidence["sql_draft"]["source"], "verified_query_template")
        warnings = json.dumps(draft_metric.evidence["ambiguity"]["warnings"], ensure_ascii=False)
        self.assertIn("draft_semantic_card", warnings)
        ambiguity_ids = [item["id"] for item in draft_metric.evidence["ambiguity"]["ambiguities"]]
        self.assertIn("rq.new_customer.date_basis", ambiguity_ids)
        self.assertIn("rq.net_revenue.refund_timing", ambiguity_ids)

        verified = results["runtime.verified_query_preferred"]
        self.assertTrue(verified.passed, verified.as_dict())
        self.assertEqual(verified.evidence["plan"]["selected_verified_query"], "verified_query.monthly_new_customer_revenue")
        self.assertEqual(verified.evidence["sql_draft"]["source"], "verified_query_template")


if __name__ == "__main__":
    unittest.main()
