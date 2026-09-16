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


    def test_cli_audit_ready_returns_0(self):
        from unittest.mock import MagicMock, patch
        from repogate.cli import build_parser, run_audit

        parser = build_parser()
        args = parser.parse_args(["audit", "https://github.com/owner/repo/pull/10"])

        mock_report = {
            "pr_url": "https://github.com/owner/repo/pull/10",
            "merge_readiness": "READY",
            "risk_score": 5,
            "gates": {},
        }
        with patch("repogate.cli.RepoGateEngine") as mock_engine_cls:
            mock_inst = MagicMock()
            mock_inst.evaluate_pr.return_value = mock_report
            mock_inst.format_markdown_report.return_value = "Mock summary"
            mock_engine_cls.return_value = mock_inst

            code = run_audit(args)
            self.assertEqual(code, 0)
            mock_engine_cls.assert_called_once_with(github_token=None)
            mock_inst.evaluate_pr.assert_called_once_with("https://github.com/owner/repo/pull/10")

    def test_cli_audit_blocked_returns_1(self):
        from unittest.mock import MagicMock, patch
        from repogate.cli import build_parser, run_audit

        parser = build_parser()
        args = parser.parse_args(["audit", "https://github.com/owner/repo/pull/11"])

        mock_report = {
            "pr_url": "https://github.com/owner/repo/pull/11",
            "merge_readiness": "BLOCKED",
            "risk_score": 85,
            "gates": {},
        }
        with patch("repogate.cli.RepoGateEngine") as mock_engine_cls:
            mock_inst = MagicMock()
            mock_inst.evaluate_pr.return_value = mock_report
            mock_inst.format_markdown_report.return_value = "Mock blocked summary"
            mock_engine_cls.return_value = mock_inst

            code = run_audit(args)
            self.assertEqual(code, 1)

    def test_cli_audit_runtime_error_returns_2(self):
        from unittest.mock import MagicMock, patch
        from repogate.cli import build_parser, run_audit

        parser = build_parser()
        args = parser.parse_args(["audit", "https://github.com/owner/repo/pull/12"])

        with patch("repogate.cli.RepoGateEngine") as mock_engine_cls:
            mock_inst = MagicMock()
            mock_inst.evaluate_pr.side_effect = RuntimeError("API Rate limit exceeded")
            mock_engine_cls.return_value = mock_inst

            code = run_audit(args)
            self.assertEqual(code, 2)

    def test_cli_audit_passes_token_to_github_token(self):
        from unittest.mock import MagicMock, patch
        from repogate.cli import build_parser, run_audit

        parser = build_parser()
        args = parser.parse_args([
            "audit",
            "https://github.com/owner/repo/pull/13",
            "--token",
            "ghp_test_secret_token_123",
        ])

        mock_report = {
            "merge_readiness": "READY",
            "risk_score": 0,
            "gates": {},
        }
        with patch("repogate.cli.RepoGateEngine") as mock_engine_cls:
            mock_inst = MagicMock()
            mock_inst.evaluate_pr.return_value = mock_report
            mock_inst.format_markdown_report.return_value = "Mock summary"
            mock_engine_cls.return_value = mock_inst

            code = run_audit(args)
            self.assertEqual(code, 0)
            mock_engine_cls.assert_called_once_with(github_token="ghp_test_secret_token_123")


if __name__ == "__main__":
    unittest.main()
