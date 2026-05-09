"""PII-safe semantic hypothesis generation from Builder column profiles.

Phase 5 intentionally emits draft hypotheses and onboarding questions only. It
never executes SQL, calls external services by default, starts MCP/VDB runtimes,
or stores raw values for PII-like columns. Future PostgreSQL-origin profiles are
represented as safe source references, not live database connections.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlparse

ProfileRecord = Mapping[str, Any]
JsonObject = dict[str, Any]

_DRAFT_STATUS = "draft"
_OPEN_STATUS = "open"
_SAFE_SOURCE_KINDS = {"file", "postgresql", "bi_doc", "query_log"}
_NUMERIC_HINTS = ("amount", "revenue", "sales", "profit", "cost", "price", "total", "quantity", "qty")
_DATE_HINTS = ("date", "day", "month", "year", "created", "started", "signup", "ship")
_STATUS_HINTS = ("status", "state", "segment", "category", "type", "channel", "country", "region", "market", "plan")


class SemanticInferenceProvider(Protocol):
    """Provider contract for producing draft semantic inference artifacts."""

    name: str

    def infer(self, profile_records: Sequence[ProfileRecord]) -> dict[str, list[JsonObject]]:
        """Return hypotheses and onboarding questions for profile records."""


@dataclass(frozen=True)
class LocalProviderConfig:
    """Explicit opt-in configuration for a future local LLM provider seam.

    The config accepts common provider field names now so env/config mappings
    can be passed through directly. The seam remains opt-in and unimplemented
    until a real provider is wired in.
    """

    enabled: bool = False
    provider: str | None = None
    endpoint: str | None = None
    api_key: str | None = None
    timeout_s: float = 30.0


class LocalSemanticInferenceProvider:
    """Config-gated local provider seam.

    The seam is present so callers can wire a local-only adapter later without
    changing the pipeline. It fails loudly until enabled and implemented rather
    than silently falling back to mock or making network calls.
    """

    name = "local"

    def __init__(
        self,
        config: LocalProviderConfig | None = None,
        *,
        client: Any | None = None,
    ) -> None:
        self.config = config or LocalProviderConfig()
        self._client = client
        if not self.config.enabled:
            raise ValueError("local semantic inference provider requires explicit enabled=True config")
        if not str(self.config.model or "").strip():
            raise ValueError("local semantic inference provider requires a model")
        if not str(self.config.endpoint or "").strip():
            raise ValueError("local semantic inference provider requires an endpoint")

    def infer(self, profile_records: Sequence[ProfileRecord]) -> dict[str, list[JsonObject]]:
        payload = self._build_request_payload(profile_records)
        response = self._post_json(payload)
        return self._parse_response(response)

    def _build_request_payload(self, profile_records: Sequence[ProfileRecord]) -> JsonObject:
        return {
            "model": self.config.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a local semantic inference service. "
                        "Return only valid JSON with keys hypotheses and onboarding_questions."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "Generate draft semantic hypotheses and onboarding questions from profile records.",
                            "profiles": list(profile_records),
                            "output_schema": {
                                "hypotheses": "array of objects",
                                "onboarding_questions": "array of objects",
                            },
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                },
            ],
        }

    def _post_json(self, payload: JsonObject) -> JsonObject:
        endpoint = str(self.config.endpoint or "").strip()
        request = urllib.request.Request(
            _openai_compat_url(endpoint),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=_openai_compat_headers(self.config.api_key),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=float(self.config.timeout_s)) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
            raise ValueError(f"local semantic inference provider HTTP {exc.code}: {message}") from exc
        except urllib.error.URLError as exc:
            raise ValueError(f"local semantic inference provider request failed: {exc.reason}") from exc

        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise ValueError("local semantic inference provider returned a non-object response")
        return parsed

    def _parse_response(self, response: JsonObject) -> dict[str, list[JsonObject]]:
        content = _extract_openai_content(response)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("local semantic inference provider returned non-JSON content") from exc
        if not isinstance(parsed, dict):
            raise ValueError("local semantic inference provider response must be a JSON object")
        hypotheses = parsed.get("hypotheses", [])
        questions = parsed.get("onboarding_questions", [])
        if not isinstance(hypotheses, list) or not isinstance(questions, list):
            raise ValueError("local semantic inference provider response must contain list values")
        return {"hypotheses": hypotheses, "onboarding_questions": questions}


class DeterministicMockInferenceProvider:
    """Deterministic provider used by tests and offline CLI runs.

    It uses cautious profile heuristics instead of pretending that an LLM has
    confirmed business semantics. Every record stays status=draft and carries
    uncertainty/questions for human confirmation.
    """

    name = "mock"

    def infer(self, profile_records: Sequence[ProfileRecord]) -> dict[str, list[JsonObject]]:
        sanitized = [_sanitize_profile_record(record) for record in profile_records]
        hypotheses: list[JsonObject] = []
        questions: list[JsonObject] = []

        if not sanitized:
            questions.append(
                _question(
                    "question.empty_profiles",
                    target="semantic_pack",
                    question="No profile rows were provided. Which data source should be profiled before semantic inference?",
                    reason="Semantic hypotheses require at least one scan/profile record; the pipeline must not fabricate terms.",
                    evidence=[],
                )
            )
            return {"hypotheses": hypotheses, "onboarding_questions": questions}

        for record_index, record in enumerate(sanitized):
            table_name = str(record.get("table_name", f"table_{record_index + 1}"))
            table_ref = f"table.{_safe_id(table_name)}"
            columns = _safe_columns(record)
            evidence = [_evidence(record, record_index, None)]
            join_keys = [column for column in columns if column.get("join_key_candidate")]
            date_columns = [column for column in columns if _looks_like_date_column(column)]
            numeric_columns = [column for column in columns if _looks_like_numeric_measure(column)]
            pii_columns = [column for column in columns if _is_pii_column(column)]

            hypotheses.append(
                _hypothesis(
                    f"hyp.table.{_safe_id(table_name)}",
                    kind="table",
                    target=table_ref,
                    label=_title(table_name),
                    description=f"Draft table meaning inferred from profile metadata for {table_name}.",
                    confidence=0.62 if columns else 0.35,
                    evidence=evidence,
                    uncertainties=[
                        "confirm_business_grain",
                        *([] if join_keys else ["confirm_primary_or_join_key"]),
                    ],
                    payload={
                        "physical_name": table_name,
                        "sheet_name": record.get("sheet_name"),
                        "row_count": record.get("row_count"),
                        "column_count": len(columns),
                    },
                )
            )

            if not columns:
                questions.append(
                    _question(
                        f"question.{_safe_id(table_name)}.empty_columns",
                        target=table_ref,
                        question=f"{table_name} has no profiled columns. Should this table be excluded or rescanned?",
                        reason="A table-level hypothesis exists, but column evidence is missing.",
                        evidence=evidence,
                    )
                )

            for column_index, column in enumerate(columns):
                column_name = str(column.get("name", f"column_{column_index + 1}"))
                column_target = f"column.{_safe_id(table_name)}.{_safe_id(column_name)}"
                pii = _is_pii_column(column)
                semantic_type = _semantic_type(column_name, str(column.get("type_guess", "unknown")), pii)
                uncertainties = ["confirm_business_definition"]
                if pii:
                    uncertainties.append("confirm_pii_policy_and_allowed_usage")
                if _looks_like_numeric_measure(column):
                    uncertainties.append("confirm_metric_formula_and_aggregation")
                if _looks_like_date_column(column):
                    uncertainties.append("confirm_date_basis")

                hypotheses.append(
                    _hypothesis(
                        f"hyp.column.{_safe_id(table_name)}.{_safe_id(column_name)}",
                        kind="column",
                        target=column_target,
                        label=column_name,
                        description=f"Draft semantic role for {table_name}.{column_name}.",
                        confidence=0.7 if semantic_type != "unknown" else 0.45,
                        evidence=[_evidence(record, record_index, column_name)],
                        uncertainties=uncertainties,
                        payload={
                            "table": table_name,
                            "column": column_name,
                            "semantic_type": semantic_type,
                            "data_type": column.get("type_guess", "unknown"),
                            "pii": _pii_summary(column),
                            "profile": _safe_column_profile(column),
                        },
                    )
                )

                if pii:
                    questions.append(
                        _question(
                            f"question.{_safe_id(table_name)}.{_safe_id(column_name)}.pii_policy",
                            target=column_target,
                            question=f"Should {table_name}.{column_name} be blocked from raw-value prompts, indexing, and value dictionaries for all analyst roles?",
                            reason="The profiler marked the column as PII-like; Phase 5 must confirm policy without exposing raw values.",
                            evidence=[_evidence(record, record_index, column_name)],
                        )
                    )
                elif semantic_type in {"category", "status"}:
                    questions.append(
                        _question(
                            f"question.{_safe_id(table_name)}.{_safe_id(column_name)}.meaning",
                            target=column_target,
                            question=f"What business definition should be used for the categories in {table_name}.{column_name}?",
                            reason="Safe categorical values can suggest a dimension, but the business meaning remains unconfirmed.",
                            evidence=[_evidence(record, record_index, column_name)],
                        )
                    )

            for metric_column in numeric_columns:
                metric_name = str(metric_column.get("name", "measure"))
                metric_id = f"hyp.metric.{_safe_id(table_name)}.{_safe_id(metric_name)}"
                hypotheses.append(
                    _hypothesis(
                        metric_id,
                        kind="metric",
                        target=f"metric.{_safe_id(table_name)}.{_safe_id(metric_name)}",
                        label=_title(metric_name),
                        description=f"Possible aggregate metric based on numeric profile for {table_name}.{metric_name}.",
                        confidence=0.52,
                        evidence=[_evidence(record, record_index, str(metric_column.get("name")))],
                        uncertainties=["confirm_aggregation", "confirm_date_basis", "confirm_business_filters"],
                        payload={
                            "table": table_name,
                            "measure_column": metric_name,
                            "suggested_aggregation": "sum",
                            "candidate_date_columns": [str(column.get("name")) for column in date_columns],
                        },
                    )
                )
                questions.append(
                    _question(
                        f"question.{_safe_id(table_name)}.{_safe_id(metric_name)}.metric_definition",
                        target=f"metric.{_safe_id(table_name)}.{_safe_id(metric_name)}",
                        question=f"If {metric_name} is a metric, should it be summed, averaged, or filtered, and which date column is the reporting basis?",
                        reason="Numeric profile evidence is insufficient to confirm a metric formula or date basis.",
                        evidence=[_evidence(record, record_index, str(metric_column.get("name")))],
                    )
                )

            for join_key in join_keys:
                join_name = str(join_key.get("name", "id"))
                questions.append(
                    _question(
                        f"question.{_safe_id(table_name)}.{_safe_id(join_name)}.join",
                        target=f"column.{_safe_id(table_name)}.{_safe_id(join_name)}",
                        question=f"Which table should {table_name}.{join_name} join to, and is the relationship one-to-one or one-to-many?",
                        reason="Join-key-like profile evidence cannot confirm relationship cardinality by itself.",
                        evidence=[_evidence(record, record_index, join_name)],
                    )
                )

            if pii_columns:
                hypotheses.append(
                    _hypothesis(
                        f"hyp.policy.{_safe_id(table_name)}.pii_blocklist",
                        kind="policy",
                        target=f"policy.{_safe_id(table_name)}.pii_blocklist",
                        label=f"{_title(table_name)} PII blocklist",
                        description="Draft policy requiring raw-value blocking for PII-like columns.",
                        confidence=0.78,
                        evidence=[_evidence(record, record_index, str(column.get("name"))) for column in pii_columns],
                        uncertainties=["confirm_role_scope", "confirm_allowed_aggregations"],
                        payload={
                            "blocked_columns": [f"{table_name}.{column.get('name')}" for column in pii_columns],
                            "raw_value_storage": "blocked",
                        },
                    )
                )

        hypotheses.extend(_join_hypotheses(sanitized))
        return {"hypotheses": hypotheses, "onboarding_questions": _dedupe_by_id(questions)}


def generate_semantic_inference(
    profile_records: Sequence[ProfileRecord],
    *,
    provider: SemanticInferenceProvider | None = None,
) -> dict[str, list[JsonObject]]:
    """Generate semantic hypotheses/questions with a deterministic default provider."""
    selected_provider = provider or DeterministicMockInferenceProvider()
    result = selected_provider.infer(profile_records)
    return {
        "hypotheses": _dedupe_by_id(result.get("hypotheses", [])),
        "onboarding_questions": _dedupe_by_id(result.get("onboarding_questions", [])),
    }


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _coerce_float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def _coerce_int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def load_profile_jsonl(path: str | Path) -> list[JsonObject]:
    """Load profile JSONL and fail explicitly on malformed rows."""
    profile_path = Path(path)
    records: list[JsonObject] = []
    for line_number, line in enumerate(profile_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"Profile JSONL row {line_number} must be a JSON object")
        records.append(payload)
    return records


def write_jsonl(records: Sequence[Mapping[str, Any]], path: str | Path) -> None:
    """Write stable JSONL records for generated artifacts."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(dict(record), ensure_ascii=False, sort_keys=True) + "\n")


