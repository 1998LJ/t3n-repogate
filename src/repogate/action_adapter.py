"""GitHub Action adapter for RepoGate.

Bridges GitHub Action runtime environment, inputs, and outputs to the
standard RepoGate CLI contract. Emits Step Summary and maps exit codes.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from repogate.cli import build_parser, run_audit

TRUE_VALUES = {"true", "1", "yes", "on"}
FALSE_VALUES = {"false", "0", "no", "off"}


def parse_bool(val: Any) -> bool:
    """Safely and strictly parse boolean inputs from GitHub Action environment."""
    if isinstance(val, bool):
        return val

    normalized = str(val).strip().lower()

    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False

    raise ValueError(
        f"Invalid boolean value: {val!r}. Expected true/false, 1/0, yes/no, or on/off."
    )


def resolve_pr_url(explicit_url: Optional[str], event_path: Optional[str]) -> str:
    """Resolve pull request URL from explicit input or GITHUB_EVENT_PATH."""
    if explicit_url and explicit_url.strip():
        return explicit_url.strip()

    if event_path and os.path.isfile(event_path):
        try:
            with open(event_path, "r", encoding="utf-8") as f:
                event_data = json.load(f)
            pr_data = event_data.get("pull_request")
            if pr_data and "html_url" in pr_data:
                return str(pr_data["html_url"])
        except Exception as e:
            sys.stderr.write(f"Warning: failed to parse GITHUB_EVENT_PATH ({event_path}): {e}\n")

    raise ValueError(
        "RepoGate could not determine a pull request URL. "
        "Provide the pr-url input when running outside a pull_request event."
    )


def resolve_report_path(explicit_path: Optional[str]) -> Path:
    """Determine absolute destination path for generated JSON audit report."""
    if explicit_path and explicit_path.strip():
        p = Path(explicit_path.strip()).expanduser().resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    default_dir = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "repogate"
    default_dir.mkdir(parents=True, exist_ok=True)
    return (default_dir / "repogate-report.json").resolve()


def emit_github_output(name: str, value: Any) -> None:
    """Write key-value pair to GITHUB_OUTPUT file if present."""
    output_file = os.environ.get("GITHUB_OUTPUT")
    if output_file:
        with open(output_file, "a", encoding="utf-8") as f:
            f.write(f"{name}={value}\n")


def write_step_summary(report_data: Dict[str, Any], report_path: Path) -> None:
    """Write markdown summary table to GITHUB_STEP_SUMMARY if present."""
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_file:
        return

    target = report_data.get("target", "N/A")
    risk_score = report_data.get("risk_score", "N/A")
    readiness = report_data.get("merge_readiness", "N/A")
    action = report_data.get("recommended_action", "N/A")

    content = f"""## 🛡️ RepoGate PR Quality Audit

| Field | Result |
|---|---|
| **Target** | `{target}` |
| **Risk score** | `{risk_score}` |
| **Merge readiness** | **{readiness}** |
| **Recommended action** | `{action}` |
| **Report** | `{report_path}` |
"""
    try:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        sys.stderr.write(f"Warning: failed to write GITHUB_STEP_SUMMARY: {e}\n")


def run_action_adapter() -> int:
    """Main execution function for GitHub Action adapter."""
    token = os.environ.get("INPUT_GITHUB-TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token or not token.strip():
        sys.stderr.write("Error: github-token input is required but was empty.\n")
        return 2

    # Set GITHUB_TOKEN in environment so RepoGateEngine picks it up without argv exposure
    os.environ["GITHUB_TOKEN"] = token.strip()

    explicit_pr_url = os.environ.get("INPUT_PR-URL", "")
    event_path = os.environ.get("GITHUB_EVENT_PATH")

    try:
        pr_url = resolve_pr_url(explicit_pr_url, event_path)
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2

    try:
        fail_on_block = parse_bool(os.environ.get("INPUT_FAIL-ON-BLOCK", "true"))
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")
        return 2
    explicit_report_path = os.environ.get("INPUT_REPORT-PATH", "")
    report_file = resolve_report_path(explicit_report_path)

    # Build standard CLI args and invoke run_audit directly (clean boundary reuse)
    cli_parser = build_parser()
    args = cli_parser.parse_args(["audit", pr_url, "--output", str(report_file)])

    audit_code = run_audit(args)

    # Always attempt to extract report data if file was generated
    report_data: Dict[str, Any] = {}
    if report_file.is_file():
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                report_data = json.load(f)
        except Exception as e:
            sys.stderr.write(f"Warning: failed to parse generated report JSON: {e}\n")

    # Map and emit GitHub outputs
    emit_github_output("risk-score", report_data.get("risk_score", ""))
    emit_github_output("merge-readiness", report_data.get("merge_readiness", ""))
    emit_github_output("recommended-action", report_data.get("recommended_action", ""))
    emit_github_output("target", report_data.get("target", ""))
    emit_github_output("report-path", str(report_file))
    emit_github_output("audit-exit-code", audit_code)

    if report_data:
        write_step_summary(report_data, report_file)

    # Exit code mapping contract:
    # CLI 0 -> Action 0
    # CLI 1 -> Action 1 if fail_on_block else 0
    # CLI 2 -> Action 2 (fatal runtime/API error)
    if audit_code == 0:
        return 0
    elif audit_code == 1:
        return 1 if fail_on_block else 0
    else:
        return audit_code


if __name__ == "__main__":
    sys.exit(run_action_adapter())
