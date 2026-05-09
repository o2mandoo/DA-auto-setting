"""Build draft Semantic Packs from local file column profiles.

This module is intentionally deterministic and file-only. It does not execute
SQL, connect to databases, call LLMs, start MCP runtimes, or create VDB indexes.
PII-like columns are represented as blocked columns and are never emitted as raw
value dictionaries.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


def load_profile_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load profile records written by the local profile CLI command."""
    return load_jsonl_records(path, record_name="Profile")


def load_jsonl_records(path: str | Path, *, record_name: str = "JSONL") -> list[dict[str, Any]]:
    """Load object records from JSONL without accepting array/string payloads."""
    profile_path = Path(path)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(profile_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{record_name} record at {profile_path}:{line_number} must be an object")
        records.append(payload)
    return records


def write_semantic_pack_yaml(pack: Mapping[str, Any], path: str | Path) -> None:
    """Write a Semantic Pack document as YAML without reordering generated cards."""
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(yaml.safe_dump(dict(pack), allow_unicode=True, sort_keys=False), encoding="utf-8")


def build_semantic_pack_draft(
    profile_records: Iterable[Mapping[str, Any]],
    *,
    # Keep the default draft id adjacent to the approved demo pack without
    # sorting ahead of it in local registries that load every YAML file under
    # semantic_packs/. This avoids a Phase 4 generated artifact silently
    # changing Phase 1/2 default-pack behavior.
    pack_id: str = "demo_company.revenue_draft",
    version: str = "0.1.0",
    title: str = "Builder Draft Semantic Pack",
    locale: str = "ko-KR",
) -> dict[str, Any]:
    """Create a contract-compatible draft pack from PII-safe profile records."""
    records = [dict(record) for record in profile_records]
    tables: list[dict[str, Any]] = []
    columns: list[dict[str, Any]] = []
    value_dictionaries: list[dict[str, Any]] = []
    blocked_columns: list[str] = []

    for record in records:
        table_name = _safe_name(str(record["table_name"]))
        profile_columns = [dict(column) for column in record.get("columns", [])]
        column_names = [_safe_name(str(column["name"])) for column in profile_columns]
        table_pii = any(_is_pii(column) for column in profile_columns)

        tables.append(
            {
                "id": f"table.{table_name}",
                "space_id": "local_files",
                "physical_name": table_name,
                "title": _title_from_name(table_name),
                "description": "Draft table inferred from local file input.",
                "role": _guess_table_role(table_name),
                "grain": "one row per source record",
                "primary_key": _primary_key(column_names),
                "columns": column_names,
                "pii_level": "high" if table_pii else "none",
                "status": "draft",
                "confidence": 0.5,
            }
        )

        for column in profile_columns:
            column_name = _safe_name(str(column["name"]))
            column_ref = f"{table_name}.{column_name}"
            pii = _is_pii(column)
            if pii:
                blocked_columns.append(column_ref)

            columns.append(
                {
                    "id": f"column.{table_name}.{column_name}",
                    "table": table_name,
                    "name": column_name,
                    "data_type": _contract_data_type(str(column.get("type_guess", "unknown"))),
                    "nullable": bool(column.get("null_count", 0)),
                    "semantic_type": _semantic_type(column_name, column),
                    "description": _column_description(column_name, column),
                    "profile": _contract_profile(column),
                    "pii": {
                        "is_candidate": pii,
                        "raw_value_storage": "blocked" if pii else "allowed",
                        "masking_notes": "Raw values blocked by Builder PII policy." if pii else None,
                    },
                    "status": "draft",
                    "confidence": 0.5,
                }
            )

            top_values = list(column.get("top_values") or [])
            if top_values and not pii:
                value_dictionaries.append(
                    {
                        "id": f"value_dict.{table_name}.{column_name}",
                        "table": table_name,
                        "column": column_name,
                        "values": [
                            {
                                "value": item["value"],
                                "label": str(item["value"]),
                                "count": item.get("count"),
                                "source": "profiler",
                                "status": "draft",
                            }
                            for item in top_values
                            if "value" in item
                        ],
                    }
                )

    policies = []
    if blocked_columns:
        policies.append(
            {
                "id": "policy.builder_pii_blocklist",
                "applies_to": {"roles": ["builder_user"]},
                "allowed_tables": [table["physical_name"] for table in tables],
                "blocked_columns": sorted(set(blocked_columns)),
                "notes": ["Builder blocks raw PII-like values and excludes them from value dictionaries."],
            }
        )

    return {
        "semantic_pack": {
            "id": pack_id,
            "version": version,
            "status": "draft",
            "title": title,
            "description": "Draft Semantic Pack generated from local file profiles.",
            "locale": locale,
            "owners": [{"role": "builder", "name": "Semantic Builder"}],
            "source_refs": [{"type": "file", "name": "local_file_profiles", "safe_reference": True}],
            "spaces": [{"id": "local_files", "title": "Local File Inputs"}],
            "tables": tables,
            "columns": columns,
            "value_dictionaries": value_dictionaries,
            "metrics": [],
            "business_terms": [],
            "join_recipes": _join_recipes(records),
            "policies": policies,
            "verified_queries": [],
            "reverse_questions": [],
            "metadata": {"generator": "semantic_builder", "phase": "4", "source": "local_file_profiles"},
        }
    }


def attach_inference_artifacts_to_draft_pack(
    pack_document: Mapping[str, Any],
    *,
    semantic_hypotheses: Iterable[Mapping[str, Any]] | None = None,
    onboarding_questions: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attach Phase 5 inference artifacts as draft-only metadata proposals.

    Phase 5 may surface LLM-assisted hypotheses/questions, but it must not
    promote them into approved pack cards or mutate confirmed business truth.
    Keeping them under metadata makes the YAML contract-compatible while Phase 6
    designs explicit human confirmation/promotion semantics.
    """
    document = copy.deepcopy(dict(pack_document))
    pack = document.get("semantic_pack") if isinstance(document.get("semantic_pack"), dict) else document
    if not isinstance(pack, dict):
        raise ValueError("Semantic Pack document must contain a semantic_pack mapping or be a pack mapping")

    status = str(pack.get("status", "draft"))
    if status != "draft":
        # Safety boundary: Phase 5 proposals are advisory and may not alter
        # reviewed/approved source-of-truth packs without a later confirmation flow.
        raise ValueError(f"Phase 5 inference artifacts can only be attached to draft packs, got status={status!r}")

    hypotheses = [_sanitize_inference_artifact(item) for item in (semantic_hypotheses or [])]
    questions = [_sanitize_inference_artifact(item) for item in (onboarding_questions or [])]
    for item in hypotheses:
        item["status"] = "draft"
    for item in questions:
        item["status"] = "open"

    if not hypotheses and not questions:
        return document

    metadata = dict(pack.get("metadata") or {})
    existing = dict(metadata.get("phase5_semantic_inference") or {})
    if hypotheses:
        existing["semantic_hypotheses"] = hypotheses
    if questions:
        existing["onboarding_questions"] = questions
    existing.update(
        {
            "status": "draft",
            "proposals_only": True,
            "auto_promoted": False,
            "pii_payload_policy": "redacted_or_excluded",
            "notes": [
                "Phase 5 stores inference artifacts as draft metadata proposals only.",
                "Human confirmation and card promotion are intentionally deferred to later phases.",
            ],
        }
    )
    metadata["phase5_semantic_inference"] = existing
    metadata["phase"] = "5"
    pack["metadata"] = metadata
    return document


_PII_TEXT_PATTERNS = [
    re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE),
]
_PHONE_CANDIDATE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d\-().\s]{7,}\d)(?!\d)")

_RAW_VALUE_KEYS = {
    "raw_value",
    "raw_values",
    "sample_value",
    "sample_values",
    "example_value",
    "example_values",
    "top_values",
    "values",
    "rows",
    "records",
    "prompt",
    "completion",
    "messages",
}


def _sanitize_inference_artifact(value: Any) -> Any:
    """Return a JSON/YAML-safe copy that excludes obvious raw-value payloads."""
    if isinstance(value, Mapping):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            safe_key = _safe_metadata_key(str(key))
            if safe_key in _RAW_VALUE_KEYS:
                # Provider artifacts may carry sample values for model reasoning,
                # but Builder metadata must remain future-indexing safe and PII-free.
                continue
            sanitized[safe_key] = _sanitize_inference_artifact(item)
        return sanitized
    if isinstance(value, list):
        return [_sanitize_inference_artifact(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_inference_artifact(item) for item in value]
    if isinstance(value, str):
        return _redact_pii_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_pii_text(str(value))


def _redact_pii_text(value: str) -> str:
    redacted = value
    for pattern in _PII_TEXT_PATTERNS:
        redacted = pattern.sub("[redacted]", redacted)
    return _PHONE_CANDIDATE_RE.sub(_redact_phone_match, redacted)


def _redact_phone_match(match: re.Match[str]) -> str:
    candidate = match.group(0)
    digit_count = len(re.sub(r"\D", "", candidate))
    # Avoid treating compact ISO dates such as 2026-01-01 as phone numbers.
    return "[redacted]" if digit_count >= 10 else candidate


def _safe_metadata_key(value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip().lower()).strip("_")
    return safe or "field"


def _join_recipes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_column: dict[str, list[str]] = {}
    for record in records:
        table_name = _safe_name(str(record["table_name"]))
        for column in record.get("columns", []):
            name = _safe_name(str(column.get("name", "")))
            if name.endswith("_id"):
                by_column.setdefault(name, []).append(table_name)

    recipes: list[dict[str, Any]] = []
    for column_name, table_names in sorted(by_column.items()):
        unique_tables = sorted(set(table_names))
        if len(unique_tables) < 2:
            continue
        left, right = unique_tables[:2]
        recipes.append(
            {
                "id": f"join.{left}_{right}_{column_name}",
                "left_table": left,
                "right_table": right,
                "join_type": "many_to_many",
                "condition": f"{left}.{column_name} = {right}.{column_name}",
                "recommended": False,
                "warnings": ["Draft join candidate inferred from matching *_id column names; human review required."],
            }
        )
    return recipes


def _contract_profile(column: Mapping[str, Any]) -> dict[str, Any]:
    profile: dict[str, Any] = {
        "null_ratio": float(column.get("null_ratio", 0.0)),
        "cardinality": int(column.get("cardinality_estimate", 0)),
        "top_values_safe": bool(column.get("top_values")) and not _is_pii(column),
    }
    if _is_pii(column):
        # Defense in depth: even if an older/stale profile JSONL includes raw
        # extrema for PII, draft packs must not persist those values.
        return profile
    if "numeric_min" in column:
        profile["min_value"] = column["numeric_min"]
    elif "date_min" in column:
        profile["min_value"] = column["date_min"]
    if "numeric_max" in column:
        profile["max_value"] = column["numeric_max"]
    elif "date_max" in column:
        profile["max_value"] = column["date_max"]
    return profile


def _contract_data_type(type_guess: str) -> str:
    return {
        "number": "numeric",
        "date": "date",
        "boolean": "boolean",
        "string": "string",
        "unknown": "string",
    }.get(type_guess, "string")


def _semantic_type(column_name: str, column: Mapping[str, Any]) -> str | None:
    pii_categories = set((column.get("pii") or {}).get("categories") or [])
    if "email" in pii_categories:
        return "email"
    if "phone" in pii_categories:
        return "phone"
    if "person_name" in pii_categories:
        return "person_name"
    if column.get("join_key_candidate"):
        return "identifier"
    if str(column.get("type_guess")) == "date":
        return "date"
    if column_name.endswith("_id"):
        return "foreign_key_candidate"
    return None


def _column_description(column_name: str, column: Mapping[str, Any]) -> str:
    if _is_pii(column):
        return "PII-like column detected by the local profiler; raw values are blocked."
    source_name = str(column.get("source_column_name") or "").strip()
    # Keep human-readable source names in the description when the normalized
    # card id has to fall back to a safe ASCII field token for Korean workbook
    # columns. This preserves searchability without reintroducing raw values.
    if source_name and source_name != column_name:
        return f"Draft column inferred from local file profile for {source_name} ({column_name})."
    return f"Draft column inferred from local file profile for {column_name}."


def _is_pii(column: Mapping[str, Any]) -> bool:
    return bool((column.get("pii") or {}).get("is_pii"))


def _primary_key(column_names: list[str]) -> str | None:
    for name in column_names:
        if name == "id" or name.endswith("_id"):
            return name
    return None


def _guess_table_role(table_name: str) -> str:
    if table_name.endswith("s") and any(token in table_name for token in ("payment", "order", "event", "fact")):
        return "fact"
    return "dimension"


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^0-9A-Za-z_]+", "_", value.strip().lower()).strip("_")
    return safe or "field"


def _title_from_name(value: str) -> str:
    return " ".join(part.capitalize() for part in value.split("_") if part) or value