def _sanitize_profile_record(record: ProfileRecord) -> JsonObject:
    sanitized = dict(record)
    sanitized["columns"] = [_sanitize_column(column) for column in _safe_columns(record)]
    return sanitized


def _sanitize_column(column: Mapping[str, Any]) -> JsonObject:
    payload = dict(column)
    if _is_pii_column(payload):
        # PII profiles may contain stale safe-value/extrema fields from older
        # runs; drop them defensively before prompt/artifact generation.
        payload["top_values"] = []
        payload.pop("numeric_min", None)
        payload.pop("numeric_max", None)
        payload.pop("date_min", None)
        payload.pop("date_max", None)
    return payload


def _safe_columns(record: ProfileRecord) -> list[JsonObject]:
    columns = record.get("columns", [])
    if not isinstance(columns, list):
        return []
    return [dict(column) for column in columns if isinstance(column, Mapping)]


def _hypothesis(
    record_id: str,
    *,
    kind: str,
    target: str,
    label: str,
    description: str,
    confidence: float,
    evidence: list[JsonObject],
    uncertainties: list[str],
    payload: JsonObject,
) -> JsonObject:
    return {
        "id": record_id,
        "kind": kind,
        "target": target,
        "label": label,
        "description": description,
        "confidence": round(confidence, 2),
        "status": _DRAFT_STATUS,
        "source": "deterministic_mock_provider",
        "evidence": evidence,
        "uncertainties": sorted(set(uncertainties)),
        "payload": payload,
    }


