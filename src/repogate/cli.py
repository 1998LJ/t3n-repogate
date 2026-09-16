"""CLI entry point for RepoGate."""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .attestation import (
    ETH_ACCOUNT_AVAILABLE,
    verify_proof_native,
    verify_proof_with_node,
)
from .engine import RepoGateEngine


def run_audit(args: argparse.Namespace) -> int:
    """Run PR quality audit and print/save report."""
    try:
        engine = RepoGateEngine(github_token=args.token)
    except Exception as e:
        sys.stderr.write(f"Error: failed to initialize RepoGateEngine: {e}\n")
        return 2

    try:
        report = engine.evaluate_pr(args.pr_url)
    except Exception as e:
        sys.stderr.write(f"Error: failed to evaluate PR: {e}\n")
        return 2

    # Handle output writing
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        sys.stdout.write(f"Report saved to {out_path}\n")
    else:
        # Default terminal summary
        summary = engine.format_markdown_report(report)
        sys.stdout.write(summary + "\n")

    # Exit code contract: 0 = READY, 1 = BLOCKED
    merge_readiness = report.get("merge_readiness")
    return 0 if merge_readiness == "READY" else 1


def run_verify(args: argparse.Namespace) -> int:
    """Verify cryptographic proof of an audit report.
    Tries Python-native verifier first (wheel portable).
    Falls back to Node bridge if requested or if Python crypto is missing.
    Exit codes:
    0 = Cryptographically valid and untampered
    1 = Proof invalid, tampered, forged, or unauthenticated
    2 = File IO or execution error
    """
    rep_file = Path(args.report)
    prf_file = Path(args.proof)

    if not rep_file.exists():
        sys.stderr.write(f"Error: report file not found: {rep_file}\n")
        return 2
    if not prf_file.exists():
        sys.stderr.write(f"Error: proof file not found: {prf_file}\n")
        return 2

    sys.stdout.write(f"[Verify] Verifying report {rep_file} against proof {prf_file}...\n")

    # If --node is explicitly requested, run Node reference verifier
    if getattr(args, "node", False):
        code, out, err = verify_proof_with_node(rep_file, prf_file)
        if out:
            sys.stdout.write(out)
        if err:
            sys.stderr.write(err)
        return code

    # Default production path: strictly Python-native verification
    if not ETH_ACCOUNT_AVAILABLE:
        sys.stderr.write(
            "Error: 'eth-account' package is missing but required for native proof verification.\n"
        )
        return 2

    res = verify_proof_native(rep_file, prf_file)
    if res.valid:
        sys.stdout.write(
            "[Verify] SUCCESS: Proof is cryptographically valid, untampered, and authorized.\n"
        )
        sys.stdout.write(json.dumps(res.to_dict(), indent=2) + "\n")
        return 0
    else:
        sys.stderr.write(f"[Verify] FAILED: {res.reason}\n")
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="repogate",
        description="Autonomous PR Quality & Cryptographic Attestation Gate Agent",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: audit
    audit_parser = subparsers.add_parser("audit", help="Audit a GitHub Pull Request")
    audit_parser.add_argument(
        "pr_url", help="GitHub Pull Request URL (e.g. https://github.com/owner/repo/pull/123)"
    )
    audit_parser.add_argument("--output", "-o", help="Path to save output JSON audit report")
    audit_parser.add_argument(
        "--token", "-t", help="GitHub Personal Access Token (defaults to GITHUB_TOKEN env var)"
    )

    # Subcommand: verify
    verify_parser = subparsers.add_parser(
        "verify", help="Verify cryptographic attestation proof of an audit report"
    )
    verify_parser.add_argument("report", help="Path to audit report JSON file")
    verify_parser.add_argument("proof", help="Path to cryptographic proof JSON file")
    verify_parser.add_argument(
        "--node",
        action="store_true",
        help="Force using Node/ethers bridge instead of Python native verifier",
    )

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "audit":
        return run_audit(args)
    elif args.command == "verify":
        return run_verify(args)

    return 2


if __name__ == "__main__":
    sys.exit(main())
