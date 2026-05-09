from __future__ import annotations

from pathlib import Path
import unittest


class Phase12ScopeTests(unittest.TestCase):
    def test_env_example_is_placeholder_only_and_env_is_ignored(self) -> None:
        gitignore = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn(".env", gitignore)
        self.assertIn(".env.*", gitignore)
        self.assertIn("!.env.example", gitignore)

        example = Path(".env.example").read_text(encoding="utf-8")
        self.assertNotIn("localhost", example)
        self.assertNotIn("SemanticCardsTest", example)

        for line in example.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, value = stripped.split("=", 1)
            self.assertTrue(
                value.startswith("<") and value.endswith(">"),
                f"{key} must use placeholder-only values, got {value!r}",
            )

    def test_no_production_execute_query_surface(self) -> None:
        token = "execute" + "_query"
        offenders: list[str] = []
        for path in self._iter_text_files():
            if path.parts[:1] == ("tests",) and path.name == "test_phase12_scope.py":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if f"def {token}" in text or f"{token}(" in text:
                offenders.append(str(path))
        self.assertEqual(offenders, [])

    def test_no_dashboard_ui_or_saas_files(self) -> None:
        forbidden_suffixes = {".tsx", ".jsx", ".vue"}
        offenders = [
            str(path)
            for root in (Path("packages"), Path("scripts"), Path("docs"))
            if root.exists()
            for path in root.rglob("*")
            if path.suffix.lower() in forbidden_suffixes or "dashboard" in path.name.casefold()
        ]
        self.assertEqual(offenders, [])

    def test_no_demo_summary_raw_pii_if_present(self) -> None:
        summary = Path("runtime/phase12_demo/demo_summary.json")
        if summary.exists():
            text = summary.read_text(encoding="utf-8")
            self.assertNotIn("ada@example.com", text)
            self.assertNotIn("grace@example.com", text)

    def test_test_commands_keep_repo_packages_before_temp_dependency_path(self) -> None:
        repo_package_prefixes = (
            "packages/semantic_contracts",
            "packages/semantic_builder",
            "packages/semantic_registry",
            "packages/semantic_mcp",
        )
        offenders: list[str] = []
        for path in (Path("README.md"), Path("docs"), Path("reports")):
            if not path.exists():
                continue
            candidates = [path] if path.is_file() else list(path.rglob("*"))
            for candidate in candidates:
                if not candidate.is_file():
                    continue
                if candidate.suffix.lower() not in {".md", ".txt"}:
                    continue
                text = candidate.read_text(encoding="utf-8", errors="ignore")
                for line in text.splitlines():
                    if "PYTHONPATH=" not in line or "/tmp/semantic-data-context-deps" not in line:
                        continue
                    temp_index = line.index("/tmp/semantic-data-context-deps")
                    for package_prefix in repo_package_prefixes:
                        package_index = line.find(package_prefix)
                        if package_index != -1 and package_index > temp_index:
                            offenders.append(f"{candidate}: {line.strip()}")
                            break
        self.assertEqual(
            offenders,
            [],
            "Repo package paths must appear before /tmp/semantic-data-context-deps in test commands",
        )

    @staticmethod
    def _iter_text_files():
        roots = [Path("packages"), Path("scripts"), Path("eval")]
        for root in roots:
            if not root.exists():
                continue
            for path in root.rglob("*"):
                if path.is_file() and path.suffix.lower() in {".py", ".md", ".toml", ".yaml", ".yml"}:
                    yield path


if __name__ == "__main__":
    unittest.main()
