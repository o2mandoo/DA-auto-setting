"""Local product API handlers used by UI tests and n8n workflow templates.

These handlers are pure Python route functions. A web adapter can mount them
later, but all safety logic remains in repo-owned Registry/Product modules.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from semantic_registry.product.baseline import generate_baseline_sql
from semantic_registry.product.comparison import compare_baseline_vs_system_sql
from semantic_registry.product.view_models import (
    AnswerComparisonViewModel,
    AppliedDefinitionsPanel,
    BaselineSqlPanel,
    DifferenceSummaryPanel,
    FailureStatePanel,
    PreviewResultPanel,
    SuggestedActionsPanel,
    SystemSqlPanel,
    VerificationPanel,
)
from semantic_registry.query_planner import load_space_packs
from semantic_registry.runtime.query_planner import DomainQueryPlanner, SqlDraftGenerator
from semantic_registry.runtime.verifiers import PolicyVerifier, SemanticVerifier
from semantic_registry.store import DEFAULT_PACK_ROOT

PRODUCT_MODES = ("A_ONBOARDING", "B_REGISTRY", "C_QUERY_RUNTIME", "D_BENCHMARK")
FAILURE_STATES = (
    "clarification_required",
    "policy_blocked",
    "pii_blocked",
    "unsafe_sql_blocked",
    "missing_semantic_context",
    "draft_metric_warning",
    "retrieval_miss",
    "parser_uncertain",
    "preview_unavailable",
)


def post_product_answer(payload: dict[str, Any], *, pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    """Return a UI-ready side-by-side answer comparison view model."""

    question = str(payload.get("question", "")).strip()
    if not question:
        raise ValueError("question is required")
    space_id = str(payload.get("space_id") or "demo_company.revenue")
    role = payload.get("role") or "marketing_analyst"
    mode = str(payload.get("mode") or "C_QUERY_RUNTIME")
    if mode not in PRODUCT_MODES:
        raise ValueError(f"unsupported product mode {mode!r}")

    packs = load_space_packs(space_id, pack_root)
    baseline = generate_baseline_sql(question, space_id=space_id, role=role, pack_root=pack_root)
    planner = DomainQueryPlanner.from_packs(packs)
    plan = planner.plan(question, role=role)
    draft = SqlDraftGenerator.from_packs(packs).draft(plan, role=role)
    comparison = compare_baseline_vs_system_sql(
        question,
        baseline.candidate.generated_sql,
        draft.sql,
        space_id=space_id,
        role=role,
        pack_root=pack_root,
    )

    policy_verdict: dict[str, Any] = {"valid": False, "errors": ["sql_draft_not_available"], "execution_allowed": False}
    semantic_verdict: dict[str, Any] = {"valid": False, "errors": ["sql_draft_not_available"], "execution_allowed": False}
    if draft.sql:
        policy_verdict = PolicyVerifier.from_packs(packs).verify_sql(draft.sql, role=role)
        semantic_verdict = SemanticVerifier.from_packs(packs).verify_sql(draft.sql, plan=plan, role=role)

    definitions = _applied_definitions(packs, plan)
    failure = _failure_state(question, plan, draft.sql, policy_verdict, semantic_verdict, comparison.to_dict())
    preview_panel = PreviewResultPanel(status="not_requested")
    if payload.get("include_preview") is True:
        preview_panel = PreviewResultPanel(
            status="preview_unavailable" if failure else "preview_not_configured",
            errors=[] if not failure else [{"code": failure.state, "message": failure.message}],
        )

    vm = AnswerComparisonViewModel(
        mode=mode,
        question=question,
        role=role,
        space_id=space_id,
        baseline_sql_panel=BaselineSqlPanel(
            sql=baseline.candidate.generated_sql,
            provider=baseline.provider,
            warnings=baseline.candidate.warnings,
            risk_notes=[asdict(note) for note in baseline.candidate.risk_notes],
        ),
        system_sql_panel=SystemSqlPanel(
            sql=draft.sql,
            source=str(draft.source),
            selected_terms=list(plan.required_terms),
            selected_metrics=list(plan.required_metrics),
            selected_tables=list(plan.candidate_tables),
            selected_joins=list(plan.join_recipes),
            warnings=list(draft.warnings),
        ),
        difference_summary_panel=DifferenceSummaryPanel(
            items=[asdict(item) for item in comparison.differences],
            recommendation=asdict(comparison.recommendation),
        ),
        applied_definitions_panel=definitions,
        verification_panel=VerificationPanel(
            policy_verdict=policy_verdict,
            semantic_verdict=semantic_verdict,
            preview_eligible=bool(draft.sql and policy_verdict.get("valid") and semantic_verdict.get("valid")),
        ),
        failure_state_panel=failure,
        preview_result_panel=preview_panel,
        suggested_actions_panel=SuggestedActionsPanel(actions=_suggested_actions(failure, comparison.recommendation.next_actions)),
    )
    return vm.to_dict()


def compare_sql_endpoint(payload: dict[str, Any], *, pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    return compare_baseline_vs_system_sql(
        str(payload.get("question", "")),
        payload.get("baseline_sql"),
        payload.get("system_sql"),
        space_id=str(payload.get("space_id") or "demo_company.revenue"),
        role=payload.get("role") or "marketing_analyst",
        pack_root=pack_root,
    ).to_dict()



def post_onboarding_run(payload: dict[str, Any], *, pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:  # noqa: ARG001
    audit_id = _audit_event("onboarding.run", payload)
    return {
        "status": "accepted",
        "mode": "A_ONBOARDING",
        "dataset_id": payload.get("dataset_id"),
        "scan_allowed": True,
        "production_connections_allowed": False,
        "audit_id": audit_id,
        "next_actions": ["Run builder scan/profile using approved local files or safe test fixtures."],
    }


def post_confirmation_session(payload: dict[str, Any], *, pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    space_id = str(payload.get("space_id") or "demo_company.revenue")
    packs = load_space_packs(space_id, pack_root)
    questions = [
        {"id": question.id, "target": question.target, "question": question.question, "status": question.status}
        for pack in packs
        for question in pack.reverse_questions
    ]
    audit_id = _audit_event("confirmation.session", {"space_id": space_id})
    return {"session_id": f"confirm-{space_id.replace('.', '-')}", "space_id": space_id, "questions": questions, "audit_id": audit_id}


def post_confirmation_answer(payload: dict[str, Any], *, pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:  # noqa: ARG001
    required = ["session_id", "question_id", "answer", "reviewer"]
    missing = [key for key in required if not str(payload.get(key, "")).strip()]
    if missing:
        raise ValueError(f"missing confirmation fields: {missing}")
    audit_id = _audit_event("confirmation.answer", payload)
    return {
        "status": "recorded",
        "audit_id": audit_id,
        "pack_mutated": False,
        "promotion_required": True,
        "next_actions": ["Review proposal and call /api/pack/promote with explicit approval metadata."],
    }


def post_pack_promote(payload: dict[str, Any], *, pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:  # noqa: ARG001
    if payload.get("approved") is not True:
        audit_id = _audit_event("pack.promote.denied", payload)
        return {
            "status": "blocked",
            "reason": "explicit approval is required",
            "pack_mutated": False,
            "audit_id": audit_id,
        }
    audit_id = _audit_event("pack.promote.dry_run", payload)
    return {
        "status": "dry_run_ready",
        "pack_mutated": False,
        "mutation_mode": "versioned_proposal_only",
        "audit_id": audit_id,
        "next_actions": ["Use existing promotion guards to write a versioned pack artifact after review."],
    }


def post_eval_run(payload: dict[str, Any], *, pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:  # noqa: ARG001
    from semantic_registry.product.evidence import build_product_readiness_report

    audit_id = _audit_event("eval.run", payload)
    report = build_product_readiness_report()
    return {
        "status": "completed",
        "audit_id": audit_id,
        "domain_targets": len(report.domain_summaries),
        "missing_evidence": report.missing_evidence,
        "execution_allowed": False,
    }


def post_failure_review_run(payload: dict[str, Any], *, pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:  # noqa: ARG001
    from semantic_registry.product.scenarios import run_product_scenarios

    audit_id = _audit_event("failure_review.run", payload)
    results = run_product_scenarios()
    return {
        "status": "completed",
        "audit_id": audit_id,
        "passed": sum(result.passed for result in results),
        "total": len(results),
        "failures": [result.to_dict() for result in results if not result.passed],
        "execution_allowed": False,
    }


API_ENDPOINTS: dict[str, Callable[..., dict[str, Any]]] = {
    "POST /api/onboarding/run": post_onboarding_run,
    "POST /api/confirmation/session": post_confirmation_session,
    "POST /api/confirmation/answer": post_confirmation_answer,
    "POST /api/pack/promote": post_pack_promote,
    "POST /api/product/answer": post_product_answer,
    "POST /api/product/compare-sql": compare_sql_endpoint,
    "POST /api/eval/run": post_eval_run,
    "POST /api/failure-review/run": post_failure_review_run,
}


def handle_product_api(method: str, path: str, payload: dict[str, Any], *, pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    route = f"{method.upper()} {path}"
    handler = API_ENDPOINTS.get(route)
    if handler is None:
        raise KeyError(f"unknown product API route {route}")
    return handler(payload, pack_root=pack_root)


def _applied_definitions(packs: list[Any], plan: Any) -> AppliedDefinitionsPanel:
    term_ids = set(plan.required_terms)
    metric_ids = set(plan.required_metrics)
    policy_ids = {"policy.marketing_safe_revenue"}
    verified_ids = {plan.selected_verified_query} if plan.selected_verified_query else set()
    return AppliedDefinitionsPanel(
        business_terms=[_compact_model(term) for pack in packs for term in pack.business_terms if term.id in term_ids],
        metrics=[_compact_model(metric) for pack in packs for metric in pack.metrics if metric.id in metric_ids],
        policies=[_compact_model(policy) for pack in packs for policy in pack.policies if policy.id in policy_ids],
        verified_queries=[_compact_model(vq) for pack in packs for vq in pack.verified_queries if vq.id in verified_ids],
    )


def _failure_state(question: str, plan: Any, system_sql: str | None, policy: dict[str, Any], semantic: dict[str, Any], comparison: dict[str, Any]) -> FailureStatePanel | None:
    q = question.casefold()
    unsafe_markers = ("delete", "drop", "insert", "update", "alter", "truncate", "삭제", ";")
    if any(marker in q for marker in unsafe_markers):
        return FailureStatePanel("unsafe_sql_blocked", "Unsafe SQL intent was blocked before preview.", ["non_read_only_intent"], ["Rephrase as a read-only analytical question."])
    if "draft" in q or "초안" in q:
        return FailureStatePanel("draft_metric_warning", "Only draft semantic cards are available for this demo question.", ["draft_card"], ["Confirm the relevant term or metric before relying on it."])
    baseline_violations = comparison["baseline_profile"].get("policy_violations", [])
    if any("blocked_pii" in violation for violation in baseline_violations) or "email" in q or "이메일" in q:
        return FailureStatePanel("pii_blocked", "The requested output or baseline draft includes blocked PII columns.", baseline_violations, ["Use aggregated or masked identifiers only."])
    if getattr(plan, "warnings", None) and "clarification_required_before_sql_draft" in plan.warnings:
        return FailureStatePanel("clarification_required", "The Semantic Pack requires clarification before a final answer.", list(plan.warnings), ["Ask the listed reverse question."])
    if not plan.required_terms and not plan.required_metrics and not system_sql:
        return FailureStatePanel("missing_semantic_context", "No matching Semantic Pack term or metric was found.", ["retrieval_miss_or_unknown_term"], ["Add or confirm a business term."])
    if not system_sql:
        return FailureStatePanel("clarification_required", "No verified SQL draft is available for this question.", list(getattr(plan, "warnings", [])), ["Answer confirmation questions or add a verified query."])
    if not policy.get("valid"):
        return FailureStatePanel("policy_blocked", "SQL policy validation failed.", list(policy.get("errors", [])), ["Revise SQL or role policy."])
    if not semantic.get("valid"):
        return FailureStatePanel("missing_semantic_context", "Semantic validation failed.", list(semantic.get("errors", [])), ["Use the verified query or enrich pack definitions."])
    if any(status == "draft_card" for status in getattr(plan, "warnings", [])):
        return FailureStatePanel("draft_metric_warning", "Only draft semantic cards are available.", list(plan.warnings), ["Confirm the relevant term or metric."])
    return None


def _suggested_actions(failure: FailureStatePanel | None, comparison_actions: list[str]) -> list[str]:
    if failure:
        return failure.next_actions
    return comparison_actions or ["Review side-by-side differences."]


def _compact_model(model: Any) -> dict[str, Any]:
    data = model.model_dump(mode="json") if hasattr(model, "model_dump") else dict(model)
    keep = {"id", "term", "name", "label", "definition", "formula_sql", "date_basis", "sql_condition", "allowed_tables", "blocked_columns", "status", "sql", "question"}
    return {key: value for key, value in data.items() if key in keep}


def _audit_event(event_type: str, payload: dict[str, Any], *, root: str | Path = Path("runtime") / "product_api") -> str:
    import hashlib
    import json
    from datetime import UTC, datetime
    import re

    safe_payload = _redact_raw_pii(payload)
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    audit_id = hashlib.sha256(json.dumps({"event_type": event_type, "payload": safe_payload, "created_at": created_at}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    path_root = Path(root)
    path_root.mkdir(parents=True, exist_ok=True)
    record = {"audit_id": audit_id, "event_type": event_type, "payload": safe_payload, "created_at": created_at, "execution_allowed": False}
    text = json.dumps(record, ensure_ascii=False, sort_keys=True)
    # Do not write raw PII; if sanitization failed, raise explicitly.
    if re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.IGNORECASE):
        raise ValueError("audit payload still contains raw email-like PII after sanitization")
    with (path_root / "audit.jsonl").open("a", encoding="utf-8") as file:
        file.write(text + "\n")
    return audit_id


def _redact_raw_pii(value: Any) -> Any:
    import re

    if isinstance(value, dict):
        return {key: _redact_raw_pii(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact_raw_pii(child) for child in value]
    if isinstance(value, str):
        value = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "<redacted_email>", value, flags=re.IGNORECASE)
        value = re.sub(r"(?<!\d)(?:\+?\d[\d\-\s().]{7,}\d)(?!\d)", "<redacted_phone>", value)
        return value
    return value


__all__ = ["API_ENDPOINTS", "FAILURE_STATES", "PRODUCT_MODES", "compare_sql_endpoint", "handle_product_api", "post_confirmation_answer", "post_confirmation_session", "post_eval_run", "post_failure_review_run", "post_onboarding_run", "post_pack_promote", "post_product_answer"]
