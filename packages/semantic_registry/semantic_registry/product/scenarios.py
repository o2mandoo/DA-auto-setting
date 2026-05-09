"""Failure-safe product scenario runner."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

import yaml

from semantic_registry.product.api import FAILURE_STATES, post_product_answer


@dataclass(frozen=True)
class ScenarioInput:
    question: str
    role: str = "marketing_analyst"
    include_preview: bool = False


@dataclass(frozen=True)
class ExpectedUiState:
    state: str


@dataclass(frozen=True)
class ExpectedSafetyVerdict:
    verdict: str


@dataclass(frozen=True)
class DemoNarrative:
    text: str


@dataclass(frozen=True)
class ProductScenario:
    scenario_id: str
    title: str
    input: ScenarioInput
    expected_ui_state: ExpectedUiState
    expected_safety_verdict: ExpectedSafetyVerdict
    narrative: DemoNarrative
    expected_difference_category: str | None = None
    expected_preview_status: str | None = None


@dataclass(frozen=True)
class ProductScenarioResult:
    scenario_id: str
    passed: bool
    observed_state: str | None
    expected_state: str
    observed_difference_categories: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    response: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_product_scenarios(path: str | Path = Path("eval/product_scenarios/phase17_red_team_scenarios.yaml")) -> list[ProductScenario]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    scenarios: list[ProductScenario] = []
    for item in data.get("scenarios", []):
        expected_state = item["expected_ui_state"]
        if expected_state not in FAILURE_STATES:
            raise ValueError(f"unknown expected failure state {expected_state!r}")
        scenarios.append(
            ProductScenario(
                scenario_id=item["id"],
                title=item["title"],
                input=ScenarioInput(**item["input"]),
                expected_ui_state=ExpectedUiState(expected_state),
                expected_safety_verdict=ExpectedSafetyVerdict(item["expected_safety_verdict"]),
                narrative=DemoNarrative(item["narrative"]),
                expected_difference_category=item.get("expected_difference_category"),
                expected_preview_status=item.get("expected_preview_status"),
            )
        )
    return scenarios


def run_product_scenarios(path: str | Path = Path("eval/product_scenarios/phase17_red_team_scenarios.yaml")) -> list[ProductScenarioResult]:
    results: list[ProductScenarioResult] = []
    for scenario in load_product_scenarios(path):
        response = post_product_answer(asdict(scenario.input))
        failure = response.get("failure_state_panel") or {}
        observed_state = failure.get("state")
        categories = [item.get("category") for item in response.get("difference_summary_panel", {}).get("items", [])]
        errors: list[str] = []
        if observed_state != scenario.expected_ui_state.state:
            errors.append(f"expected state {scenario.expected_ui_state.state}, observed {observed_state}")
        if scenario.expected_difference_category and scenario.expected_difference_category not in categories:
            errors.append(f"missing difference category {scenario.expected_difference_category}")
        if scenario.expected_preview_status:
            observed_preview = response.get("preview_result_panel", {}).get("status")
            if observed_preview != scenario.expected_preview_status:
                errors.append(f"expected preview {scenario.expected_preview_status}, observed {observed_preview}")
        results.append(
            ProductScenarioResult(
                scenario_id=scenario.scenario_id,
                passed=not errors,
                observed_state=observed_state,
                expected_state=scenario.expected_ui_state.state,
                observed_difference_categories=[str(category) for category in categories],
                errors=errors,
                response=response,
            )
        )
    return results


def write_product_scenario_reports(
    *,
    scenario_path: str | Path = Path("eval/product_scenarios/phase17_red_team_scenarios.yaml"),
    out_dir: str | Path = Path("reports/productization"),
) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    results = run_product_scenarios(scenario_path)
    json_path = out / "phase17_failure_safe_ux_red_team.json"
    md_path = out / "phase17_failure_safe_ux_red_team.md"
    import json

    json_path.write_text(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# Phase 17 — Failure-Safe UX + Red-Team Product Scenarios", "", f"Passed: {sum(r.passed for r in results)}/{len(results)}", ""]
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"- {status} `{result.scenario_id}`: expected `{result.expected_state}`, observed `{result.observed_state}`")
        for error in result.errors:
            lines.append(f"  - {error}")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


__all__ = [
    "DemoNarrative",
    "ExpectedSafetyVerdict",
    "ExpectedUiState",
    "ProductScenario",
    "ProductScenarioResult",
    "ScenarioInput",
    "load_product_scenarios",
    "run_product_scenarios",
    "write_product_scenario_reports",
]