def _question(record_id: str, *, target: str, question: str, reason: str, evidence: list[JsonObject]) -> JsonObject:
    return {
        "id": record_id,
        "target": target,
        "question": question,
        "reason": reason,
        "status": _OPEN_STATUS,
        "evidence": evidence,
    }


def _evidence(record: ProfileRecord, record_index: int, column_name: str | None) -> JsonObject:
    source_ref = _source_ref(record)
    evidence: JsonObject = {
        "source_ref": source_ref,
        "profile_row": record_index + 1,
        "table_name": record.get("table_name"),
    }
    if record.get("sheet_name") is not None:
        evidence["sheet_name"] = record.get("sheet_name")
    if column_name is not None:
        evidence["column_name"] = column_name
    return evidence


def _source_ref(record: ProfileRecord) -> JsonObject:
    raw = record.get("source_ref") if isinstance(record.get("source_ref"), Mapping) else {}
    source_kind = str(raw.get("type") or record.get("source_kind") or ("postgresql" if record.get("postgresql") else "file"))
    if source_kind not in _SAFE_SOURCE_KINDS:
        source_kind = "file"
    name = raw.get("name") or record.get("path") or record.get("source_name") or record.get("table_name") or "profile_jsonl"
    return {"type": source_kind, "name": str(name), "safe_reference": True}


