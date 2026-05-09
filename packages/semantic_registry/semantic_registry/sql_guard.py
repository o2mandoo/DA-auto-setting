"""Deterministic, validation-only SQL guard for Semantic Packs.

This module deliberately validates metadata and policy references only. It never
opens a database connection, never executes SQL, and never calls an external LLM;
those safety boundaries are Phase 3 product policy, not implementation details.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Iterable

from semantic_contracts import SemanticPack, SqlCheckName, SqlCheckStatus, SqlGuardResult

from .store import DEFAULT_PACK_ROOT, PackStore

_DANGEROUS_STATEMENTS = {
    "alter",
    "create",
    "delete",
    "drop",
    "insert",
    "merge",
    "replace",
    "truncate",
    "update",
}
_SQL_KEYWORDS = {
    "and",
    "as",
    "asc",
    "by",
    "case",
    "cast",
    "desc",
    "distinct",
    "else",
    "end",
    "false",
    "from",
    "group",
    "having",
    "in",
    "is",
    "join",
    "left",
    "limit",
    "not",
    "null",
    "on",
    "or",
    "order",
    "over",
    "partition",
    "right",
    "select",
    "then",
    "true",
    "when",
    "where",
    "with",
}


@dataclass(frozen=True)
class SqlPolicyLimits:
    """Policy-derived validation envelope for one role/pack selection."""

    allowed_tables: set[str]
    blocked_columns: set[str]
    matched_policy_ids: list[str]


class SQLGuard:
    """Validate SQL text against Semantic Pack policy without execution.

    The MVP parser is intentionally conservative: when it cannot prove a table
    or blocked-column reference is safe (for example ``SELECT *`` on a table
    with blocked columns), it fails validation instead of permitting execution.
    """

    def __init__(self, packs: Iterable[SemanticPack]) -> None:
        self.packs = list(packs)

    @classmethod
    def from_pack(cls, pack: SemanticPack) -> "SQLGuard":
        return cls([pack])

    @classmethod
    def from_pack_root(cls, space_id: str, pack_root: str | Path = DEFAULT_PACK_ROOT) -> "SQLGuard":
        return cls(_load_space_packs(space_id, pack_root))

    def validate(self, sql: str, role: str | None = None) -> SqlGuardResult:
        """Return a contract-shaped validation result; no SQL is executed."""

        normalized_sql = sql.strip()
        sql_without_literals = _strip_string_literals(normalized_sql)
        statements = _split_sql_statements(sql_without_literals)
        checks: dict[SqlCheckName, SqlCheckStatus] = {}
        warnings: list[str] = []
        errors: list[str] = []

        select_only = bool(statements) and all(_is_select_like(statement) for statement in statements)
        dangerous_hits = _dangerous_statement_hits(sql_without_literals)
        if not select_only or dangerous_hits:
            checks[SqlCheckName.SELECT_ONLY] = SqlCheckStatus.FAIL
            if dangerous_hits:
                errors.append(f"Non-SELECT SQL keywords are blocked: {', '.join(dangerous_hits)}")
            else:
                errors.append("Only SELECT/WITH statements may be validated; SQL execution is out of scope.")
        else:
            checks[SqlCheckName.SELECT_ONLY] = SqlCheckStatus.PASS

        multi_statement = len(statements) > 1
        checks[SqlCheckName.MULTI_STATEMENT] = SqlCheckStatus.FAIL if multi_statement else SqlCheckStatus.PASS
        if multi_statement:
            errors.append("Multiple SQL statements are not allowed.")

        referenced_tables = _extract_referenced_tables(sql_without_literals)
        alias_to_table = _extract_table_aliases(sql_without_literals)
        referenced_columns = _extract_referenced_columns(sql_without_literals, alias_to_table)
        policy_limits = self._policy_limits_for_role(role)

        if not policy_limits.matched_policy_ids:
            checks[SqlCheckName.ALLOWED_TABLES] = SqlCheckStatus.FAIL
            role_label = role if role is not None else "<unspecified>"
            errors.append(f"No Semantic Pack table policy matched role: {role_label}")
        else:
            unknown_tables = [table for table in referenced_tables if table not in policy_limits.allowed_tables]
            checks[SqlCheckName.ALLOWED_TABLES] = SqlCheckStatus.FAIL if unknown_tables else SqlCheckStatus.PASS
            if unknown_tables:
                errors.append(f"Referenced tables are outside role policy: {', '.join(unknown_tables)}")

        blocked_hits = self._blocked_column_hits(
            sql_without_literals=sql_without_literals,
            referenced_tables=referenced_tables,
            referenced_columns=referenced_columns,
            blocked_columns=policy_limits.blocked_columns,
        )
        checks[SqlCheckName.BLOCKED_COLUMNS] = SqlCheckStatus.FAIL if blocked_hits else SqlCheckStatus.PASS
        if blocked_hits:
            errors.append(f"Blocked columns referenced: {', '.join(blocked_hits)}")

        if "*" in _select_list(sql_without_literals) and not blocked_hits:
            warnings.append("SELECT * is permitted only when no referenced table has blocked columns.")

        return SqlGuardResult(
            valid=not any(status == SqlCheckStatus.FAIL for status in checks.values()),
            execution_allowed=False,
            checks=checks,
            referenced_tables=referenced_tables,
            referenced_columns=referenced_columns,
            warnings=warnings,
            errors=errors,
        )

    def _policy_limits_for_role(self, role: str | None) -> SqlPolicyLimits:
        allowed_tables: set[str] = set()
        blocked_columns: set[str] = set()
        matched_policy_ids: list[str] = []
        for pack in self.packs:
            for policy in pack.policies:
                # Unspecified roles use all local policies for direct validation
                # tests; explicit roles must match to avoid silently widening access.
                if role is not None and role not in policy.applies_to.roles:
                    continue
                matched_policy_ids.append(policy.id)
                allowed_tables.update(_normalize_identifier(table) for table in policy.allowed_tables)
                blocked_columns.update(_normalize_qualified_column(column) for column in policy.blocked_columns)
        return SqlPolicyLimits(allowed_tables=allowed_tables, blocked_columns=blocked_columns, matched_policy_ids=matched_policy_ids)

    def _blocked_column_hits(
        self,
        *,
        sql_without_literals: str,
        referenced_tables: list[str],
        referenced_columns: list[str],
        blocked_columns: set[str],
    ) -> list[str]:
        hits: set[str] = set()
        normalized_sql = sql_without_literals.casefold()
        normalized_columns = {_normalize_qualified_column(column) for column in referenced_columns}
        referenced_table_set = set(referenced_tables)
        select_list = _select_list(sql_without_literals)

        for blocked_column in blocked_columns:
            table, _, column = blocked_column.partition(".")
            # Alias expansion above makes table aliases explicit in
            # referenced_columns; matching any alias with the same column name
            # would over-block safe columns from other allowed tables.
            qualified_patterns = [rf"\b{re.escape(table)}\s*\.\s*{re.escape(column)}\b"]
            if blocked_column in normalized_columns or any(re.search(pattern, normalized_sql) for pattern in qualified_patterns):
                hits.add(blocked_column)
                continue
            # MVP policy: unqualified blocked names are denied because the guard
            # should never infer that a PII-looking projection is safe.
            if re.search(rf"\b{re.escape(column)}\b", select_list.casefold()):
                hits.add(blocked_column)
                continue
            if "*" in select_list and table in referenced_table_set:
                hits.add(blocked_column)
        return sorted(hits)


def validate_sql(
    sql: str,
    *,
    space_id: str = "demo_company.revenue",
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
) -> SqlGuardResult:
    """Convenience API for validating local-pack SQL without execution."""

    return SQLGuard.from_pack_root(space_id=space_id, pack_root=pack_root).validate(sql, role=role)


def validate_sql_dict(
    sql: str,
    *,
    space_id: str = "demo_company.revenue",
    role: str | None = None,
    pack_root: str | Path = DEFAULT_PACK_ROOT,
) -> dict[str, object]:
    """JSON-compatible helper for MCP/tool layers that cannot return models."""

    return validate_sql(sql, space_id=space_id, role=role, pack_root=pack_root).model_dump(mode="json")


def _load_space_packs(space_id: str, pack_root: str | Path) -> list[SemanticPack]:
    store = PackStore(pack_root)
    selected = [pack for pack in store.load_packs() if pack.id == space_id or any(space.id == space_id for space in pack.spaces)]
    if not selected:
        raise KeyError(f"Unknown semantic space: {space_id}")
    return selected


def _strip_string_literals(sql: str) -> str:
    return re.sub(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"", "''", sql)


def _split_sql_statements(sql: str) -> list[str]:
    # Literal stripping above keeps semicolons inside simple quoted values from
    # looking like statement separators while preserving conservative behavior.
    return [part.strip() for part in sql.split(";") if part.strip()]


def _is_select_like(statement: str) -> bool:
    return bool(re.match(r"(?is)^\s*(select|with)\b", statement))


def _dangerous_statement_hits(sql: str) -> list[str]:
    lowered = sql.casefold()
    return sorted(keyword for keyword in _DANGEROUS_STATEMENTS if re.search(rf"\b{keyword}\b", lowered))


def _extract_referenced_tables(sql: str) -> list[str]:
    tables = []
    for match in re.finditer(r"(?is)\b(?:from|join)\s+([a-zA-Z_][\w.]*)", sql):
        table = match.group(1).split(".")[-1]
        # CTE/subquery extraction is intentionally simple for the MVP; unknown
        # aliases are later rejected by allowed-table policy instead of executed.
        tables.append(_normalize_identifier(table))
    return _unique(tables)


def _extract_table_aliases(sql: str) -> dict[str, str]:
    aliases: dict[str, str] = {}
    pattern = re.compile(r"(?is)\b(?:from|join)\s+([a-zA-Z_][\w.]*)(?:\s+(?:as\s+)?([a-zA-Z_]\w*))?")
    for match in pattern.finditer(sql):
        table = _normalize_identifier(match.group(1).split(".")[-1])
        alias = match.group(2)
        if alias and alias.casefold() not in _SQL_KEYWORDS:
            aliases[_normalize_identifier(alias)] = table
        aliases[table] = table
    return aliases


def _extract_referenced_columns(sql: str, alias_to_table: dict[str, str]) -> list[str]:
    columns: list[str] = []
    for table_or_alias, column in re.findall(r"\b([a-zA-Z_]\w*)\s*\.\s*([a-zA-Z_]\w*)\b", sql):
        table = alias_to_table.get(_normalize_identifier(table_or_alias), _normalize_identifier(table_or_alias))
        columns.append(f"{table}.{_normalize_identifier(column)}")
    for column in _unqualified_select_columns(sql):
        columns.append(column)
    return _unique(columns)


def _unqualified_select_columns(sql: str) -> list[str]:
    select_list = _select_list(sql)
    columns: list[str] = []
    for token in re.findall(r"\b[a-zA-Z_]\w*\b", select_list):
        lowered = token.casefold()
        if lowered in _SQL_KEYWORDS:
            continue
        if re.search(rf"\b{re.escape(token)}\s*\(", select_list):
            continue
        columns.append(lowered)
    return _unique(columns)


def _select_list(sql: str) -> str:
    match = re.search(r"(?is)\bselect\b(?P<select>.*?)\bfrom\b", sql)
    return match.group("select") if match else ""


def _normalize_identifier(value: str) -> str:
    return value.strip().strip('"`[]').casefold()


def _normalize_qualified_column(value: str) -> str:
    parts = [_normalize_identifier(part) for part in value.split(".")]
    return ".".join(part for part in parts if part)


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


__all__ = ["SQLGuard", "SqlPolicyLimits", "validate_sql", "validate_sql_dict"]
