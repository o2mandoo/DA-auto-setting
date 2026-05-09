from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path


def load_release_module() -> object:
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "release" / "build_release_packet.py"
    spec = importlib.util.spec_from_file_location("build_release_packet", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_redact_text_masks_secrets_and_pii() -> None:
    module = load_release_module()
    redact_text = getattr(module, "redact_text")

    redacted, summary = redact_text(
        "email=alice@example.com "
        "dsn=postgresql://user:password@localhost:5432/db "
        "key=sk-abcdefghijklmnopqrstuvwxyz123456 "
        "aws_secret_access_key=ABC123TOKEN "
        "Authorization: Bearer abc.def.ghi"
    )

    assert "<redacted_email>" in redacted
    assert "<redacted_credentials>" in redacted
    assert "<redacted_openai_key>" in redacted
    assert "<redacted_secret>" in redacted
    assert "Bearer <redacted_token>" in redacted
    assert summary.had_findings is True
    assert summary.counts["email"] == 1


def test_build_packet_writes_release_artifacts(tmp_path: Path) -> None:
    module = load_release_module()
    build_packet = getattr(module, "build_packet")

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = tmp_path / "release-packet"
    manifest = build_packet(repo_root, "unit-test-release", out_dir)

    expected_files = {
        "release_manifest.json",
        "release_summary.md",
        "risk_register.md",
        "known_limitations.md",
        "support_matrix.md",
    }
    assert expected_files == {path.name for path in out_dir.iterdir()}
    assert manifest["release_id"] == "unit-test-release"
    assert manifest["status"] == "dry-run"
    assert "sensitive_content_redacted" in manifest["safety_checks"]
    assert manifest["safety_checks"]["secrets_redacted"] == manifest["safety_checks"]["sensitive_content_redacted"]
    assert manifest["safety_checks"]["no_production_execute_query_claim"] is True
    assert manifest["safety_checks"]["no_silent_fallback_claim"] is True
    assert manifest["safety_checks"]["no_raw_pii_claim"] is True

    summary = (out_dir / "release_summary.md").read_text(encoding="utf-8")
    risk_register = (out_dir / "risk_register.md").read_text(encoding="utf-8")
    known_limitations = (out_dir / "known_limitations.md").read_text(encoding="utf-8")
    support_matrix = (out_dir / "support_matrix.md").read_text(encoding="utf-8")

    assert "Risk register" in risk_register or "Risk Register" in risk_register
    assert "Known limitations" in known_limitations or "known limitations" in known_limitations
    assert "Support matrix" in support_matrix or "support matrix" in support_matrix
    assert "dry-run release packet" in summary

    manifest_path = out_dir / "release_manifest.json"
    loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert loaded["release_id"] == "unit-test-release"
    assert loaded["artifacts"]["risk_register"] == "risk_register.md"
    assert loaded["artifacts"]["known_limitations"] == "known_limitations.md"
    assert loaded["artifacts"]["support_matrix"] == "support_matrix.md"


def test_generated_packet_contains_no_obvious_secret_markers(tmp_path: Path) -> None:
    module = load_release_module()
    build_packet = getattr(module, "build_packet")

    repo_root = Path(__file__).resolve().parents[2]
    out_dir = tmp_path / "release-packet"
    build_packet(repo_root, "unit-test-release", out_dir)

    combined = "\n".join(path.read_text(encoding="utf-8") for path in out_dir.iterdir() if path.is_file())
    assert not re.search(r"\bsk-[A-Za-z0-9]{20,}\b", combined)
    assert not re.search(r"\bAKIA[0-9A-Z]{16}\b", combined)
    assert "password@" not in combined
    assert not re.search(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b", combined)
    assert "client_secret" not in combined
    assert "/Users/" not in combined
    assert not re.search(r"\bworker-\d+\b", combined)
    assert "leader-fixed" not in combined