def _semantic_type(name: str, type_guess: str, pii: bool) -> str:
    normalized = _safe_id(name)
    if pii:
        return "pii"
    if _contains_any(normalized, _DATE_HINTS) or type_guess == "date":
        return "date"
    if _contains_any(normalized, _NUMERIC_HINTS) and type_guess == "number":
        return "measure"
    if normalized.endswith("_id") or normalized == "id":
        return "identifier"
    if _contains_any(normalized, _STATUS_HINTS):
        return "status" if "status" in normalized or "state" in normalized else "category"
    return type_guess if type_guess in {"number", "string", "boolean"} else "unknown"


def _safe_column_profile(column: Mapping[str, Any]) -> JsonObject:
    profile = {
        "null_ratio": column.get("null_ratio"),
        "cardinality_estimate": column.get("cardinality_estimate"),
        "join_key_candidate": bool(column.get("join_key_candidate")),
    }
    if not _is_pii_column(column):
        for key in ("numeric_min", "numeric_max", "date_min", "date_max", "top_values"):
            if key in column:
                profile[key] = column[key]
    else:
        profile["raw_values"] = "blocked"
    return profile


def _pii_summary(column: Mapping[str, Any]) -> JsonObject:
    pii = column.get("pii") if isinstance(column.get("pii"), Mapping) else {}
    return {
        "is_candidate": bool(pii.get("is_pii")),
        "categories": list(pii.get("categories", [])) if isinstance(pii.get("categories", []), list) else [],
        "raw_value_storage": "blocked" if pii.get("is_pii") else "allowed",
    }


