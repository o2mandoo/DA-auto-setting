from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "semantic_contracts"))
sys.path.insert(0, str(ROOT / "packages" / "semantic_registry"))

from semantic_registry import PackStore  # noqa: E402
from semantic_contracts import SemanticPack  # noqa: E402


def _field(value: Any, name: str) -> Any:
    if isinstance(value, dict):
        return value[name]
    return getattr(value, name)


class PackStoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.pack_root = ROOT / "semantic_packs"
        self.store = PackStore(self.pack_root)

    def test_load_pack_validates_demo_pack_from_local_files(self) -> None:
        pack = self.store.load_pack("demo_company.revenue")

        self.assertIsInstance(pack, SemanticPack)
        self.assertEqual(pack.id, "demo_company.revenue")
        self.assertEqual(pack.version, "0.1.0")
        self.assertEqual({table.id for table in pack.tables}, {"table.users", "table.payments", "table.campaigns"})

    def test_list_packs_returns_demo_pack_metadata(self) -> None:
        packs = self.store.list_packs()
        demo = next(item for item in packs if _field(item, "pack_id") == "demo_company.revenue")

        self.assertEqual(_field(demo, "version"), "0.1.0")
        self.assertEqual(_field(demo, "title"), "Demo Company Revenue Context")
        self.assertEqual(_field(demo, "path"), self.pack_root / "demo_company" / "revenue.v0_1.yaml")

    def test_list_spaces_returns_semantic_space_summaries(self) -> None:
        spaces = self.store.list_spaces()
        demo = next(item for item in spaces if _field(item, "space_id") == "demo_company.revenue")

        self.assertEqual(_field(demo, "title"), "Demo Company Revenue Context")
        self.assertEqual(_field(demo, "version"), "0.1.0")
        self.assertEqual(_field(demo, "status"), "approved")
        self.assertEqual(_field(demo, "spaces"), ["revenue"])

    def test_load_pack_rejects_unknown_pack_id(self) -> None:
        with self.assertRaises(KeyError):
            self.store.load_pack("missing.pack")

    def test_load_pack_rejects_invalid_pack_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            broken_dir = tmp_root / "broken"
            broken_dir.mkdir()
            shutil.copyfile(self.pack_root / "demo_company" / "revenue.v0_1.yaml", broken_dir / "valid.yaml")
            (broken_dir / "broken.yaml").write_text('{"semantic_pack": {"id": "broken.pack"}}', encoding="utf-8")

            store = PackStore(tmp_root)
            with self.assertRaises(ValueError):
                store.load_pack("broken.pack")


if __name__ == "__main__":
    unittest.main()
