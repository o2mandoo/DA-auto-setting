"""Console entrypoint for the local evaluation harness."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from .runner import (
    load_benchmark_manifest,
    render_benchmark_json,
    render_benchmark_markdown,
    run_benchmark_manifest,
    write_benchmark_report,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="semantic-eval")
    parser.add_argument("--manifest")
    parser.add_argument("--manifest-dir")
    parser.add_argument("--out")
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    args = parser.parse_args(argv)

    if args.manifest_dir:
        return _run_manifest_corpus(Path(args.manifest_dir), Path(args.out) if args.out else None, args.format)
    if not args.manifest:
        # No silent demo fallback: callers must opt into a single manifest or a corpus run explicitly.
        parser.error("either --manifest or --manifest-dir is required")

    manifest = load_benchmark_manifest(Path(args.manifest))
    out_dir = Path(args.out) if args.out else Path("runtime") / "benchmarks" / _slug(manifest.dataset_id)
    run = run_benchmark_manifest(manifest, out_dir=out_dir)
    write_benchmark_report(
        run,
        args.json_out or str(out_dir / "benchmark.json"),
        args.markdown_out or str(out_dir / "benchmark.md"),
    )
    output = render_benchmark_markdown(run) if args.format == "markdown" else render_benchmark_json(run)
    print(output)
    return 0 if run.summary["failed"] == 0 else 1


def _run_manifest_corpus(manifest_dir: Path, out_dir: Path | None, output_format: str) -> int:
    manifest_paths = sorted(
        path for path in manifest_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".yaml", ".yml"}
    )
    if not manifest_paths:
        raise ValueError(f"no benchmark manifests found under {manifest_dir}")

    runs = []
    for manifest_path in manifest_paths:
        manifest = load_benchmark_manifest(manifest_path)
        dataset_out = (out_dir / _slug(manifest.dataset_id)) if out_dir else None
        runs.append(run_benchmark_manifest(manifest, out_dir=dataset_out))

    summary = {
        "passed": sum(run.summary["passed"] for run in runs),
        "failed": sum(run.summary["failed"] for run in runs),
        "skipped": sum(run.summary["skipped"] for run in runs),
        "total": sum(run.summary["total"] for run in runs),
    }
    corpus_payload = {
        "manifest_dir": str(manifest_dir),
        "summary": summary,
        "runs": [run.as_dict() for run in runs],
    }
    if output_format == "markdown":
        print(_render_corpus_markdown(corpus_payload))
    else:
        print(_render_corpus_json(corpus_payload))
    return 0 if summary["failed"] == 0 else 1


def _render_corpus_json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def _render_corpus_markdown(payload: dict[str, object]) -> str:
    runs = payload["runs"]
    summary = payload["summary"]
    rows = [
        "# Phase 11 Benchmark Corpus",
        "",
        f"- Manifest dir: `{payload['manifest_dir']}`",
        f"- Summary: {summary['passed']} passed / {summary['failed']} failed / {summary['skipped']} skipped",
        "",
        "| Dataset | Passed | Failed | Skipped | Total |",
        "| --- | --- | --- | --- | --- |",
    ]
    for run in runs:
        manifest = run["manifest"]
        run_summary = run["summary"]
        rows.append(
            f"| {manifest['dataset_id']} | {run_summary['passed']} | {run_summary['failed']} | {run_summary['skipped']} | {run_summary['total']} |"
        )
    rows.append("")
    return "\n".join(rows)


def _slug(value: str) -> str:
    slug = []
    for char in value:
        slug.append(char.lower() if char.isalnum() else "_")
    result = "".join(slug).strip("_")
    while "__" in result:
        result = result.replace("__", "_")
    return result or "benchmark"


if __name__ == "__main__":  # pragma: no cover - console path
    raise SystemExit(main())
