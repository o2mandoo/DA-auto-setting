"""Stdlib HTTP adapter for local Semantic Registry product routes.

The adapter is intentionally thin:
- it serves process health and readiness checks,
- it exposes an OpenAPI-like route inventory generated from the current
  product API surface,
- and it delegates POST routes to ``semantic_registry.product.api``.

The module does not import or depend on web frameworks. It can be smoke-tested
in-process with ``python -m semantic_registry.product.http_adapter --check`` or
served with the optional stdlib HTTP server entrypoint.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable, Sequence

from semantic_registry.product.api import API_ENDPOINTS, handle_product_api
from semantic_registry.store import DEFAULT_PACK_ROOT, PackStore

ADAPTER_NAME = "semantic_registry_http_adapter"
CORRELATION_HEADER = "X-Correlation-ID"
AUDIT_FILENAME = "audit.jsonl"
DEFAULT_AUDIT_ROOT = Path("runtime") / "product_http_adapter"


@dataclass(frozen=True)
class AdapterError:
    """Typed adapter error payload."""

    code: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": _json_safe(self.details),
        }


@dataclass(frozen=True)
class AdapterResponse:
    """Transport-neutral response envelope for the HTTP adapter."""

    status_code: int
    body: dict[str, Any]
    headers: dict[str, str] = field(default_factory=dict)

    def to_http(self) -> tuple[int, dict[str, str], bytes]:
        payload = json.dumps(self.body, ensure_ascii=False, sort_keys=True).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8", **self.headers}
        headers["Content-Length"] = str(len(payload))
        return self.status_code, headers, payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "status_code": self.status_code,
            "headers": dict(self.headers),
            "body": _json_safe(self.body),
        }


class AdapterConfigError(RuntimeError):
    """Typed configuration/readiness error."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


class AdapterDependencyError(RuntimeError):
    """Typed dependency/readiness error."""

    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def build_healthz_response(*, correlation_id: str | None = None) -> AdapterResponse:
    """Return a process-health response."""

    return _ok_response(
        {
            "service": ADAPTER_NAME,
            "status": "healthy",
            "pid": os.getpid(),
            "execution_allowed": False,
        },
        route="GET /healthz",
        correlation_id=correlation_id,
    )


def build_readyz_response(
    *,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    audit_root: str | Path = DEFAULT_AUDIT_ROOT,
    correlation_id: str | None = None,
) -> AdapterResponse:
    """Return readiness state or a typed explicit error."""

    try:
        ready = inspect_readiness(pack_root)
    except (AdapterConfigError, AdapterDependencyError) as exc:
        return _error_response(
            exc.code,
            exc.message,
            exc.details,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            route="GET /readyz",
            correlation_id=correlation_id,
            pack_root=pack_root,
            audit_root=audit_root,
        )
    return _ok_response(
        {
            "service": ADAPTER_NAME,
            "ready": True,
            "execution_allowed": False,
            **ready,
        },
        route="GET /readyz",
        correlation_id=correlation_id,
        pack_root=pack_root,
        audit_root=audit_root,
    )


def build_openapi_response(*, correlation_id: str | None = None) -> AdapterResponse:
    """Return a stable OpenAPI-like document from the current route inventory."""

    routes = [
        {
            "method": "GET",
            "path": "/healthz",
            "summary": "Process health check",
            "execution_allowed": False,
        },
        {
            "method": "GET",
            "path": "/readyz",
            "summary": "Pack root and config readiness check",
            "execution_allowed": False,
        },
        {
            "method": "GET",
            "path": "/openapi.json",
            "summary": "OpenAPI-like route inventory",
            "execution_allowed": False,
        },
    ]
    for route, handler in sorted(API_ENDPOINTS.items()):
        method, path = route.split(" ", 1)
        routes.append(
            {
                "method": method,
                "path": path,
                "summary": _route_summary(path),
                "operation_id": handler.__name__,
                "execution_allowed": False,
            }
        )

    paths: dict[str, dict[str, Any]] = {}
    for route in routes:
        path = route["path"]
        method = route["method"].lower()
        paths.setdefault(path, {})[method] = {
            "summary": route["summary"],
            "operationId": route.get("operation_id", route["summary"].lower().replace(" ", "_")),
            "responses": {
                "200": {"description": "Successful response"},
                "400": {"description": "Validation error"},
                "404": {"description": "Route not found"},
                "503": {"description": "Readiness/configuration error"},
            },
            "x-execution-allowed": False,
        }

    return _ok_response(
        {
            "openapi": "3.1.0",
            "info": {
                "title": "Semantic Registry Local HTTP Adapter",
                "version": "0.1.0",
            },
            "x-correlation-header": CORRELATION_HEADER,
            "x-execution-allowed": False,
            "paths": paths,
        },
        route="GET /openapi.json",
        correlation_id=correlation_id,
    )


