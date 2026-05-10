from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def load_guard_module() -> object:
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "release" / "check_no_tracked_test_datasets.py"
    spec = importlib.util.spec_from_file_location("check_no_tracked_test_datasets", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_dataset_guard_rejects_local_only_dataset_inventory(monkeypatch) -> None:
    module = load_guard_module()
    monkeypatch.setattr(
        module,
        "tracked_files",
        lambda: [
            "README.md",
            "docs/reference/test_datasets/tableau_superstore/Sample - Superstore.xls",
            "eval/datasets/sinagong_tableau_2026.yaml",
        ],
    )

    assert module.main() == 1


def test_dataset_guard_allows_demo_fixtures(monkeypatch) -> None:
    module = load_guard_module()
    monkeypatch.setattr(
        module,
        "tracked_files",
        lambda: [
            "README.md",
            "examples/demo_data/users.csv",
            "eval/datasets/demo_company_revenue.yaml",
        ],
    )

    assert module.main() == 0
