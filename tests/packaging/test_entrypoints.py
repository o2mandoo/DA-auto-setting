from __future__ import annotations

from pathlib import Path
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
        from semantic_builder.cli import main as builder_main
        from semantic_builder.eval.cli import main as eval_main
        from semantic_registry.cli import main as registry_main
        from semantic_mcp.server import main as mcp_main

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


if __name__ == "__main__":
    unittest.main()
