#!/usr/bin/env python3
"""Run a live n8n Docker smoke against the local product HTTP adapter.

This script intentionally uses the real n8n runtime (Docker image) rather than
simulating n8n in Python. It fails closed: missing Docker/n8n execution, missing
API routes, or unsafe workflow content produce explicit failures instead of a
silent keyword/API fallback.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAGE = "n8nio/n8n:2.19.5"
DEFAULT_OUT = REPO_ROOT / "runtime" / "n8n_live_smoke" / "latest"
DEFAULT_PRODUCT_PORT = 8765
EXPECTED_ROUTES = {
    "POST /api/onboarding/run",
    "POST /api/confirmation/session",
    "POST /api/confirmation/answer",
    "POST /api/pack/promote",
    "POST /api/product/answer",
    "POST /api/product/compare-sql",
    "POST /api/eval/run",
    "POST /api/failure-review/run",
}
FORBIDDEN_WORKFLOW_SUBSTRINGS = (
    "postgres://",
    "mysql://",
    "mongodb://",
    "password",
    "api_key",
    "apikey",
    "authorization",
    "bearer ",
)
FORBIDDEN_SQL_NODES = {
    "n8n-nodes-base.postgres",
    "n8n-nodes-base.mysql",
    "n8n-nodes-base.mssql",
    "n8n-nodes-base.sqlite",
    "n8n-nodes-base.mariadb",
    "n8n-nodes-base.oracledb",
    "n8n-nodes-base.snowflake",
}


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "returncode": self.returncode,
            "stdout_tail": self.stdout[-4000:],
            "stderr_tail": self.stderr[-4000:],
        }


@dataclass
class LiveSmokeReport:
    status: str
    generated_at: str
    runner: str
    product_api_base_url: str
    workflows_imported: list[str] = field(default_factory=list)
    workflow_ids: list[str] = field(default_factory=list)
    executed_workflows: list[dict[str, Any]] = field(default_factory=list)
    observed_routes: list[str] = field(default_factory=list)
    missing_routes: list[str] = field(default_factory=list)
    safety_checks: dict[str, bool] = field(default_factory=dict)
    explicit_fallbacks: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "generated_at": self.generated_at,
            "runner": self.runner,
            "product_api_base_url": self.product_api_base_url,
            "workflows_imported": self.workflows_imported,
            "workflow_ids": self.workflow_ids,
            "executed_workflows": self.executed_workflows,
            "observed_routes": self.observed_routes,
            "missing_routes": self.missing_routes,
            "safety_checks": self.safety_checks,
            "explicit_fallbacks": self.explicit_fallbacks,
            "errors": self.errors,
            "artifacts": self.artifacts,
        }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="n8n-live-runtime-smoke")
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--product-port", type=int, default=DEFAULT_PRODUCT_PORT)
    parser.add_argument("--workflow-dir", type=Path, default=REPO_ROOT / "n8n" / "workflows")
    parser.add_argument("--keep-runtime", action="store_true", help="Do not delete existing output directory before running")
    parser.add_argument("--skip-pull", action="store_true", help="Use an already-available Docker image; fail if absent")
    args = parser.parse_args(argv)

    out = args.out.resolve()
    if out.exists() and not args.keep_runtime:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    log_dir = out / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    report = LiveSmokeReport(
        status="failed",
        generated_at=_now_utc(),
        runner="docker",
        product_api_base_url=f"http://host.docker.internal:{args.product_port}",
        artifacts={
            "out_dir": str(out),
            "product_api_audit": str(out / "product_api_audit" / "audit.jsonl"),
            "n8n_user_dir": str(out / "n8n_user"),
        },
    )

    try:
        _preflight(args.workflow_dir)
        _assert_workflows_safe(args.workflow_dir)
        report.safety_checks.update(
            {
                "workflow_json_safe": True,
                "no_direct_sql_connector_nodes": True,
                "no_db_credentials_or_raw_pii_literals": True,
            }
        )
        _require_docker()
        if not args.skip_pull:
            _run(["docker", "pull", args.image], log_dir / "docker_pull", check=True)
        _docker_version(args.image, log_dir)

        product_proc = _start_product_adapter(args.product_port, out / "product_api_audit", log_dir)
        try:
            _wait_for_http(f"http://127.0.0.1:{args.product_port}/healthz")
            _wait_for_http(f"http://127.0.0.1:{args.product_port}/readyz")
            report.safety_checks["product_adapter_live"] = True
            report.workflows_imported = sorted(path.name for path in args.workflow_dir.glob("*.json"))
            n8n_user = out / "n8n_user"
            n8n_user.mkdir(parents=True, exist_ok=True)
            os.chmod(n8n_user, 0o777)
            _run_n8n(args.image, n8n_user, args.workflow_dir, report.product_api_base_url, ["import:workflow", "--separate", "--input=/workflows"], log_dir / "n8n_import", check=True)
            list_result = _run_n8n(args.image, n8n_user, args.workflow_dir, report.product_api_base_url, ["list:workflow", "--onlyId"], log_dir / "n8n_list", check=True)
            report.workflow_ids = [line.strip() for line in list_result.stdout.splitlines() if line.strip()]
            if len(report.workflow_ids) != len(report.workflows_imported):
                raise RuntimeError(f"imported workflow count mismatch: ids={report.workflow_ids}, files={report.workflows_imported}")
            for workflow_id in report.workflow_ids:
                result = _run_n8n(
                    args.image,
                    n8n_user,
                    args.workflow_dir,
                    report.product_api_base_url,
                    ["execute", f"--id={workflow_id}", "--rawOutput"],
                    log_dir / f"n8n_execute_{workflow_id}",
                    check=False,
                )
                report.executed_workflows.append(
                    {
                        "workflow_id": workflow_id,
                        "returncode": result.returncode,
                        "stdout_log": str(log_dir / f"n8n_execute_{workflow_id}.stdout.log"),
                        "stderr_log": str(log_dir / f"n8n_execute_{workflow_id}.stderr.log"),
                    }
                )
                if result.returncode != 0:
                    raise RuntimeError(f"n8n workflow {workflow_id} failed; see {log_dir / f'n8n_execute_{workflow_id}.stderr.log'}")
        finally:
            _stop_process(product_proc)

        observed_routes = _read_audit_routes(out / "product_api_audit" / "audit.jsonl")
        report.observed_routes = sorted(observed_routes)
        report.missing_routes = sorted(EXPECTED_ROUTES.difference(observed_routes))
        report.safety_checks["expected_product_api_routes_called"] = not report.missing_routes
        report.safety_checks["execution_allowed_false_in_audit"] = _audit_execution_allowed_false(out / "product_api_audit" / "audit.jsonl")
        report.safety_checks["no_raw_pii_in_audit"] = not _file_contains_email_like(out / "product_api_audit" / "audit.jsonl")
        if report.missing_routes:
            raise RuntimeError(f"missing expected product API routes from live n8n audit: {report.missing_routes}")
        if not all(report.safety_checks.values()):
            failed = [key for key, ok in report.safety_checks.items() if not ok]
            raise RuntimeError(f"failed safety checks: {failed}")
        report.status = "passed"
    except Exception as exc:  # noqa: BLE001 - report must preserve any runtime failure.
        report.errors.append(str(exc))
        report.status = "failed"
    finally:
        _write_report(out, report)

    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report.status == "passed" else 1


def _preflight(workflow_dir: Path) -> None:
    if not workflow_dir.exists():
        raise FileNotFoundError(f"workflow directory missing: {workflow_dir}")
    workflow_files = sorted(workflow_dir.glob("*.json"))
    if len(workflow_files) < 5:
        raise RuntimeError(f"expected at least 5 workflow templates, found {len(workflow_files)}")


def _assert_workflows_safe(workflow_dir: Path) -> None:
    for path in workflow_dir.glob("*.json"):
        text = path.read_text(encoding="utf-8")
        lowered = text.casefold()
        hits = [needle for needle in FORBIDDEN_WORKFLOW_SUBSTRINGS if needle in lowered]
        if hits:
            raise RuntimeError(f"unsafe literal(s) in {path}: {hits}")
        if _text_contains_email_like(text):
            raise RuntimeError(f"raw PII-like literal in {path}: email-like value")
        data = json.loads(text)
        node_types = {node.get("type") for node in data.get("nodes", []) if isinstance(node, dict)}
        sql_nodes = sorted(FORBIDDEN_SQL_NODES.intersection(node_types))
        if sql_nodes:
            raise RuntimeError(f"direct SQL node(s) in {path}: {sql_nodes}")
        meta = data.get("meta", {}).get("semanticDataContext", {})
        if meta.get("noSilentFallback") is not True or meta.get("noSqlRun") is not True:
            raise RuntimeError(f"workflow missing explicit safety meta: {path}")


def _require_docker() -> None:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker is required for live n8n runtime smoke; no Docker binary found")
    _run(["docker", "version", "--format", "{{.Server.Version}}"], Path("/tmp/n8n_docker_version"), check=True)


def _docker_version(image: str, log_dir: Path) -> None:
    _run(["docker", "run", "--rm", image, "--version"], log_dir / "n8n_version", check=True)


def _start_product_adapter(port: int, audit_root: Path, log_dir: Path) -> subprocess.Popen[str]:
    audit_root.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = ":".join(
        [
            str(REPO_ROOT / "packages" / "semantic_contracts"),
            str(REPO_ROOT / "packages" / "semantic_builder" / "src"),
            str(REPO_ROOT / "packages" / "semantic_registry"),
            str(REPO_ROOT / "packages" / "semantic_mcp" / "src"),
            "/tmp/semantic-data-context-deps",
        ]
    )
    python = str(REPO_ROOT / ".venv" / "bin" / "python") if (REPO_ROOT / ".venv" / "bin" / "python").exists() else sys.executable
    stdout = (log_dir / "product_adapter.stdout.log").open("w", encoding="utf-8")
    stderr = (log_dir / "product_adapter.stderr.log").open("w", encoding="utf-8")
    return subprocess.Popen(
        [
            python,
            "-m",
            "semantic_registry.product.http_adapter",
            "--serve",
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "--audit-root",
            str(audit_root),
        ],
        cwd=REPO_ROOT,
        env=env,
        stdout=stdout,
        stderr=stderr,
        text=True,
    )


def _run_n8n(
    image: str,
    n8n_user: Path,
    workflow_dir: Path,
    product_api_base_url: str,
    args: list[str],
    log_prefix: Path,
    *,
    check: bool,
) -> CommandResult:
    command = [
        "docker",
        "run",
        "--rm",
        "-e",
        "N8N_ENCRYPTION_KEY=semantic-data-context-local-live-smoke-key-32",
        "-e",
        "N8N_SECURE_COOKIE=false",
        "-e",
        "N8N_RUNNERS_ENABLED=true",
        "-e",
        "N8N_BLOCK_ENV_ACCESS_IN_NODE=false",
        "-e",
        f"SDC_PRODUCT_API_BASE_URL={product_api_base_url}",
        "-e",
        "SDC_DEMO_KEY=local-live-smoke-only",
        "-v",
        f"{n8n_user}:/home/node/.n8n",
        "-v",
        f"{workflow_dir.resolve()}:/workflows:ro",
        image,
        *args,
    ]
    return _run(command, log_prefix, check=check)


def _run(command: list[str], log_prefix: Path, *, check: bool) -> CommandResult:
    log_prefix.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    (log_prefix.with_suffix(".stdout.log")).write_text(proc.stdout, encoding="utf-8")
    (log_prefix.with_suffix(".stderr.log")).write_text(proc.stderr, encoding="utf-8")
    result = CommandResult(command, proc.returncode, proc.stdout, proc.stderr)
    (log_prefix.with_suffix(".json")).write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    if check and proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(command)}; stderr={proc.stderr[-1200:]}")
    return result


def _wait_for_http(url: str, *, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:  # noqa: S310 - local-only smoke URL.
                if 200 <= response.status < 300:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError, socket.timeout) as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"timed out waiting for {url}: {last_error}")


def _stop_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def _read_audit_routes(path: Path) -> set[str]:
    if not path.exists():
        raise FileNotFoundError(f"product adapter audit missing: {path}")
    routes: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        route = record.get("route")
        if isinstance(route, str):
            routes.add(route)
    return routes


def _audit_execution_allowed_false(path: Path) -> bool:
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("execution_allowed") is not False:
            return False
    return True


def _file_contains_email_like(path: Path) -> bool:
    if not path.exists():
        return False
    return _text_contains_email_like(path.read_text(encoding="utf-8"))


def _text_contains_email_like(text: str) -> bool:
    return bool(re.search(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.IGNORECASE))


def _write_report(out: Path, report: LiveSmokeReport) -> None:
    (out / "live_smoke_report.json").write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    lines = [
        "# n8n Live Runtime Smoke Report",
        "",
        f"Status: {report.status}",
        f"Generated at: {report.generated_at}",
        f"Runner: {report.runner}",
        f"Product API base URL from n8n: `{report.product_api_base_url}`",
        "",
        "## Workflows",
        *[f"- `{name}`" for name in report.workflows_imported],
        "",
        "## Observed product API routes",
        *[f"- `{route}`" for route in report.observed_routes],
        "",
        "## Missing routes",
        *(f"- `{route}`" for route in report.missing_routes),
        "",
        "## Safety checks",
        *[f"- {name}: {value}" for name, value in sorted(report.safety_checks.items())],
        "",
        "## Errors",
        *(f"- {error}" for error in report.errors),
        "",
        "## Executed workflow IDs",
        *[f"- `{entry['workflow_id']}` returncode={entry['returncode']}" for entry in report.executed_workflows],
    ]
    (out / "live_smoke_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _now_utc() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


if __name__ == "__main__":
    raise SystemExit(main())
