#!/usr/bin/env python3
"""Run the local Semantic Data Context demo end to end.

This script uses only repository-local demo data and validation-only runtimes.
It never executes production SQL, never contacts external services, and never
stores raw PII in the emitted summary.
"""

from __future__ import annotations

import json
from pathlib import Path
from semantic_builder.cli import main as builder_main
from semantic_builder.eval import run_benchmark_manifest, write_benchmark_report
from semantic_contracts import ConfirmationStatus, HumanConfirmation, PackStatus, ProposalStatus, load_pack_yaml
from semantic_mcp import (
    inspect_registration_surface,
    list_semantic_spaces,
    plan_data_query,
    preview_query,
    resolve_business_terms,
    search_semantic_context,
    validate_sql,
)
from semantic_registry import PackStore
from semantic_registry.promotion import promote_pack, promotion_manifest, require_explicit_confirmation
from semantic_registry.proposals import create_pack_proposal, file_evidence_ref, record_confirmation

ROOT = Path(__file__).resolve().parents[2]
DEMO_DATA = ROOT / "examples" / "demo_data"
PACK_ROOT = ROOT / "semantic_packs"
RUNTIME = ROOT / "runtime" / "phase12_demo"


def main() -> int:
    RUNTIME.mkdir(parents=True, exist_ok=True)
    scan_path = RUNTIME / "scan_report.json"
    profiles_path = RUNTIME / "column_profiles.jsonl"
    hypotheses_path = RUNTIME / "semantic_hypotheses.jsonl"
    questions_path = RUNTIME / "onboarding_questions.jsonl"
    draft_path = RUNTIME / "semantic_pack.draft.yaml"
    eval_json = RUNTIME / "eval_report.json"
    eval_md = RUNTIME / "eval_report.md"

    _run_builder("scan", "--source", str(DEMO_DATA), "--out", str(scan_path))
    _run_builder("profile", "--scan", str(scan_path), "--out", str(profiles_path))
    _run_builder(
        "infer-semantics",
        "--profiles", str(profiles_path),
        "--hypotheses-out", str(hypotheses_path),
        "--questions-out", str(questions_path),
        "--provider", "mock",
    )
    _run_builder(
        "build-pack",
        "--profiles", str(profiles_path),
        "--semantic-hypotheses", str(hypotheses_path),
        "--onboarding-questions", str(questions_path),
        "--out", str(draft_path),
    )

    pack = load_pack_yaml(PACK_ROOT / "demo_company" / "revenue.v0_1.yaml")
    evidence = file_evidence_ref(
        "demo-profile-users",
        "examples/demo_data/users.csv",
        column_refs=["user_id", "signup_date", "marketing_channel"],
        notes="safe column-level pointer only; no raw row values",
    )
    proposal = create_pack_proposal(
        proposal_id="phase12.demo.confirmation",
        pack_id=pack.id,
        target_ref="term.new_customer",
        proposed_patch={"status": "reviewed", "source": "demo_confirmation"},
        evidence_refs=[evidence],
        status=ProposalStatus.REVIEWED,
        created_by="phase12-demo",
        indexable_summary="Confirm new customer basis from safe demo profile evidence.",
    )
    confirmation = HumanConfirmation(
        confirmation_id="phase12.demo.approval",
        proposal_id=proposal.proposal_id,
        status=ConfirmationStatus.APPROVED,
        reviewer="demo_reviewer",
        rationale="Approved for local demo pack lifecycle only.",
        evidence_refs=[evidence],
    )
    confirmed_proposal = record_confirmation(proposal, confirmation)
    manifest = promotion_manifest(confirmed_proposal, next_version="0.1.1")
    require_explicit_confirmation(confirmed_proposal)
    promotion = promote_pack(
        pack,
        target_status=PackStatus.APPROVED,
        confirmations=[{"confirmation_id": confirmation.confirmation_id, "target_id": proposal.proposal_id, "status": "approved", "source_ref": "demo:phase12"}],
        proposal_id=proposal.proposal_id,
        promoted_at="2026-05-09T00:00:00Z",
    )

    spaces = list_semantic_spaces(pack_root=PACK_ROOT)
    search = search_semantic_context("demo_company.revenue", "순매출 신규 고객", pack_root=PACK_ROOT, backend="keyword")
    resolved = resolve_business_terms("demo_company.revenue", ["new customer", "net revenue"], pack_root=PACK_ROOT)
    plan = plan_data_query("demo_company.revenue", "월별 신규 고객 순매출을 보여줘", role="marketing_analyst", pack_root=PACK_ROOT)
    validation = validate_sql(
        "demo_company.revenue",
        "SELECT users.email FROM users",
        role="marketing_analyst",
        pack_root=PACK_ROOT,
    )
    preview = preview_query(
        "demo_company.revenue",
        "SELECT payment_id, amount FROM payments",
        role="marketing_analyst",
        pack_root=PACK_ROOT,
        fixture_root=DEMO_DATA,
        max_rows=2,
        audit_root=RUNTIME / "preview_audit",
    )
    eval_run = run_benchmark_manifest(ROOT / "eval" / "datasets" / "demo_company_revenue.yaml")
    write_benchmark_report(eval_run, eval_json, eval_md)

    summary = {
        "ok": True,
        "artifacts": {
            "scan_report": str(scan_path.relative_to(ROOT)),
            "column_profiles": str(profiles_path.relative_to(ROOT)),
            "semantic_hypotheses": str(hypotheses_path.relative_to(ROOT)),
            "onboarding_questions": str(questions_path.relative_to(ROOT)),
            "draft_pack": str(draft_path.relative_to(ROOT)),
            "eval_json": str(eval_json.relative_to(ROOT)),
            "eval_markdown": str(eval_md.relative_to(ROOT)),
        },
        "counts": {
            "scan_datasets": len(json.loads(scan_path.read_text(encoding="utf-8"))["datasets"]),
            "profile_rows": sum(1 for _ in profiles_path.open(encoding="utf-8")),
            "hypotheses": sum(1 for _ in hypotheses_path.open(encoding="utf-8")),
            "questions": sum(1 for _ in questions_path.open(encoding="utf-8")),
            "registry_packs": len(PackStore(PACK_ROOT).list_packs()),
        },
        "lifecycle": {
            "proposal_id": confirmed_proposal.proposal_id,
            "confirmation_status": confirmation.status.value,
            "promotion_manifest": manifest,
            "promotion_target_status": promotion.pack.status.value,
            "promotion_target_version": promotion.target_version,
        },
        "mcp_like": {
            "registered_tools": inspect_registration_surface()["tools"],
            "spaces": spaces["spaces"],
            "search_top": search["results"][0]["card_id"] if search.get("results") else None,
            "resolved_terms": [item["term_id"] for item in resolved["resolved_terms"]],
            "plan_terms": plan["required_terms"],
            "plan_metrics": plan["required_metrics"],
            "blocked_sql_valid": validation["valid"],
            "blocked_sql_execution_allowed": validation["execution_allowed"],
            "preview_ok": preview.get("ok"),
            "preview_execution_allowed": preview.get("execution_allowed"),
        },
        "eval_summary": eval_run.summary,
        "safety": {
            "production_execute_query": False,
            "dashboard_ui": False,
            "saaS_multi_tenancy": False,
            "pii_raw_values_in_summary": False,
        },
    }
    summary_path = RUNTIME / "demo_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _run_builder(*args: str) -> None:
    rc = builder_main(list(args))
    if rc != 0:
        raise RuntimeError(f"semantic-builder {' '.join(args)} failed with exit code {rc}")


if __name__ == "__main__":
    raise SystemExit(main())
