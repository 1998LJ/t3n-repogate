import unittest
from unittest.mock import patch, MagicMock
import os
import subprocess
from pathlib import Path
from repogate_engine import RepoGateEngine

PROJECT_ROOT = str(Path(__file__).resolve().parent)

class TestRepoGateEngine(unittest.TestCase):
    def setUp(self):
        self.engine = RepoGateEngine(proxies={})

    def test_policy_guard_detection(self):
        files = [
            {
                "filename": "SECURITY.md",
                "patch": "@@ -0,0 +1,5 @@\n+Please report to security@example.com within 48 hours for a 500 USD reward."
            }
        ]
        res = self.engine._eval_policy_guard(files)
        self.assertEqual(res["status"], "FAIL")
        self.assertEqual(len(res["findings"]), 3)

    def test_scope_guard_large_diff(self):
        files = [{"filename": f"file_{i}.py", "patch": "@@ -1 +1 @@\n+change"} for i in range(25)]
        pr = {"changed_files": 25, "additions": 25, "deletions": 0, "title": "fix bug"}
        res = self.engine._eval_scope_gate(pr, files)
        self.assertEqual(res["status"], "EXCESSIVE_SCOPE")
        self.assertIn("25 files", res["reason"])

    def test_regression_guard_xfail_removal(self):
        files = [
            {
                "filename": "tests/test_foo.py",
                "patch": "@@ -10,3 +10 @@\n-@pytest.mark.xfail(strict=True)\n def test_something():\n+    assert True"
            }
        ]
        res = self.engine._eval_regression_test_gate(files)
        self.assertEqual(res["status"], "PASSED")
        self.assertTrue(res["xfail_removed_verified"])
        self.assertEqual(res["test_files"], ["tests/test_foo.py"])

    def test_regression_guard_no_tests_for_code_change(self):
        files = [
            {
                "filename": "src/core/parser.py",
                "patch": "@@ -10,2 +10,2 @@\n-return False\n+return True"
            }
        ]
        res = self.engine._eval_regression_test_gate(files)
        self.assertEqual(res["status"], "MISSING_TESTS")
        self.assertIn("Modified 1 production code files", res["reason"])

    def test_duplicate_gate_merged_issue(self):
        def mock_side_effect(url, **kwargs):
            m = MagicMock()
            if "search/issues" in url:
                m.status_code = 200
                m.json.return_value = {
                    "items": [
                        {"number": 397, "title": "Add tool octal_to_binary (#379)", "state": "closed", "html_url": "https://github.com/abduznik/bitbox/pull/397"}
                    ]
                }
            elif "contents" in url:
                m.status_code = 200
                m.json.return_value = {"name": "octal_to_binary.py", "path": "tools/octal_to_binary.py"}
            else:
                m.status_code = 200
                m.json.return_value = {"default_branch": "main"}
            return m

        with patch.object(self.engine, "_get", side_effect=mock_side_effect):
            pr_data = {
                "title": "Add tool octal_to_binary (#379)",
                "body": "Closes #379",
                "base": {"ref": "main"},
                "number": 482
            }
            files = [{"filename": "tools/octal_to_binary.py", "status": "modified", "patch": "+# author: @1998LJ\n-# author: @MateiB20"}]
            res = self.engine._eval_duplicate_gate("abduznik", "bitbox", pr_data, files)
            self.assertEqual(res["status"], "DUPLICATE")
            self.assertIn("was already implemented and merged in PR #397", res["reason"])

    def test_ci_gate_statuses(self):
        dummy_pr = {"head": {"sha": "abc1234"}}
        
        with patch.object(self.engine, "_get") as mock_get:
            # Mock success
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "workflow_runs": [{"conclusion": "success", "status": "completed"}]
            }
            mock_get.return_value = mock_resp
            ci_success = self.engine._eval_ci_gate("https://api.github.com/repos/dummy/repo", dummy_pr)
            self.assertEqual(ci_success["status"], "CI Passed")

            # Mock failure
            mock_resp.json.return_value = {
                "workflow_runs": [{"conclusion": "failure", "status": "completed"}]
            }
            ci_failed = self.engine._eval_ci_gate("https://api.github.com/repos/dummy/repo", dummy_pr)
            self.assertEqual(ci_failed["status"], "CI Failed")

            # Mock pending/submitted
            mock_resp.json.return_value = {
                "workflow_runs": [{"conclusion": None, "status": "in_progress"}]
            }
            ci_pending = self.engine._eval_ci_gate("https://api.github.com/repos/dummy/repo", dummy_pr)
            self.assertEqual(ci_pending["status"], "Submitted")

    def test_clean_machine_proxy_default(self):
        with patch.dict(os.environ, {}, clear=True):
            engine = RepoGateEngine()
            self.assertIsNone(engine.proxies)

    def test_t3n_persistent_did_and_tamper_proof(self):
        # Run node t3n_auth.js twice and ensure exact same DID
        cmd = ["node", "-e", """
        const { main } = require('./t3n_auth');
        Promise.all([main(), main()]).then(([r1, r2]) => {
          if (r1.did !== r2.did) {
            console.error('DID Mismatch:', r1.did, r2.did);
            process.exit(1);
          }
          console.log('DID_PERSISTENT_OK');
        }).catch(err => {
          console.error(err);
          process.exit(1);
        });
        """]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        self.assertIn("DID_PERSISTENT_OK", proc.stdout)

        # Test tamper proof
        verify_cmd = ["node", "verify_proof.js"]
        v_proc = subprocess.run(verify_cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        self.assertEqual(v_proc.returncode, 0)
        self.assertIn("SUCCESS: Proof is cryptographically valid", v_proc.stdout)

        # Test tamper rejection (negative test)
        tamper_cmd = ["node", "-e", """
        const { verifyProof } = require('./verify_proof');
        const path = require('path');
        const fs = require('fs');
        const rPath = path.join(__dirname, 'demo_reports', 'high_quality_clean_pr66.json');
        const pPath = path.join(__dirname, 'demo_reports', 'high_quality_clean_pr66.proof.json');
        const tPath = '/tmp/tamper_sub_test.json';
        fs.writeFileSync(tPath, fs.readFileSync(rPath, 'utf8') + ' ');
        const res = verifyProof(tPath, pPath);
        if (res.valid) process.exit(1);
        console.log('TAMPER_REJECTED_OK');
        """]
        t_proc = subprocess.run(tamper_cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        self.assertEqual(t_proc.returncode, 0)
        self.assertIn("TAMPER_REJECTED_OK", t_proc.stdout)

        # Test wrong signer rejection (negative test)
        signer_cmd = ["node", "-e", """
        const { verifyProof } = require('./verify_proof');
        const path = require('path');
        const rPath = path.join(__dirname, 'demo_reports', 'high_quality_clean_pr66.json');
        const pPath = path.join(__dirname, 'demo_reports', 'high_quality_clean_pr66.proof.json');
        const wrongSigner = '0x0000000000000000000000000000000000000000';
        const res = verifyProof(rPath, pPath, wrongSigner);
        if (res.valid) process.exit(1);
        console.log('WRONG_SIGNER_REJECTED_OK');
        """]
        s_proc = subprocess.run(signer_cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
        self.assertEqual(s_proc.returncode, 0)
        self.assertIn("WRONG_SIGNER_REJECTED_OK", s_proc.stdout)

if __name__ == "__main__":
    unittest.main()