def handle_http_request(
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    *,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    audit_root: str | Path = DEFAULT_AUDIT_ROOT,
    correlation_id: str | None = None,
) -> AdapterResponse:
    """Handle one local HTTP request without starting a server."""

    request_payload = payload or {}
    correlation_id = correlation_id or _new_correlation_id()
    route = f"{method.upper()} {path}"
    try:
        if method.upper() == "GET" and path == "/healthz":
            response = build_healthz_response(correlation_id=correlation_id)
        elif method.upper() == "GET" and path == "/readyz":
            response = build_readyz_response(pack_root=pack_root, audit_root=audit_root, correlation_id=correlation_id)
        elif method.upper() == "GET" and path == "/openapi.json":
            response = build_openapi_response(correlation_id=correlation_id)
        elif method.upper() == "POST" and route in API_ENDPOINTS:
            body = handle_product_api(method, path, request_payload, pack_root=pack_root)
            response = _ok_response(
                body,
                route=route,
                correlation_id=correlation_id,
                pack_root=pack_root,
                audit_root=audit_root,
                request_payload=request_payload,
            )
        elif route in API_ENDPOINTS:
            response = _error_response(
                "method_not_allowed",
                f"route {route} only supports POST",
                {"route": route},
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                route=route,
                correlation_id=correlation_id,
                pack_root=pack_root,
                audit_root=audit_root,
                request_payload=request_payload,
            )
        else:
            response = _error_response(
                "route_not_found",
                f"unknown adapter route {route}",
                {"route": route},
                status_code=HTTPStatus.NOT_FOUND,
                route=route,
                correlation_id=correlation_id,
                pack_root=pack_root,
                audit_root=audit_root,
                request_payload=request_payload,
            )
    except (AdapterConfigError, AdapterDependencyError) as exc:
        response = _error_response(
            exc.code,
            exc.message,
            exc.details,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            route=route,
            correlation_id=correlation_id,
            pack_root=pack_root,
            audit_root=audit_root,
            request_payload=request_payload,
        )
    except KeyError as exc:
        response = _error_response(
            "route_not_found",
            str(exc).strip("'"),
            {"route": route},
            status_code=HTTPStatus.NOT_FOUND,
            route=route,
            correlation_id=correlation_id,
            pack_root=pack_root,
            audit_root=audit_root,
            request_payload=request_payload,
        )
    except ValueError as exc:
        response = _error_response(
            "validation_error",
            str(exc),
            {"route": route},
            status_code=HTTPStatus.BAD_REQUEST,
            route=route,
            correlation_id=correlation_id,
            pack_root=pack_root,
            audit_root=audit_root,
            request_payload=request_payload,
        )
    return response


def inspect_readiness(pack_root: str | Path = DEFAULT_PACK_ROOT) -> dict[str, Any]:
    """Check local pack root readiness without falling back to another source."""

    root = Path(pack_root)
    if not root.exists():
        raise AdapterConfigError(
            "pack_root_missing",
            f"pack root {root} does not exist",
            details={"pack_root": str(root)},
        )
    if not root.is_dir():
        raise AdapterConfigError(
            "pack_root_not_directory",
            f"pack root {root} is not a directory",
            details={"pack_root": str(root)},
        )
    summary = PackStore(root).inspect_all()
    if int(summary.get("pack_count", 0)) <= 0:
        raise AdapterDependencyError(
            "no_semantic_packs_found",
            f"no Semantic Packs were discovered under {root}",
            details={"pack_root": str(root)},
        )
    return {
        "pack_root": str(root),
        "pack_count": summary["pack_count"],
        "pack_ids": summary["pack_ids"],
        "card_counts": summary["card_counts"],
    }


