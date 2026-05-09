"""Write optional Postgres live fixture evidence without backend fallback.

The default path is safe in environments without a local PostgreSQL server: it
writes an explicit ``pending`` status explaining which gate is missing. When a
local PostgreSQL fixture DSN and safety gate are provided, it delegates to
``postgres_fixture_loader`` and records the gated execution status.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from .fixture_modes import FixtureTablePlan, build_fixture_table_plan
from .postgres_fixture_loader import (
    POSTGRES_DSN_ENV,
    PostgresLiveLoadStatus,
    build_postgres_sql_plan,
    load_postgres_fixture,
    load_postgres_fixture_from_env,
)


DEFAULT_OUTPUT = Path("reports/reality/postgres_live_fixture_evidence.json")


@dataclass(frozen=True)
class PostgresLiveEvidence:
    backend: str
    fixture_only: bool
    fallback_used: bool
    fallback_backend: str | None
    dsn_configured: bool
    status: dict[str, Any]
    sql_plan: dict[str, Any]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_default_fixture_plan() -> FixtureTablePlan:
    """Return a small PostgreSQL fixture plan with source-provided comments."""

    return build_fixture_table_plan(
        dataset_id="postgres_scope_c",
        schema_name="semantic_fixture_postgres_scope_c",
        table_name="orders",
        columns=["status", "amount", "order_date"],
        mode="real_comments",
        real_comments={
            "table": "Fixture-only order table for PostgreSQL scope C validation",
            "columns": {
                "status": "Order lifecycle status",
                "amount": "Order amount represented as fixture text",
                "order_date": "Order date represented as fixture text",
            },
        },
    )


def collect_postgres_live_evidence(
    *,
    fixture_plan: FixtureTablePlan | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
    dsn: str | None = None,
    connection_factory=None,
) -> PostgresLiveEvidence:
    """Collect PostgreSQL fixture evidence, leaving unavailable live runs pending."""

    plan = fixture_plan or build_default_fixture_plan()
    fixture_rows = list(rows or _default_rows())
    source_env = os.environ if env is None else env
    sql_plan = build_postgres_sql_plan(plan, fixture_rows)
    if dsn is not None:
        status = load_postgres_fixture(
            dsn=dsn,
            fixture_plan=plan,
            rows=fixture_rows,
            env=source_env,
            connection_factory=connection_factory,
        )
    else:
        status = load_postgres_fixture_from_env(
            plan,
            fixture_rows,
            env=source_env,
            connection_factory=connection_factory,
        )
    return _evidence_from_status(
        status=status,
        sql_plan=sql_plan.to_dict(),
        dsn_configured=bool((dsn or source_env.get(POSTGRES_DSN_ENV) or "").strip()),
    )


def write_postgres_live_evidence(
    path: str | Path = DEFAULT_OUTPUT,
    *,
    evidence: PostgresLiveEvidence | None = None,
    **collect_kwargs: Any,
) -> Path:
    """Write evidence JSON and return the output path."""

    output = Path(path)
    payload = evidence or collect_postgres_live_evidence(**collect_kwargs)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument(
        "--dsn",
        default=None,
        help=(
            "Optional local PostgreSQL fixture DSN. If omitted, "
            f"{POSTGRES_DSN_ENV} is read from the environment."
        ),
    )
    args = parser.parse_args(argv)
    path = write_postgres_live_evidence(args.output, dsn=args.dsn)
    print(path)
    return 0


def _evidence_from_status(
    *,
    status: PostgresLiveLoadStatus,
    sql_plan: dict[str, Any],
    dsn_configured: bool,
) -> PostgresLiveEvidence:
    return PostgresLiveEvidence(
        backend="postgres",
        fixture_only=True,
        fallback_used=False,
        fallback_backend=None,
        dsn_configured=dsn_configured,
        status=status.to_dict(),
        sql_plan=sql_plan,
        generated_at=datetime.now(UTC).isoformat(),
    )


def _default_rows() -> list[dict[str, str]]:
    return [
        {"status": "PAID", "amount": "100.00", "order_date": "2026-01-01"},
        {"status": "REFUNDED", "amount": "20.00", "order_date": "2026-01-02"},
    ]


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
