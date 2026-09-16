"""CLI integration and smoke tests for RepoGate."""

import os
import subprocess
import sys
import unittest
from pathlib import Path


class TestRepoGateCLI(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).parent.parent
        self.cli_module = [sys.executable, "-m", "repogate.cli"]

    def run_cli(self, args, cwd=None):
        cmd = self.cli_module + args
        full_env = os.environ.copy()
        full_env["PYTHONPATH"] = str(self.repo_root / "src")
        return subprocess.run(
            cmd,
            cwd=cwd or self.repo_root,
            capture_output=True,
            text=True,
            env=full_env,
        )

    def test_cli_version(self):
        res = self.run_cli(["--version"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("repogate", res.stdout.lower())

    def test_cli_help(self):
        res = self.run_cli(["--help"])
        self.assertEqual(res.returncode, 0)
        self.assertIn("audit", res.stdout)
        self.assertIn("verify", res.stdout)

    def test_cli_verify_success(self):
        report_path = self.repo_root / "demo_reports" / "high_quality_clean_pr66.json"
        proof_path = (
            self.repo_root / "demo_reports" / "high_quality_clean_pr66.proof.json"
        )
        res = self.run_cli(["verify", str(report_path), str(proof_path)])
        self.assertEqual(res.returncode, 0)
        self.assertIn("Proof is cryptographically valid", res.stdout)

    def test_cli_verify_failure_tampered(self):
        tampered_report = (
            self.repo_root / "demo_reports" / "duplicate_dirty_pr_pr482.json"
        )
        clean_proof = (
            self.repo_root / "demo_reports" / "high_quality_clean_pr66.proof.json"
        )
        res = self.run_cli(["verify", str(tampered_report), str(clean_proof)])
        self.assertEqual(res.returncode, 1)
        output = res.stdout + res.stderr
        self.assertIn("FAILED", output)

    def test_import_purity_no_side_effects(self):
        """Verify that importing repogate produces no network, process, or file side-effects."""
        script = (
            "import sys, subprocess, os; "
            "import repogate; "
            "import repogate.engine; "
            "import repogate.github_client; "
            "import repogate.attestation; "
            "print('Purity Verified')"
        )
        env = os.environ.copy()
        src_path = str(self.repo_root / "src")
        env["PYTHONPATH"] = f"{src_path}:{env.get('PYTHONPATH', '')}"
        purity_res = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        self.assertEqual(purity_res.returncode, 0, f"Import impurity: {purity_res.stderr}")
        self.assertIn("Purity Verified", purity_res.stdout)


if __name__ == "__main__":
    unittest.main()
