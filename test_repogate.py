import unittest
from unittest.mock import patch, MagicMock
from repogate_engine import RepoGateEngine

class TestRepoGateEngine(unittest.TestCase):
    def setUp(self):
        self.engine = RepoGateEngine(github_token="mock_token")

    def test_policy_guard_detection(self):
        files = [
            {
                "filename": "SECURITY.md",
                "patch": "@@ -0,0 +1,5 @@\n+Please report to security@example.com within 48 hours for a 500 USD reward."
            }
        ]
        res = self.engine._eval_policy_guard(files)
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(len(res["findings"]), 3) # email, 48 hours, $500 reward

    def test_policy_guard_clean(self):
        files = [
            {
                "filename": "SECURITY.md",
                "patch": "@@ -0,0 +1,5 @@\n+To report vulnerabilities, please use GitHub Private Vulnerability Reporting."
            }
        ]
        res = self.engine._eval_policy_guard(files)
        self.assertEqual(res["status"], "PASS")

    def test_scope_gate_excessive(self):
        files = [{"filename": f"file_{i}.py"} for i in range(20)]
        pr_data = {"title": "fix: small bug", "additions": 1500, "deletions": 200}
        res = self.engine._eval_scope_gate(files, pr_data)
        self.assertEqual(res["status"], "HIGH_RISK")

    def test_scope_gate_clean(self):
        files = [{"filename": "fix.py"}, {"filename": "test_fix.py"}]
        pr_data = {"title": "fix: small bug", "additions": 10, "deletions": 2}
        res = self.engine._eval_scope_gate(files, pr_data)
        self.assertEqual(res["status"], "LOW_RISK")

    def test_regression_test_gate_fail(self):
        files = [{"filename": "core/engine.py"}]
        pr_data = {"title": "fix: prevent memory leak"}
        res = self.engine._eval_regression_test_gate(files, pr_data)
        self.assertEqual(res["status"], "FAIL")

    def test_regression_test_gate_pass(self):
        files = [{"filename": "core/engine.py"}, {"filename": "tests/test_engine.py"}]
        pr_data = {"title": "fix: prevent memory leak"}
        res = self.engine._eval_regression_test_gate(files, pr_data)
        self.assertEqual(res["status"], "PASS")

if __name__ == "__main__":
    unittest.main()
