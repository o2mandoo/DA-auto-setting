from __future__ import annotations

import subprocess
import sys
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SETUP_DIR = ROOT / "scripts" / "setup"


class SetupScriptsPackagingTests(unittest.TestCase):
    def test_setup_helpers_are_present(self) -> None:
        expected = {
            "README.md",
            "clean_runtime.sh",
            "clone_ready_setup.py",
            "env_check.sh",
        }
        self.assertTrue(SETUP_DIR.exists(), SETUP_DIR)
        self.assertTrue(expected.issubset({path.name for path in SETUP_DIR.iterdir()}))

    def test_clone_ready_setup_prints_repo_paths_without_temp_bundle(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SETUP_DIR / "clone_ready_setup.py")],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        stdout = completed.stdout
        self.assertIn("clone-ready setup checks: PASS", stdout)
        self.assertIn(
            "python3 -m pip install -e packages/semantic_contracts -e packages/semantic_registry -e packages/semantic_mcp -e packages/semantic_builder",
            stdout,
        )
        self.assertIn("cp .env.example .env", stdout)
        self.assertIn("python3 scripts/demo/run_local_demo.py", stdout)
        self.assertNotIn("/tmp/semantic-data-context-deps", stdout)

    def test_setup_docs_and_helper_do_not_depend_on_hidden_temp_bundle(self) -> None:
        contents = [
            Path("docs/setup/README.md").read_text(encoding="utf-8"),
            Path("docs/setup/DEVELOPMENT.md").read_text(encoding="utf-8"),
            Path("docs/setup/CLONE_READY_USAGE_SUMMARY.md").read_text(encoding="utf-8"),
            Path("scripts/setup/clone_ready_setup.py").read_text(encoding="utf-8"),
        ]
        for content in contents:
            self.assertNotIn("/tmp/semantic-data-context-deps", content)

    def test_env_check_script_passes(self) -> None:
        subprocess.run(
            ["bash", str(SETUP_DIR / "env_check.sh")],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )


if __name__ == "__main__":
    unittest.main()
