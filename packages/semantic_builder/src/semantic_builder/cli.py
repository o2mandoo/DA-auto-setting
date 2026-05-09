"""CLI orchestration for the local file-only Semantic Builder MVP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import yaml

from semantic_builder.builder import (
    attach_inference_artifacts_to_draft_pack,
    build_semantic_pack_draft,
    load_jsonl_records,
    load_profile_jsonl,
    write_semantic_pack_yaml,
)
from semantic_builder.connectors import PostgresConnector, SafeScanConfig, load_file_datasets, scan_source
from semantic_builder.profiler import profile_dataset
from semantic_builder.scanner.postgres import scan_postgres_database
from semantic_builder.inference import generate_semantic_inference, load_profile_jsonl as load_inference_profile_jsonl, write_jsonl


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="semantic-builder")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan local CSV/JSON/XLSX files")
    scan_parser.add_argument("--source", required=True)
    scan_parser.add_argument("--out", required=True)

    profile_parser = subparsers.add_parser("profile", help="Profile scanned local files")
    profile_parser.add_argument("--scan", required=True)
    profile_parser.add_argument("--out", required=True)

    db_parser = subparsers.add_parser("db", help="Read-only database scan/profile commands")
    db_subparsers = db_parser.add_subparsers(dest="db_command", required=True)

    db_scan_parser = db_subparsers.add_parser("scan", help="Run a safe read-only DB scan")
    db_scan_parser.add_argument("--connector", required=True, choices=("postgres",))
    db_scan_parser.add_argument("--config", required=True)
    db_scan_parser.add_argument("--out", required=True)

    db_profile_parser = db_subparsers.add_parser("profile", help="Flatten a DB scan report into column profiles")
    db_profile_parser.add_argument("--scan", required=True)
    db_profile_parser.add_argument("--out", required=True)

    build_parser = subparsers.add_parser("build-pack", help="Build semantic_pack.draft.yaml from profiles")
    build_parser.add_argument("--profiles", required=True)
    build_parser.add_argument("--out", required=True)
    build_parser.add_argument("--pack-id", default="demo_company.revenue_draft")
    build_parser.add_argument("--title", default="Builder Draft Semantic Pack")
    build_parser.add_argument(
        "--semantic-hypotheses",
        help="Optional Phase 5 semantic_hypotheses.jsonl to attach as draft metadata proposals",
    )
    build_parser.add_argument(
        "--onboarding-questions",
        help="Optional Phase 5 onboarding_questions.jsonl to attach as open metadata proposals",
    )

    infer_parser = subparsers.add_parser("infer-semantics", help="Generate Phase 5 draft semantic hypotheses/questions")
    infer_parser.add_argument("--profiles", required=True)
    infer_parser.add_argument("--hypotheses-out", required=True)
    infer_parser.add_argument("--questions-out", required=True)
    infer_parser.add_argument("--provider", choices=("mock", "local"), default="mock")

    args = parser.parse_args(argv)
    if args.command == "scan":
        return _scan(Path(args.source), Path(args.out))
    if args.command == "profile":
        return _profile(Path(args.scan), Path(args.out))
    if args.command == "db":
        if args.db_command == "scan":
            return _db_scan(args.connector, Path(args.config), Path(args.out))
        if args.db_command == "profile":
            return _db_profile(Path(args.scan), Path(args.out))
    if args.command == "build-pack":
        return _build_pack(
            Path(args.profiles),
            Path(args.out),
            pack_id=args.pack_id,
            title=args.title,
            semantic_hypotheses=Path(args.semantic_hypotheses) if args.semantic_hypotheses else None,
            onboarding_questions=Path(args.onboarding_questions) if args.onboarding_questions else None,
        )
    if args.command == "infer-semantics":
        return _infer_semantics(
            Path(args.profiles),
            Path(args.hypotheses_out),
            Path(args.questions_out),
            provider_name=args.provider,
        )
    parser.error(f"Unknown command: {args.command}")
    return 2


def _scan(source: Path, out: Path) -> int:
    datasets = scan_source(source)
    _write_json({"datasets": [dataset.to_scan_record() for dataset in datasets]}, out)
    return 0


def _profile(scan_report: Path, out: Path) -> int:
    payload = json.loads(scan_report.read_text(encoding="utf-8"))
    records = payload.get("datasets", [])
    if not isinstance(records, list):
        raise ValueError("scan report must contain a datasets list")

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for record in records:
            dataset_path = Path(record["path"])
            # Re-read local files here so profile output is based on the actual
            # connector path rather than trusting a stale or hand-written scan.
            for dataset in _datasets_for_scan_record(record, dataset_path):
                handle.write(json.dumps(profile_dataset(dataset), ensure_ascii=False, sort_keys=True) + "\n")
    return 0


def _db_scan(connector_name: str, config_path: Path, out: Path) -> int:
    config_payload = _load_yaml_mapping(config_path)
    if connector_name != "postgres":
        raise ValueError(f"unsupported database connector: {connector_name}")
    connector_config = _mapping_from_payload(config_payload, "connector")
    scan_config_payload = _mapping_from_payload(config_payload, "scan")
    postgres = _build_postgres_connector(connector_config)
    try:
        report = scan_postgres_database(postgres, config=_load_scan_config(scan_config_payload))
    finally:
        postgres.close()
    _write_json(report, out)
    return 0


def _db_profile(scan_report: Path, out: Path) -> int:
    report = json.loads(scan_report.read_text(encoding="utf-8"))
    columns = _flatten_db_scan_report(report)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for column in columns:
            handle.write(json.dumps(column, ensure_ascii=False, sort_keys=True) + "\n")
    return 0


def _datasets_for_scan_record(record: dict[str, Any], dataset_path: Path):
    datasets = load_file_datasets(dataset_path)
    sheet_name = record.get("sheet_name")
    table_name = record.get("table_name")
    if sheet_name is None and table_name is None:
        return datasets
    selected = [
        dataset
        for dataset in datasets
        if (sheet_name is None or dataset.sheet_name == sheet_name)
        and (table_name is None or dataset.table_name == table_name)
    ]
    if not selected:
        # Explicit failure avoids silently profiling every sheet when a scan row
        # references stale sheet/table metadata.
        raise ValueError(f"No dataset in {dataset_path} matches scan record table={table_name!r} sheet={sheet_name!r}")
    return selected


def _build_pack(
    profiles: Path,
    out: Path,
    *,
    pack_id: str,
    title: str,
    semantic_hypotheses: Path | None = None,
    onboarding_questions: Path | None = None,
) -> int:
    pack = build_semantic_pack_draft(load_profile_jsonl(profiles), pack_id=pack_id, title=title)
    if semantic_hypotheses or onboarding_questions:
        # Phase 5 artifacts stay as draft metadata proposals; this CLI path does
        # not promote generated business meaning into confirmed pack cards.
        pack = attach_inference_artifacts_to_draft_pack(
            pack,
            semantic_hypotheses=load_jsonl_records(semantic_hypotheses, record_name="Semantic hypothesis")
            if semantic_hypotheses
            else None,
            onboarding_questions=load_jsonl_records(onboarding_questions, record_name="Onboarding question")
            if onboarding_questions
            else None,
        )
    write_semantic_pack_yaml(pack, out)
    return 0


def _infer_semantics(profiles: Path, hypotheses_out: Path, questions_out: Path, *, provider_name: str) -> int:
    if provider_name != "mock":
        # Local provider support is an explicit seam only in Phase 5. Failing
        # loudly avoids hidden network calls or a silent mock fallback.
        raise ValueError("only the deterministic mock semantic inference provider is implemented by default")
    result = generate_semantic_inference(load_inference_profile_jsonl(profiles))
    write_jsonl(result["hypotheses"], hypotheses_out)
    write_jsonl(result["onboarding_questions"], questions_out)
    return 0


def _write_json(payload: dict[str, Any], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("scan config must be a mapping")
    return payload


def _mapping_from_payload(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    if value is None:
        return payload
    if not isinstance(value, dict):
        raise ValueError(f"{key} section must be a mapping")
    return value


def _build_postgres_connector(config: dict[str, Any]) -> PostgresConnector:
    connection_string = str(config.get("connection_string") or config.get("dsn") or "").strip()
    if not connection_string:
        raise ValueError("Postgres scan config requires a connection_string or dsn")
    return PostgresConnector(dsn=connection_string)


def _load_scan_config(config: dict[str, Any]) -> SafeScanConfig:
    return SafeScanConfig(
        schemas=tuple(config.get("schemas") or ()),
        tables=tuple(config.get("tables") or ()),
        max_tables=int(config.get("max_tables", 25)),
        max_columns=int(config.get("max_columns", 100)),
        max_sample_rows=int(config.get("max_sample_rows", 10)),
        timeout_ms=int(config.get("timeout_ms", 5000)),
        low_cardinality_threshold=int(config.get("low_cardinality_threshold", 20)),
        pii_policy=str(config.get("pii_policy", "block_raw_values")),
    )


def _flatten_db_scan_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in report.get("tables", []):
        table_name = table.get("table_name")
        schema_name = table.get("schema_name")
        for column in table.get("columns", []):
            row = dict(column)
            row.setdefault("schema_name", schema_name)
            row.setdefault("table_name", table_name)
            row.setdefault("qualified_name", table.get("qualified_name"))
            rows.append(row)
    return rows


if __name__ == "__main__":
    raise SystemExit(main())