def _join_hypotheses(records: Sequence[ProfileRecord]) -> list[JsonObject]:
    by_key: dict[str, list[tuple[int, ProfileRecord, JsonObject]]] = {}
    for record_index, record in enumerate(records):
        for column in _safe_columns(record):
            name = str(column.get("name", ""))
            if column.get("join_key_candidate") or _safe_id(name).endswith("_id"):
                by_key.setdefault(_safe_id(name), []).append((record_index, record, column))

    hypotheses: list[JsonObject] = []
    for key, entries in sorted(by_key.items()):
        tables = sorted({str(record.get("table_name")) for _, record, _ in entries if record.get("table_name")})
        if len(tables) < 2:
            continue
        evidence = [_evidence(record, record_index, str(column.get("name"))) for record_index, record, column in entries]
        hypotheses.append(
            _hypothesis(
                f"hyp.join.{key}",
                kind="join",
                target=f"join.{key}",
                label=f"Candidate join on {key}",
                description=f"Possible join relationship across tables sharing {key}.",
                confidence=0.5,
                evidence=evidence,
                uncertainties=["confirm_join_cardinality", "confirm_join_condition"],
                payload={"join_key": key, "candidate_tables": tables},
            )
        )
    return hypotheses


def _openai_compat_url(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if not parsed.scheme:
        raise ValueError("local semantic inference provider endpoint must include a URL scheme")
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/v1/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _openai_compat_headers(api_key: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = str(api_key or "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _extract_openai_content(response: Mapping[str, Any]) -> str:
    if "output_text" in response and response["output_text"] is not None:
        return str(response["output_text"])
    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, Mapping):
            message = first.get("message")
            if isinstance(message, Mapping) and message.get("content") is not None:
                return str(message["content"])
            text = first.get("text")
            if text is not None:
                return str(text)
    raise ValueError("local semantic inference provider response did not include assistant content")


def _dedupe_by_id(records: Sequence[Mapping[str, Any]]) -> list[JsonObject]:
    seen: set[str] = set()
    output: list[JsonObject] = []
    for record in records:
        record_id = str(record.get("id", ""))
        if not record_id or record_id in seen:
            continue
        seen.add(record_id)
        output.append(dict(record))
    return output


def _is_pii_column(column: Mapping[str, Any]) -> bool:
    pii = column.get("pii")
    return isinstance(pii, Mapping) and bool(pii.get("is_pii"))


def _looks_like_numeric_measure(column: Mapping[str, Any]) -> bool:
    return column.get("type_guess") == "number" and _contains_any(_safe_id(str(column.get("name", ""))), _NUMERIC_HINTS)


def _looks_like_date_column(column: Mapping[str, Any]) -> bool:
    return column.get("type_guess") == "date" or _contains_any(_safe_id(str(column.get("name", ""))), _DATE_HINTS)


def _contains_any(value: str, hints: Sequence[str]) -> bool:
    return any(hint in value for hint in hints)


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return safe or "unknown"


def _title(value: str) -> str:
    return re.sub(r"[_-]+", " ", value).strip().title() or value
