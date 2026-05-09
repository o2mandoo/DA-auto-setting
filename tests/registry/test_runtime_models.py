from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_contracts import (  # noqa: E402
    AmbiguityDecision,
    AmbiguityStatus,
    AnswerStatus,
    ContextCardRef,
    PolicyVerdict,
    RuntimeAnswerDraft,
    RuntimeContext,
    RuntimeIntent,
    SemanticVerdict,
    SqlDraft,
    SqlDraftSource,
    UserQuestion,
    VerdictStatus,
)
from semantic_registry.runtime.models import UserQuestion as RegistryUserQuestion  # noqa: E402


class RuntimeModelsTest(unittest.TestCase):
    def test_runtime_models_are_importable_from_contracts_and_registry_runtime(self) -> None:
        question = UserQuestion(space_id="revenue", question="지난달 신규 고객 순매출", role="marketing_analyst")
        context = RuntimeContext(user_question=question, pack_ids=["demo_company.revenue"])

        self.assertIsInstance(question, RegistryUserQuestion)
        self.assertEqual(context.retrieval_backend, "keyword")
        self.assertEqual(context.user_question.role, "marketing_analyst")

    def test_user_question_is_strict_and_requires_non_blank_fields(self) -> None:
        with self.assertRaises(ValidationError):
            UserQuestion(space_id="revenue", question="   ")
        with self.assertRaises(ValidationError):
            UserQuestion(space_id="revenue", question="매출", unexpected=True)

    def test_draft_card_warning_rolls_up_to_context_bundle_and_answer(self) -> None:
        card = ContextCardRef(
            card_id="metric.net_revenue",
            card_type="metric",
            source_pack="demo_company.revenue",
            status="draft",
            score=0.92,
        )
        answer = RuntimeAnswerDraft(
            status=AnswerStatus.READY,
            question=UserQuestion(space_id="revenue", question="순매출"),
            context={"cards": [card]},
        )

        self.assertIn("draft_card", card.warnings)
        self.assertIn("draft_card", answer.context.warnings)
        self.assertIn("draft_card", answer.warnings)

    def test_sql_draft_is_validation_only_and_rejects_mutating_sql_or_execution_flag(self) -> None:
        draft = SqlDraft(
            sql="SELECT DATE_TRUNC('month', users.first_paid_at) AS month FROM users",
            source=SqlDraftSource.RULE_BASED,
            used_cards=["table.users"],
            confidence=0.7,
        )

        self.assertFalse(draft.execution_allowed)
        with self.assertRaises(ValidationError):
            SqlDraft(sql="DELETE FROM users", source=SqlDraftSource.RULE_BASED)
        with self.assertRaises(ValidationError):
            SqlDraft(sql="SELECT 'ada@example.com'", source=SqlDraftSource.RULE_BASED)
        with self.assertRaises(ValidationError):
            SqlDraft(sql="SELECT 1", source=SqlDraftSource.RULE_BASED, execution_allowed=True)

    def test_ambiguity_and_answer_statuses_require_clarifying_questions(self) -> None:
        with self.assertRaises(ValidationError):
            AmbiguityDecision(status=AmbiguityStatus.NEEDS_CLARIFICATION)

        decision = AmbiguityDecision(
            status=AmbiguityStatus.NEEDS_CLARIFICATION,
            questions=["총매출과 순매출 중 어느 매출인가요?"],
            ambiguous_targets=["metric.gross_revenue", "metric.net_revenue"],
        )
        answer = RuntimeAnswerDraft(
            status=AnswerStatus.NEEDS_CLARIFICATION,
            question=UserQuestion(space_id="revenue", question="매출 보여줘"),
            ambiguity=decision,
            clarification_questions=decision.questions,
        )

        self.assertEqual(answer.ambiguity.status, AmbiguityStatus.NEEDS_CLARIFICATION)
        self.assertEqual(answer.clarification_questions, ["총매출과 순매출 중 어느 매출인가요?"])

    def test_policy_and_semantic_verdicts_require_explicit_failure_evidence(self) -> None:
        policy = PolicyVerdict(
            status=VerdictStatus.FAIL,
            allowed=False,
            blocked_columns=["users.email"],
            reasons=["Raw user PII columns are blocked for marketing_analyst."],
        )
        semantic = SemanticVerdict(
            status=VerdictStatus.FAIL,
            valid=False,
            missing_terms=["term.unknown"],
            reasons=["Question referenced an unresolved business term."],
        )
        answer = RuntimeAnswerDraft(
            status=AnswerStatus.BLOCKED,
            question=UserQuestion(space_id="revenue", question="users.email까지 보여줘"),
            policy_verdict=policy,
            semantic_verdict=semantic,
        )

        self.assertFalse(answer.policy_verdict.allowed)
        self.assertFalse(answer.semantic_verdict.valid)
        self.assertFalse(answer.execution_allowed)
        with self.assertRaises(ValidationError):
            PolicyVerdict(status=VerdictStatus.PASS, allowed=False)
        with self.assertRaises(ValidationError):
            SemanticVerdict(status=VerdictStatus.PASS, valid=False)

    def test_intent_enum_serializes_structured_output(self) -> None:
        answer = RuntimeAnswerDraft(
            status=AnswerStatus.READY,
            question=UserQuestion(space_id="revenue", question="순매출"),
            intent={"intent": RuntimeIntent.DATA_QUERY, "normalized_question": "순매출", "confidence": 0.8},
        )
        dumped = answer.model_dump(mode="json")

        self.assertEqual(dumped["intent"]["intent"], "data_query")
        self.assertFalse(dumped["execution_allowed"])


if __name__ == "__main__":
    unittest.main()
