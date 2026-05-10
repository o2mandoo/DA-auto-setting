from __future__ import annotations

from pathlib import Path
import re
import unittest


class EntrypointPackagingTests(unittest.TestCase):
    def test_package_entrypoints_are_declared(self) -> None:
        builder = Path("packages/semantic_builder/pyproject.toml").read_text(encoding="utf-8")
        registry = Path("packages/semantic_registry/pyproject.toml").read_text(encoding="utf-8")
        mcp = Path("packages/semantic_mcp/pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('semantic-builder = "semantic_builder.cli:main"', builder)
        self.assertIn('semantic-eval = "semantic_builder.eval.cli:main"', builder)
        self.assertIn('semantic-registry = "semantic_registry.cli:main"', registry)
        self.assertIn('semantic-mcp = "semantic_mcp.server:main"', mcp)

    def test_cli_modules_import_without_side_effects(self) -> None:
        from semantic_builder.cli import main as builder_main  # type: ignore[import-untyped]
        from semantic_builder.eval.cli import main as eval_main  # type: ignore[import-untyped]
        from semantic_registry.cli import main as registry_main  # type: ignore[import-untyped]
        from semantic_mcp.server import main as mcp_main  # type: ignore[import-untyped]

        self.assertTrue(callable(builder_main))
        self.assertTrue(callable(eval_main))
        self.assertTrue(callable(registry_main))
        self.assertTrue(callable(mcp_main))

    def test_clone_ready_setup_assets_exist(self) -> None:
        self.assertTrue(Path("scripts/setup/bootstrap.py").is_file())
        self.assertTrue(Path("docs/setup/DEVELOPMENT.md").is_file())
        self.assertTrue(Path(".env.example").is_file())

    def test_clone_ready_setup_commands_are_documented(self) -> None:
        docs = Path("docs/setup/DEVELOPMENT.md").read_text(encoding="utf-8")
        self.assertIn("python3 scripts/setup/bootstrap.py --check-only", docs)
        self.assertIn("python3 scripts/setup/bootstrap.py --copy-env", docs)
        self.assertIn("cp .env.example .env", docs)
        self.assertIn("make setup", docs)
        self.assertIn("make env-check", docs)
        self.assertIn("make test", docs)
        self.assertIn("make demo", docs)

        example = Path(".env.example").read_text(encoding="utf-8")
        self.assertIn("SEMANTIC_WEAVIATE_ENABLED=<0|1>", example)
        self.assertIn("SEMANTIC_WEAVIATE_URL=<SEMANTIC_WEAVIATE_URL>", example)
        self.assertIn("SEMANTIC_WEAVIATE_API_KEY=<SEMANTIC_WEAVIATE_API_KEY>", example)
        self.assertNotIn("localhost", example)
        self.assertNotIn("token", example.casefold())

    def test_makefile_exposes_full_local_test_command(self) -> None:
        makefile = Path("Makefile").read_text(encoding="utf-8")

        self.assertRegex(makefile, r"(?m)^\.PHONY:.*\btest\b")
        self.assertRegex(makefile, r"(?m)^test:\n\t\$\(PYTHON\) -m pytest -q tests$")
        self.assertIn("release-scan", makefile)
        self.assertIn("release-verify", makefile)
        self.assertIn("ci: env-check test lint release-verify", makefile)
        self.assertIn("scripts/release/scan_release_artifacts.py", makefile)

        setup_docs = Path("docs/setup/README.md").read_text(encoding="utf-8")
        dev_docs = Path("docs/setup/DEVELOPMENT.md").read_text(encoding="utf-8")
        self.assertIn("make test", setup_docs)
        self.assertIn("make test", dev_docs)

    def test_clean_clone_packaging_workflow_verifies_install_and_tests(self) -> None:
        workflow = Path(".github/workflows/packaging-clean-clone.yml").read_text(encoding="utf-8")
        install_block = re.search(
            r"name: Install editable local packages\n\s+run: \|\n(?P<body>(?:\s+python -m pip install -e .+\n)+)",
            workflow,
        )

        self.assertIsNotNone(install_block)
        install_body = install_block.group("body") if install_block else ""
        self.assertIn("python -m pip install -e packages/semantic_contracts", install_body)
        self.assertIn("python -m pip install -e packages/semantic_registry", install_body)
        self.assertIn("python -m pip install -e packages/semantic_mcp", install_body)
        self.assertIn("python -m pip install -e 'packages/semantic_builder[test]'", install_body)
        self.assertIn('python-version: "3.14"', workflow)
        self.assertIn("PYTHON: python", workflow)
        self.assertIn('SDC_LLM_ENABLED: "0"', workflow)
        self.assertIn('SEMANTIC_WEAVIATE_ENABLED: "0"', workflow)
        self.assertIn('SEMANTIC_POSTGRES_ENABLED: "0"', workflow)
        self.assertIn('SEMANTIC_MYSQL_ENABLED: "0"', workflow)
        self.assertIn('SEMANTIC_CONTEXT_FIXTURE_DB: "0"', workflow)
        self.assertIn("run: make env-check", workflow)
        self.assertIn("run: PYTHONDONTWRITEBYTECODE=1 make test", workflow)
        self.assertIn("run: make release-test", workflow)
        self.assertIn("run: make release-pack RELEASE_ID=ci-smoke RELEASE_OUT=reports/release", workflow)
        self.assertIn("run: make release-scan RELEASE_ID=ci-smoke RELEASE_OUT=reports/release", workflow)
        self.assertIn("uses: actions/upload-artifact@v4", workflow)
        self.assertIn("run: python scripts/setup/clone_ready_setup.py", workflow)


if __name__ == "__main__":
    unittest.main()
