from __future__ import annotations

import json
from pathlib import Path

from scripts.release.release_pack import build_release_packet, scan_sensitive_material


def test_build_release_packet_writes_machine_readable_manifest(tmp_path: Path) -> None:
    out_dir = tmp_path / "release" / "release-test"
    manifest = build_release_packet(release_id="release-test", out_root=out_dir)

    manifest_path = out_dir / "release_manifest.json"
    summary_path = out_dir / "release_summary.md"
    limits_path = out_dir / "known_limitations.md"
    support_path = out_dir / "support_matrix.md"

    assert manifest_path.exists()
    assert summary_path.exists()
    assert limits_path.exists()
    assert support_path.exists()

    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert loaded["schema_version"] == "1.0"
    assert loaded["release_id"] == "release-test"
    assert loaded["release_status"] == "draft"
    assert str(loaded["artifact_paths"]["manifest"]).endswith("release_manifest.json")
    assert str(loaded["artifact_paths"]["summary"]).endswith("release_summary.md")
    assert loaded["missing_evidence"]
    assert any(item["gate"].startswith("PR-1") for item in loaded["missing_evidence"])
    assert "support_matrix" in loaded and len(loaded["support_matrix"]) >= 5
    assert loaded["safety_proof"]["no_production_execute_query"]["status"] == "explicitly_prohibited"
    assert loaded["safety_proof"]["no_silent_fallback"]["status"] == "explicitly_prohibited"
    assert loaded["dependency_snapshot"]["status"] in {"available", "missing"}

    assert "Known limitations" in limits_path.read_text(encoding="utf-8")
    assert "Support matrix" in support_path.read_text(encoding="utf-8")
    assert manifest["release_id"] == "release-test"


def test_sensitive_material_scanner_flags_common_secret_shapes() -> None:
    findings = scan_sensitive_material(
        [
            "postgres://user:secret@db.example.com/app",
            "sk-test-abc123def456ghi789",
            "ada.lovelace@example.com",
        ]
    )
    assert any("postgres://" in item for item in findings)
    assert any(item.startswith("sk-") for item in findings)
    assert any("@" in item for item in findings)
