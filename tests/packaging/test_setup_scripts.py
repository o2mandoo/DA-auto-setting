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

    def test_clone_ready_setup_prints_repo_paths_before_temp_bundle(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(SETUP_DIR / "clone_ready_setup.py")],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        stdout = completed.stdout
        self.assertIn("clone-ready setup checks: PASS", stdout)
        self.assertIn("cp .env.example .env", stdout)
        self.assertIn("python3 scripts/demo/run_local_demo.py", stdout)
        self.assertIn("packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps", stdout)
        self.assertLess(
            stdout.index("packages/semantic_contracts:packages/semantic_builder/src:packages/semantic_registry:packages/semantic_mcp/src:/tmp/semantic-data-context-deps"),
            stdout.index("python3 scripts/demo/run_local_demo.py"),
        )

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
