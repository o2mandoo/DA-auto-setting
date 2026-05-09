"""MCP-facing safe preview adapter over the Registry preview runtime.

This module is intentionally a thin tool boundary: Registry preview code owns
local fixture access, SQLGuard checks, policy row limits, and audit behavior.
When merge order leaves only the legacy ``semantic_registry.preview`` path
available, the response records that compatibility path explicitly.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import asdict, is_dataclass
import inspect
from pathlib import Path
from typing import Any

from semantic_registry.store import DEFAULT_PACK_ROOT
from semantic_registry.store import PackStore

DEFAULT_FIXTURE_ROOT = Path("examples") / "demo_data"


class PreviewRuntimeUnavailable(RuntimeError):
    """Raised when no Registry safe-preview runtime is importable."""


def preview_query(
    space_id: str,
    sql: str,
    role: str,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    root: str | Path | None = None,
    fixture_root: str | Path = DEFAULT_FIXTURE_ROOT,
    data_root: str | Path | None = None,
    audit_root: str | Path | None = None,
    max_rows: int | None = None,
    validated_guard_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Run a validation-gated local preview through the Registry runtime.

    ``preview_query`` is the only Phase 9 query-result MCP surface. It requires
    an explicit semantic space, caller role, and SQL text, then delegates to the
    Registry's local/demo-data preview runtime. There is deliberately no
    production database or general query execution fallback here.
    """

    _require_non_blank(space_id, "space_id")
    _require_non_blank(role, "role")
    _require_non_blank(sql, "sql")
    effective_root = root if root is not None else pack_root
    effective_fixture_root = data_root if data_root is not None else fixture_root
    effective_max_rows = max_rows or _policy_max_preview_rows(space_id=space_id, role=role, pack_root=effective_root)

    try:
        runner, adapter_warning = _load_registry_preview_query()
    except PreviewRuntimeUnavailable as exc:
        return _runtime_unavailable_response(space_id=space_id, role=role, message=str(exc))

    payload = _call_preview_runner(
        runner,
        space_id=space_id,
        sql=sql,
        role=role,
        user_role=role,
        pack_root=effective_root,
        root=effective_root,
        fixture_root=effective_fixture_root,
        data_root=effective_fixture_root,
        audit_root=audit_root,
        max_rows=effective_max_rows,
        validated_guard_result=validated_guard_result,
        require_validation=True,
    )
    response = _dump(payload)
    response.setdefault("tool_name", "preview_query")
    response.setdefault("space_id", space_id)
    response.setdefault("role", role)
    if "ok" in response and "valid" not in response:
        response["valid"] = bool(response["ok"])
    response.setdefault("preview_allowed", bool(response.get("valid", False)))
    response["execution_allowed"] = False
    response["execution_target"] = "local_fixture_only"
    # Normalize the reported row cap to the policy-derived effective limit so
    # compatibility layers cannot leak a higher default from deeper layers.
    response["limit"] = effective_max_rows
    response["limit_added"] = not _has_terminal_limit(sql)
    if "error" in response and response["error"] and "errors" not in response:
        response["errors"] = [response["error"]]
    response.setdefault("errors", [])
    response.setdefault("warnings", [])
    response["production_execution_allowed"] = False
    if adapter_warning:
        response["warnings"] = _unique([*response.get("warnings", []), adapter_warning])
    return response


def _load_registry_preview_query() -> tuple[Callable[..., Any], str | None]:
    try:
        from semantic_registry.execution import preview_query as registry_preview_query

        return registry_preview_query, None
    except ModuleNotFoundError as exc:
        if exc.name != "semantic_registry.execution":
            raise
    except ImportError as exc:
        if "preview_query" not in str(exc):
            raise

    try:
        from semantic_registry.preview import preview_query as legacy_preview_query
    except ModuleNotFoundError as exc:
        if exc.name == "semantic_registry.preview":
            raise PreviewRuntimeUnavailable(
                "No Registry preview runtime is available; no MCP fallback preview was run"
            ) from exc
        raise
    except ImportError as exc:
        if "preview_query" in str(exc):
            raise PreviewRuntimeUnavailable(
                "No Registry preview runtime is available; no MCP fallback preview was run"
            ) from exc
        raise
    return (
        legacy_preview_query,
        "semantic_registry.execution.preview_query is unavailable; used semantic_registry.preview compatibility path explicitly",
    )


def _call_preview_runner(runner: Callable[..., Any], **kwargs: Any) -> Any:
    """Call current or near-current Registry preview signatures safely.

    Phase 9 team lanes may merge the execution-layer function before or after
    this MCP wrapper. Filtering unknown keyword arguments is a compatibility shim
    for those merge-order differences; validation remains forced on whenever the
    runner accepts a validation flag.
    """

    signature = inspect.signature(runner)
    accepts_var_kwargs = any(parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values())
    if accepts_var_kwargs:
        return runner(**kwargs)
    accepted_kwargs = {key: value for key, value in kwargs.items() if key in signature.parameters}
    return runner(**accepted_kwargs)


def _policy_max_preview_rows(*, space_id: str, role: str, pack_root: str | Path) -> int:
    limits: list[int] = []
    for pack in PackStore(pack_root).load_packs():
        if pack.id != space_id and not any(getattr(space, "space_id", getattr(space, "id", None)) == space_id for space in pack.spaces):
            continue
        for policy in pack.policies:
            if role in policy.applies_to.roles:
                limits.append(int(getattr(policy, "max_preview_rows", 100)))
    return min(limits) if limits else 100


def _runtime_unavailable_response(*, space_id: str, role: str, message: str) -> dict[str, Any]:
    return {
        "tool_name": "preview_query",
        "space_id": space_id,
        "role": role,
        "status": "error",
        "valid": False,
        "preview_allowed": False,
        "truncated": False,
        "rows": [],
        "columns": [],
        "row_count": 0,
        "errors": [message],
        "warnings": ["Registry preview runtime missing; no fallback preview was run."],
        "production_execution_allowed": False,
    }


def _dump(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return dict(payload.model_dump(mode="json"))
    if is_dataclass(payload):
        return _jsonable(asdict(payload))
    if isinstance(payload, Mapping):
        return _jsonable(dict(payload))
    raise TypeError(f"preview_query runner returned unsupported payload type: {type(payload).__name__}")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _require_non_blank(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required for preview_query")
    return value.strip()


def _has_terminal_limit(sql: str) -> bool:
    import re

    return bool(re.search(r"(?is)\blimit\s+\d+\s*;?\s*$", sql))


def _unique(values: list[Any]) -> list[Any]:
    result: list[Any] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


__all__ = ["DEFAULT_FIXTURE_ROOT", "PreviewRuntimeUnavailable", "preview_query"]
