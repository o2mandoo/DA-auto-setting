from __future__ import annotations

import json
import subprocess
import sys
import unittest


class LocalDemoE2ETest(unittest.TestCase):
    def test_local_demo_script_runs_end_to_end(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/demo/run_local_demo.py"],
            check=True,
            text=True,
            capture_output=True,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(payload["counts"]["scan_datasets"], 3)
        self.assertGreaterEqual(payload["counts"]["questions"], 1)
        self.assertEqual(payload["lifecycle"]["confirmation_status"], "approved")
        self.assertFalse(payload["mcp_like"]["blocked_sql_valid"])
        self.assertFalse(payload["mcp_like"]["blocked_sql_execution_allowed"])
        self.assertFalse(payload["mcp_like"]["preview_execution_allowed"])
        self.assertEqual(payload["eval_summary"]["failed"], 0)
        self.assertFalse(payload["safety"]["production_execute_query"])
        self.assertNotIn("ada@example.com", result.stdout)


if __name__ == "__main__":
    unittest.main()
