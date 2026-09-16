"""CLI entry point for RepoGate."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .engine import RepoGateEngine


def run_audit(args: argparse.Namespace) -> int:
    """Execute PR audit command.
    Exit codes:
    0 = Gate ACCEPTED (merge readiness: READY_FOR_MAINTAINER_REVIEW)
    1 = Gate BLOCKED or CHANGES_REQUESTED
    2 = API / network / argument execution error
    """
    token = args.token or os.getenv("GITHUB_TOKEN")
    engine = RepoGateEngine(github_token=token)

    try:
        report = engine.evaluate_pr(args.pr_url)
    except Exception as e:
        sys.stderr.write(f"Error: failed to evaluate PR: {e}\n")
        return 2

    # Handle output writing
    if args.output:
        try:
            out_path = Path(args.output)
            out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        except Exception as e:
            sys.stderr.write(f"Error: failed to write output file: {e}\n")
            return 2
    else:
        # If no output file specified, print markdown summary to stdout
        summary = engine.generate_markdown_summary(report)
        print(summary)

    # Determine exit code based on merge readiness
    readiness = report.get("merge_readiness")
    if readiness == "READY_FOR_MAINTAINER_REVIEW":
        return 0
    else:
        # BLOCKED or CHANGES_REQUESTED
        return 1


def run_verify(args: argparse.Namespace) -> int:
    """Verify cryptographic proof using Node verification script.
    Exit codes:
    0 = Cryptographically valid and untampered
    1 = Proof invalid, tampered, or verification failed
    2 = File not found or execution error
    """
    report_file = Path(args.report)
    proof_file = Path(args.proof)

    if not report_file.is_file():
        sys.stderr.write(f"Error: report file not found: {report_file}\n")
        return 2
    if not proof_file.is_file():
        sys.stderr.write(f"Error: proof file not found: {proof_file}\n")
        return 2

    # Look for verify_proof.js in common locations
    candidates = [
        Path(__file__).parent.parent.parent / "verify_proof.js",
        Path.cwd() / "verify_proof.js",
        Path(__file__).parent / "verify_proof.js",
    ]
    script_path = None
    for c in candidates:
        if c.is_file():
            script_path = c
            break

    if not script_path:
        sys.stderr.write("Error: verify_proof.js not found in repository\n")
        return 2

    try:
        res = subprocess.run(
            ["node", str(script_path), str(report_file), str(proof_file)],
            capture_output=True,
            text=True,
        )
        sys.stdout.write(res.stdout)
        sys.stderr.write(res.stderr)
        return 0 if res.returncode == 0 else 1
    except FileNotFoundError:
        sys.stderr.write("Error: 'node' executable not found in PATH\n")
        return 2
    except Exception as e:
        sys.stderr.write(f"Error executing verification: {e}\n")
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repogate",
        description="Autonomous PR Quality & Cryptographic Attestation Gate Agent",
    )
    parser.add_argument(
        "-v", "--version", action="version", version=f"%(prog)s {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: audit
    audit_parser = subparsers.add_parser("audit", help="Audit a GitHub Pull Request")
    audit_parser.add_argument("pr_url", help="GitHub Pull Request URL (e.g. https://github.com/owner/repo/pull/123)")
    audit_parser.add_argument(
        "-o", "--output", help="Path to write the machine-readable JSON report"
    )
    audit_parser.add_argument(
        "--token", help="GitHub Personal Access Token (defaults to GITHUB_TOKEN env var)"
    )

    # Subcommand: verify
    verify_parser = subparsers.add_parser(
        "verify", help="Verify cryptographic attestation proof of an audit report"
    )
    verify_parser.add_argument("report", help="Path to audit report JSON file")
    verify_parser.add_argument("proof", help="Path to cryptographic proof JSON file")

    return parser


def main(args: Optional[List[str]] = None) -> int:
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if not parsed_args.command:
        parser.print_help()
        return 0

    if parsed_args.command == "audit":
        return run_audit(parsed_args)
    elif parsed_args.command == "verify":
        return run_verify(parsed_args)
    else:
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(main())
