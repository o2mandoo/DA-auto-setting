from __future__ import annotations

import json

from experiments.db_fixtures.scripts.mysql_live_evidence import (
    collect_mysql_live_evidence,
    write_mysql_live_evidence,
)


class _FakeCursor:
    def __init__(self) -> None:
        self.statements: list[str] = []

    def execute(self, statement: str) -> None:
        self.statements.append(statement)

    def close(self) -> None:
        return None


class _FakeConnection:
    def __init__(self) -> None:
        self.cursor_obj = _FakeCursor()
        self.committed = False
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return self.cursor_obj

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        self.closed = True


def test_mysql_live_evidence_defaults_to_pending_without_fallback(tmp_path) -> None:
    output = tmp_path / "mysql_live_fixture_evidence.json"

    path = write_mysql_live_evidence(output, env={})
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["backend"] == "mysql"
    assert payload["fixture_only"] is True
    assert payload["fallback_used"] is False
    assert payload["fallback_backend"] is None
    assert payload["dsn_configured"] is False
    assert payload["status"]["status"] == "pending"
    assert payload["status"]["attempted"] is False
    assert any("no fallback backend" in reason for reason in payload["status"]["reasons"])
    assert payload["sql_plan"]["backend"] == "mysql"


def test_mysql_live_evidence_records_loaded_status_when_gate_passes() -> None:
    connection = _FakeConnection()

    evidence = collect_mysql_live_evidence(
        dsn="mysql://localhost/semantic_fixture_mysql_scope_c",
        env={"SEMANTIC_CONTEXT_FIXTURE_DB": "1"},
        connection_factory=lambda _dsn: connection,
    )

    assert evidence.backend == "mysql"
    assert evidence.fallback_used is False
    assert evidence.dsn_configured is True
    assert evidence.status["status"] == "loaded"
    assert evidence.status["attempted"] is True
    assert evidence.status["executed_statement_count"] == len(connection.cursor_obj.statements)
    assert connection.committed is True
    assert connection.closed is True