def run_check(*, pack_root: str | Path = DEFAULT_PACK_ROOT, audit_root: str | Path = DEFAULT_AUDIT_ROOT) -> dict[str, Any]:
    """Run a deterministic smoke check without starting the HTTP server."""

    health = handle_http_request("GET", "/healthz", {}, pack_root=pack_root, audit_root=audit_root)
    ready = handle_http_request("GET", "/readyz", {}, pack_root=pack_root, audit_root=audit_root)
    openapi = handle_http_request("GET", "/openapi.json", {}, pack_root=pack_root, audit_root=audit_root)
    sample = handle_http_request(
        "POST",
        "/api/product/answer",
        {"question": "월별 신규 고객 순매출을 보여줘", "role": "marketing_analyst"},
        pack_root=pack_root,
        audit_root=audit_root,
    )
    unknown = handle_http_request("POST", "/api/not-a-route", {}, pack_root=pack_root, audit_root=audit_root)
    validation = handle_http_request(
        "POST",
        "/api/product/answer",
        {"role": "marketing_analyst"},
        pack_root=pack_root,
        audit_root=audit_root,
    )
    return {
        "status": "ok",
        "checks": {
            "healthz": health.body["data"]["status"] == "healthy",
            "readyz": bool(ready.body["data"].get("ready")),
            "openapi_route_count": len(openapi.body["data"]["paths"]),
            "product_route": sample.status_code == HTTPStatus.OK,
            "unknown_route": unknown.status_code == HTTPStatus.NOT_FOUND,
            "validation_error": validation.status_code == HTTPStatus.BAD_REQUEST,
            "correlation_header": CORRELATION_HEADER in sample.headers,
            "audit_written": (Path(audit_root) / AUDIT_FILENAME).exists(),
        },
    }


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    audit_root: str | Path = DEFAULT_AUDIT_ROOT,
) -> None:
    """Start the optional stdlib HTTP server."""

    handler_cls = _request_handler_factory(pack_root=pack_root, audit_root=audit_root)
    server = ThreadingHTTPServer((host, port), handler_cls)
    try:
        print(json.dumps({"status": "listening", "host": host, "port": port, "pack_root": str(pack_root)}, ensure_ascii=False))
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover - interactive path
        pass
    finally:
        server.server_close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="semantic-registry-http-adapter")
    parser.add_argument("--pack-root", default=str(DEFAULT_PACK_ROOT))
    parser.add_argument("--audit-root", default=str(DEFAULT_AUDIT_ROOT))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--check", action="store_true", help="Run a deterministic smoke check and exit")
    parser.add_argument("--serve", action="store_true", help="Start the optional stdlib HTTP server")
    args = parser.parse_args(argv)

    pack_root = Path(args.pack_root)
    audit_root = Path(args.audit_root)
    if args.check or not args.serve:
        print(json.dumps(run_check(pack_root=pack_root, audit_root=audit_root), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    serve(host=args.host, port=args.port, pack_root=pack_root, audit_root=audit_root)
    return 0


def _ok_response(
    data: dict[str, Any],
    *,
    route: str,
    correlation_id: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    audit_root: str | Path = DEFAULT_AUDIT_ROOT,
    request_payload: dict[str, Any] | None = None,
) -> AdapterResponse:
    correlation_id = correlation_id or _new_correlation_id()
    body = {"ok": True, "correlation_id": correlation_id, "data": _json_safe(data)}
    headers = {CORRELATION_HEADER: correlation_id}
    _write_audit(
        route=route,
        correlation_id=correlation_id,
        status_code=HTTPStatus.OK,
        payload=request_payload or data,
        pack_root=pack_root,
        audit_root=audit_root,
    )
    return AdapterResponse(status_code=HTTPStatus.OK, body=body, headers=headers)


def _error_response(
    code: str,
    message: str,
    details: dict[str, Any] | None,
    *,
    status_code: int,
    route: str,
    correlation_id: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
    audit_root: str | Path = DEFAULT_AUDIT_ROOT,
    request_payload: dict[str, Any] | None = None,
) -> AdapterResponse:
    correlation_id = correlation_id or _new_correlation_id()
    error = AdapterError(code=code, message=message, details=details or {})
    body = {"ok": False, "correlation_id": correlation_id, "error": error.to_dict()}
    headers = {CORRELATION_HEADER: correlation_id}
    _write_audit(
        route=route,
        correlation_id=correlation_id,
        status_code=status_code,
        payload=request_payload or details or {},
        pack_root=pack_root,
        audit_root=audit_root,
        error=error.to_dict(),
    )
    return AdapterResponse(status_code=int(status_code), body=body, headers=headers)


def _write_audit(
    *,
    route: str,
    correlation_id: str,
    status_code: int,
    payload: dict[str, Any] | Any,
    pack_root: str | Path,
    audit_root: str | Path,
    error: dict[str, Any] | None = None,
) -> None:
    root = Path(audit_root)
    root.mkdir(parents=True, exist_ok=True)
    created_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    record = {
        "created_at": created_at,
        "route": route,
        "correlation_id": correlation_id,
        "status_code": int(status_code),
        "execution_allowed": False,
        "pack_root": str(pack_root),
        "payload": _redact_raw_pii(payload),
    }
    if error is not None:
        record["error"] = _redact_raw_pii(error)
    text = json.dumps(record, ensure_ascii=False, sort_keys=True)
    if "<redacted_email>" not in text and _contains_email_like(text):
        raise ValueError("audit payload still contains raw email-like PII after sanitization")
    with (root / AUDIT_FILENAME).open("a", encoding="utf-8") as file:
        file.write(text + "\n")


def _request_handler_factory(*, pack_root: str | Path, audit_root: str | Path) -> type[BaseHTTPRequestHandler]:
    class AdapterRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler naming
            self._write_response(handle_http_request("GET", self.path, {}, pack_root=pack_root, audit_root=audit_root))

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler naming
            payload = self._read_json_body()
            self._write_response(handle_http_request("POST", self.path, payload, pack_root=pack_root, audit_root=audit_root))

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 - stdlib signature
            return

        def _read_json_body(self) -> dict[str, Any]:
            try:
                content_length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                content_length = 0
            raw = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
            if not raw.strip():
                return {}
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("request body must be a JSON object")
            return data

        def _write_response(self, response: AdapterResponse) -> None:
            status, headers, payload = response.to_http()
            self.send_response(int(status))
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)

    return AdapterRequestHandler


def _route_summary(path: str) -> str:
    mapping = {
        "/api/onboarding/run": "Local onboarding run",
        "/api/confirmation/session": "Confirmation session",
        "/api/confirmation/answer": "Confirmation answer",
        "/api/pack/promote": "Pack promotion",
        "/api/product/answer": "Product answer comparison",
        "/api/product/compare-sql": "SQL comparison",
        "/api/eval/run": "Evidence evaluation",
        "/api/failure-review/run": "Failure review loop",
    }
    return mapping.get(path, path.rsplit("/", 1)[-1] or path)


def _new_correlation_id() -> str:
    return uuid.uuid4().hex[:16]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_json_safe(child) for child in value]
    if isinstance(value, tuple):
        return [_json_safe(child) for child in value]
    if hasattr(value, "model_dump"):
        return _json_safe(value.model_dump(mode="json"))
    if hasattr(value, "as_dict"):
        return _json_safe(value.as_dict())
    if hasattr(value, "to_dict"):
        return _json_safe(value.to_dict())
    if isinstance(value, Path):
        return str(value)
    return value


def _redact_raw_pii(value: Any) -> Any:
    import re

    if isinstance(value, dict):
        return {key: _redact_raw_pii(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_redact_raw_pii(child) for child in value]
    if isinstance(value, tuple):
        return [_redact_raw_pii(child) for child in value]
    if isinstance(value, str):
        value = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "<redacted_email>", value, flags=re.IGNORECASE)
        value = re.sub(r"(?<!\d)(?:\+?\d[\d\-\s().]{7,}\d)(?!\d)", "<redacted_phone>", value)
        return value
    return value


def _contains_email_like(text: str) -> bool:
    import re

    return bool(re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.IGNORECASE))


__all__ = [
    "ADAPTER_NAME",
    "AUDIT_FILENAME",
    "AdapterConfigError",
    "AdapterDependencyError",
    "AdapterError",
    "AdapterResponse",
    "CORRELATION_HEADER",
    "DEFAULT_AUDIT_ROOT",
    "build_healthz_response",
    "build_openapi_response",
    "build_readyz_response",
    "handle_http_request",
    "inspect_readiness",
    "main",
    "run_check",
    "serve",
]


if __name__ == "__main__":  # pragma: no cover - console path
    raise SystemExit(main())
