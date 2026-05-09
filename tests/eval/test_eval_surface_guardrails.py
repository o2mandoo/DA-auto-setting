from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class EvalSurfaceGuardrailTests(unittest.TestCase):
    def test_eval_source_tree_has_no_dashboard_saas_or_credential_path(self) -> None:
        source_roots = [
            ROOT / "packages" / "semantic_builder" / "src" / "semantic_builder" / "eval",
            ROOT / "packages" / "semantic_mcp" / "src" / "semantic_mcp",
        ]
        file_paths = [
            str(path.relative_to(ROOT)).casefold()
            for root in source_roots
            for path in root.rglob("*")
            if path.is_file()
        ]
        joined = "\n".join(file_paths)
        self.assertNotIn("dashboard", joined)
        self.assertNotIn("saas", joined)
        self.assertNotIn("credential", joined)


if __name__ == "__main__":
    unittest.main()
