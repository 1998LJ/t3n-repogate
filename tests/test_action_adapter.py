"""Unit tests for GitHub Action adapter."""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from repogate.action_adapter import (
    emit_github_output,
    parse_bool,
    resolve_pr_url,
    resolve_report_path,
    run_action_adapter,
    write_step_summary,
)


class TestActionAdapter(unittest.TestCase):
    def test_parse_bool_true_values(self):
        for val in (True, "true", "True", "TRUE", "1", "yes", "YES", "on", "ON"):
            self.assertTrue(parse_bool(val), f"Failed for {val}")

    def test_parse_bool_false_values(self):
        for val in (False, "false", "False", "FALSE", "0", "no", "NO", "off", "OFF"):
            self.assertFalse(parse_bool(val), f"Failed for {val}")

    def test_parse_bool_invalid_rejected(self):
        invalid_inputs = ["treu", "TRUEE", "foobar", "invalid", "", " ", "2", None, 42]
        for val in invalid_inputs:
            with self.assertRaises(ValueError, msg=f"Should raise ValueError for {val}"):
                parse_bool(val)

    def test_invalid_fail_on_block_exits_2(self):
        env = {
            "INPUT_GITHUB-TOKEN": "test-token-123",
            "INPUT_PR-URL": "https://github.com/org/repo/pull/1",
            "INPUT_FAIL-ON-BLOCK": "treu",
        }
        with patch.dict(os.environ, env, clear=True):
            stderr_io = io.StringIO()
            with patch("sys.stderr", stderr_io):
                code = run_action_adapter()
                self.assertEqual(code, 2)
            err_msg = stderr_io.getvalue()
            self.assertIn("Error:", err_msg)
            self.assertIn("Invalid boolean value", err_msg)
            self.assertIn("treu", err_msg)

    def test_resolve_pr_url_explicit_wins(self):
        url = "https://github.com/foo/bar/pull/42"
        res = resolve_pr_url(url, "/fake/event.json")
        self.assertEqual(res, url)

    def test_resolve_pr_url_from_event_path(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            json.dump({"pull_request": {"html_url": "https://github.com/org/repo/pull/99"}}, f)
            event_file = f.name
        try:
            res = resolve_pr_url("", event_file)
            self.assertEqual(res, "https://github.com/org/repo/pull/99")
        finally:
            if os.path.exists(event_file):
                os.remove(event_file)

    def test_resolve_pr_url_missing_raises(self):
        with self.assertRaises(ValueError):
            resolve_pr_url("", None)
        with self.assertRaises(ValueError):
            resolve_pr_url("", "/nonexistent/path/event.json")

    def test_resolve_report_path_explicit(self):
        with tempfile.TemporaryDirectory() as td:
            exp = Path(td) / "custom" / "audit.json"
            res = resolve_report_path(str(exp))
            self.assertEqual(res, exp.resolve())

    def test_resolve_report_path_default(self):
        res = resolve_report_path("")
        self.assertTrue(str(res).endswith("repogate-report.json"))

    def test_missing_token_fails_exit_2(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("sys.stderr", io.StringIO()):
                code = run_action_adapter()
                self.assertEqual(code, 2)

    @patch("repogate.action_adapter.run_audit")
    def test_fail_on_block_true_returns_1(self, mock_audit):
        mock_audit.return_value = 1
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            json.dump(
                {
                    "target": "org/repo#1",
                    "risk_score": 45,
                    "merge_readiness": "BLOCKED",
                    "recommended_action": "FIX_REQUIRED",
                },
                f,
            )
            report_file = f.name

        env = {
            "INPUT_GITHUB-TOKEN": "test-token-123",
            "INPUT_PR-URL": "https://github.com/org/repo/pull/1",
            "INPUT_FAIL-ON-BLOCK": "true",
            "INPUT_REPORT-PATH": report_file,
        }
        try:
            with patch.dict(os.environ, env, clear=True):
                code = run_action_adapter()
                self.assertEqual(code, 1)
        finally:
            if os.path.exists(report_file):
                os.remove(report_file)

    @patch("repogate.action_adapter.run_audit")
    def test_fail_on_block_false_returns_0(self, mock_audit):
        mock_audit.return_value = 1
        with tempfile.NamedTemporaryFile("w", delete=False) as f:
            json.dump(
                {
                    "target": "org/repo#1",
                    "risk_score": 45,
                    "merge_readiness": "BLOCKED",
                    "recommended_action": "FIX_REQUIRED",
                },
                f,
            )
            report_file = f.name

        env = {
            "INPUT_GITHUB-TOKEN": "test-token-123",
            "INPUT_PR-URL": "https://github.com/org/repo/pull/1",
            "INPUT_FAIL-ON-BLOCK": "false",
            "INPUT_REPORT-PATH": report_file,
        }
        try:
            with patch.dict(os.environ, env, clear=True):
                code = run_action_adapter()
                self.assertEqual(code, 0)
        finally:
            if os.path.exists(report_file):
                os.remove(report_file)

    @patch("repogate.action_adapter.run_audit")
    def test_runtime_error_returns_2_regardless_of_fail_on_block(self, mock_audit):
        mock_audit.return_value = 2
        env = {
            "INPUT_GITHUB-TOKEN": "test-token-123",
            "INPUT_PR-URL": "https://github.com/org/repo/pull/1",
            "INPUT_FAIL-ON-BLOCK": "false",
        }
        with patch.dict(os.environ, env, clear=True):
            code = run_action_adapter()
            self.assertEqual(code, 2)

    def test_emit_github_output_and_step_summary(self):
        with (
            tempfile.NamedTemporaryFile("w", delete=False) as out_f,
            tempfile.NamedTemporaryFile("w", delete=False) as sum_f,
        ):
            out_path = out_f.name
            sum_path = sum_f.name

        try:
            with patch.dict(
                os.environ,
                {"GITHUB_OUTPUT": out_path, "GITHUB_STEP_SUMMARY": sum_path},
            ):
                emit_github_output("foo", "bar")
                write_step_summary(
                    {
                        "target": "org/repo#10",
                        "risk_score": 12,
                        "merge_readiness": "READY",
                        "recommended_action": "MERGE_READY",
                    },
                    Path("/path/to/report.json"),
                )

            with open(out_path, "r", encoding="utf-8") as f:
                self.assertIn("foo=bar\n", f.read())

            with open(sum_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.assertIn("## 🛡️ RepoGate PR Quality Audit", content)
                self.assertIn("READY", content)
        finally:
            if os.path.exists(out_path):
                os.remove(out_path)
            if os.path.exists(sum_path):
                os.remove(sum_path)


if __name__ == "__main__":
    unittest.main()
