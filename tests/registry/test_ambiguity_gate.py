from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry.runtime.ambiguity import AmbiguityGate, evaluate_ambiguity_gate_dict  # noqa: E402
from semantic_registry.store import PackStore  # noqa: E402


class AmbiguityGateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pack_root = ROOT / "semantic_packs"
        cls.pack = PackStore(cls.pack_root).load_pack("demo_company.revenue")
        cls.gate = AmbiguityGate.from_pack(cls.pack)

    def test_generic_revenue_question_requires_metric_clarification(self) -> None:
        result = self.gate.evaluate("매출 보여줘", role="marketing_analyst")

        self.assertFalse(result.execution_allowed)
        self.assertTrue(result.requires_clarification)
        metric_choice = [item for item in result.ambiguities if item.id == "runtime.metric_choice_required"]
        self.assertEqual(len(metric_choice), 1)
        self.assertEqual(set(metric_choice[0].choices), {"metric.gross_revenue", "metric.net_revenue"})

    def test_draft_metric_and_term_statuses_are_warnings_not_confirmed_truth(self) -> None:
        result = self.gate.evaluate("지난달 신규 고객 순매출을 보여줘", role="marketing_analyst")

        warning_targets = {warning.target for warning in result.warnings if warning.code == "draft_semantic_card"}
        self.assertIn("term.new_customer", warning_targets)
        self.assertIn("metric.net_revenue", warning_targets)
        self.assertFalse(result.execution_allowed)

    def test_missing_semantic_term_is_returned_unresolved_without_fake_definition(self) -> None:
        result = self.gate.evaluate("활성 리텐션 점수를 보여줘", role="marketing_analyst")

        self.assertTrue(result.requires_clarification)
        self.assertEqual(result.unresolved_terms, ("활성 리텐션 점수를 보여줘",))
        self.assertEqual(result.plan.required_terms, [])
        self.assertEqual(result.plan.required_metrics, [])
        self.assertFalse(result.execution_allowed)

    def test_dict_api_is_json_compatible_and_validation_only(self) -> None:
        payload = evaluate_ambiguity_gate_dict(
            "demo_company.revenue",
            "매출 보여줘",
            role="marketing_analyst",
            root=self.pack_root,
        )

        self.assertTrue(payload["requires_clarification"])
        self.assertFalse(payload["execution_allowed"])
        self.assertIn("plan", payload)
        self.assertIsInstance(payload["ambiguities"], list)


if __name__ == "__main__":
    unittest.main()
