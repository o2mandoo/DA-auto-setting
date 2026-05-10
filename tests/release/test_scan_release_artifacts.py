from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run_scan(release_dir: Path, workflow_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "scripts/release/scan_release_artifacts.py",
            "--release-dir",
            str(release_dir),
            "--workflow-dir",
            str(workflow_dir),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_release_scan_passes_for_current_release_packet() -> None:
    result = run_scan(Path("reports/release/release-test"), Path("n8n/workflows"))
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "passed"
    assert payload["finding_count"] == 0


def test_release_scan_fails_closed_on_secret_and_direct_sql_node(tmp_path: Path) -> None:
    release_dir = tmp_path / "release"
    workflow_dir = tmp_path / "workflows"
    release_dir.mkdir()
    workflow_dir.mkdir()
    (release_dir / "release_summary.md").write_text("token=supersecret\n", encoding="utf-8")
    (workflow_dir / "unsafe.json").write_text(
        '{"nodes":[{"type":"n8n-nodes-base.postgres"}],"meta":{"semanticDataContext":{"noSilentFallback":true}}}',
        encoding="utf-8",
    )

    result = run_scan(release_dir, workflow_dir)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    categories = {finding["category"] for finding in payload["findings"]}
    assert "release_artifact_sensitive_content" in categories
    assert "n8n_workflow_unsafe_content" in categories
