"""Physical-schema-only baseline SQL generation for product comparisons.

The baseline runner is intentionally weaker than the Semantic Pack powered
system: it receives physical table/column shape only, stores the candidate, and
marks every result as not executed. If a caller explicitly selects a non-mock
provider, configuration failures are raised with evidence instead of silently
falling back to mock output.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Iterable, Protocol

from semantic_contracts import SemanticPack  # type: ignore[import-untyped]
from semantic_registry.query_planner import load_space_packs
from semantic_registry.store import DEFAULT_PACK_ROOT

_FORBIDDEN_BASELINE_CONTEXT = (
    "semantic_pack",
    "business_terms",
    "metric.",
    "value_dictionary",
    "policy.",
    "verified_query",
    "human_confirmation",
    "reverse_question",
)


class BaselineProviderConfigurationError(RuntimeError):
    """Raised when an explicitly selected provider is not configured."""


@dataclass(frozen=True)
class BaselineRiskNote:
    category: str
    severity: str
    message: str
    evidence: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BaselinePromptContext:
    question: str
    physical_schema_snapshot: list[dict[str, Any]]
    dialect: str = "postgres"
    schema_source: str = "physical_schema_only"
    forbidden_context: tuple[str, ...] = _FORBIDDEN_BASELINE_CONTEXT

    def build_prompt(self) -> str:
        lines = [
            "You are a generic SQL generator.",
            "Use only the physical tables and columns listed below.",
            "Do not assume business terms, metric formulas, policies, verified queries, or human confirmations.",
            f"Dialect: {self.dialect}",
            f"Question: {self.question}",
            "Physical schema:",
        ]
        for table in self.physical_schema_snapshot:
            columns = ", ".join(f"{column['name']}:{column.get('data_type', 'unknown')}" for column in table.get("columns", []))
            lines.append(f"- {table['table_name']}({columns})")
        return "\n".join(lines)

    def assert_no_semantic_context_leak(self) -> None:
        prompt = self.build_prompt().casefold()
        leaked = [marker for marker in self.forbidden_context if marker.casefold() in prompt]
        if leaked:
            raise ValueError(f"baseline prompt includes forbidden semantic context markers: {leaked}")


@dataclass(frozen=True)
class BaselineSqlCandidate:
    question: str
    physical_schema_snapshot: list[dict[str, Any]]
    generated_sql: str
    provider: str
    generated_at: str
    warnings: list[str] = field(default_factory=list)
    risk_notes: list[BaselineRiskNote] = field(default_factory=list)
    question_id: str | None = None
    domain_id: str | None = None
    not_executed: bool = True

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["not_executed"] = True
        return data


@dataclass(frozen=True)
class BaselineGenerationResult:
    candidate: BaselineSqlCandidate
    prompt: str
    provider: str
    not_executed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate": self.candidate.to_dict(),
            "prompt": self.prompt,
            "provider": self.provider,
            "not_executed": True,
        }


class BaselineProvider(Protocol):
    provider_name: str

    def generate(self, context: BaselinePromptContext) -> BaselineGenerationResult:
        ...


class MockBaselineProvider:
    """Deterministic offline baseline used only when no explicit provider is selected."""

    provider_name = "mock"

    def generate(self, context: BaselinePromptContext) -> BaselineGenerationResult:
        context.assert_no_semantic_context_leak()
        sql, notes = _mock_sql_for_question(context.question, context.physical_schema_snapshot)
        candidate = BaselineSqlCandidate(
            question=context.question,
            physical_schema_snapshot=context.physical_schema_snapshot,
            generated_sql=sql,
            provider=self.provider_name,
            generated_at=_utc_now(),
            warnings=["physical_schema_only", "baseline_not_executed"],
            risk_notes=notes,
            not_executed=True,
        )
        return BaselineGenerationResult(candidate=candidate, prompt=context.build_prompt(), provider=self.provider_name)


class LocalLLMBaselineProvider:
    """Explicit local provider placeholder.

    The repo cannot assume another user's local serving URL/model. Selecting this
    provider without endpoint and model is a configuration error, not a mock
    downgrade. Actual HTTP integration can be added later behind this contract.
    """

    provider_name = "local"

    def __init__(self, *, endpoint: str | None = None, model: str | None = None) -> None:
        self.endpoint = endpoint
        self.model = model

    def generate(self, context: BaselinePromptContext) -> BaselineGenerationResult:
        if not self.endpoint or not self.model:
            raise BaselineProviderConfigurationError(
                "explicit baseline provider 'local' requires endpoint and model; no fallback was used"
            )
        raise BaselineProviderConfigurationError(
            "explicit baseline provider 'local' is configured but HTTP generation is not implemented in this productization phase"
        )


class BaselineStore:
    """Append-only JSONL store for baseline candidates."""

    def __init__(self, root: str | Path = Path("runtime") / "baseline") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def append(self, result: BaselineGenerationResult, *, stream_name: str = "baseline_candidates") -> Path:
        path = self.root / f"{stream_name}.jsonl"
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(_jsonable(result), ensure_ascii=False, sort_keys=True) + "\n")
        return path

    def load(self, *, stream_name: str = "baseline_candidates") -> list[dict[str, Any]]:
        path = self.root / f"{stream_name}.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_physical_schema_snapshot(pack: SemanticPack) -> list[dict[str, Any]]:
    """Extract table/column shape only; no semantic definitions or policies."""

    columns_by_table: dict[str, list[dict[str, str]]] = {}
    for column in pack.columns:
        columns_by_table.setdefault(column.table, []).append({"name": column.name, "data_type": column.data_type})
    snapshot = []
    for table in pack.tables:
        snapshot.append(
            {
                "table_name": table.physical_name,
                "columns": sorted(columns_by_table.get(table.physical_name, []), key=lambda item: item["name"]),
            }
        )
    return sorted(snapshot, key=lambda item: item["table_name"])


def generate_baseline_sql(
    question: str,
    *,
    space_id: str = "demo_company.revenue",
    role: str | None = None,  # noqa: ARG001 - role is not allowed into baseline context.
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    provider_name: str | None = None,
    provider_config: dict[str, Any] | None = None,
    store_root: str | Path | None = None,
) -> BaselineGenerationResult:
    """Generate and optionally store a baseline candidate without execution."""

    packs = load_space_packs(space_id, pack_root)
    snapshot = [table for pack in packs for table in build_physical_schema_snapshot(pack)]
    context = BaselinePromptContext(question=question, physical_schema_snapshot=snapshot)
    provider = _select_provider(provider_name, provider_config or {})
    result = provider.generate(context)
    if store_root is not None:
        BaselineStore(store_root).append(result)
    return result


def _select_provider(provider_name: str | None, provider_config: dict[str, Any]) -> BaselineProvider:
    if provider_name in (None, "", "mock"):
        return MockBaselineProvider()
    if provider_name == "local":
        return LocalLLMBaselineProvider(endpoint=provider_config.get("endpoint"), model=provider_config.get("model"))
    raise BaselineProviderConfigurationError(f"unsupported explicit baseline provider {provider_name!r}; no fallback was used")


def _mock_sql_for_question(question: str, snapshot: Iterable[dict[str, Any]]) -> tuple[str, list[BaselineRiskNote]]:
    text = question.casefold()
    table_names = {table["table_name"] for table in snapshot}
    notes: list[BaselineRiskNote] = []
    if "delete" in text or "삭제" in text:
        notes.append(BaselineRiskNote("safety", "high", "Baseline model drafted non-SELECT SQL from the question."))
        return "DELETE FROM users WHERE created_at < CURRENT_DATE - INTERVAL '1 year'", notes
    if "email" in text or "이메일" in text:
        notes.append(BaselineRiskNote("pii", "high", "Baseline selected a likely PII column from physical schema."))
        return "SELECT users.email FROM users", notes
    if ("신규" in text or "new customer" in text) and ("순매출" in text or "net revenue" in text or "매출" in text):
        notes.append(BaselineRiskNote("date_basis", "high", "Baseline uses users.created_at instead of confirmed first-paid date."))
        notes.append(BaselineRiskNote("metric_basis", "high", "Baseline sums gross amount and misses refund/discount columns."))
        return (
            "SELECT DATE_TRUNC('month', users.created_at) AS month, "
            "SUM(payments.amount) AS revenue FROM users "
            "JOIN payments ON users.user_id = payments.user_id "
            "WHERE users.created_at >= {start_date} AND users.created_at < {end_date} "
            "GROUP BY 1",
            notes,
        )
    if "매출" in text or "revenue" in text:
        notes.append(BaselineRiskNote("metric_basis", "medium", "Baseline picks gross payment amount without semantic metric context."))
        return "SELECT SUM(payments.amount) AS revenue FROM payments", notes
    first_table = sorted(table_names)[0] if table_names else "unknown_table"
    notes.append(BaselineRiskNote("missing_semantic_context", "medium", "Baseline only counted rows because no semantic context was provided."))
    return f"SELECT COUNT(*) AS row_count FROM {first_table}", notes


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, dict):
        return {key: _jsonable(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(child) for child in value]
    return value


__all__ = [
    "BaselineGenerationResult",
    "BaselinePromptContext",
    "BaselineProviderConfigurationError",
    "BaselineRiskNote",
    "BaselineSqlCandidate",
    "BaselineStore",
    "MockBaselineProvider",
    "build_physical_schema_snapshot",
    "generate_baseline_sql",
]
