"""Attestation bridge for RepoGate cryptographic proof verification."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple


def find_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent.parent


def find_verifier_script() -> Path:
    direct = find_repo_root() / "verify_proof.js"
    if direct.exists():
        return direct
    cwd_candidate = Path.cwd() / "verify_proof.js"
    if cwd_candidate.exists():
        return cwd_candidate
    return direct


def verify_proof_with_node(report_path: str, proof_path: str) -> Tuple[int, str, str]:
    """Execute Node verification bridge against report and proof files.

    Returns:
        Tuple of (exit_code, stdout, stderr)
        exit_code 0: valid, untampered proof
        exit_code 1: invalid, tampered proof or failure
        exit_code 2: missing files, missing Node runtime, or internal error
    """
    rep_file = Path(report_path)
    prf_file = Path(proof_path)

    if not rep_file.exists():
        return 2, "", f"Error: report file not found: {report_path}\n"
    if not prf_file.exists():
        return 2, "", f"Error: proof file not found: {proof_path}\n"

    verifier = find_verifier_script()
    if not verifier.exists():
        return (
            2,
            "",
            f"Error: verify_proof.js not found at {verifier}. Node attestation verifier is repository-local.\n",
        )

    try:
        res = subprocess.run(
            ["node", str(verifier), str(rep_file), str(prf_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        return (0 if res.returncode == 0 else 1), res.stdout, res.stderr
    except FileNotFoundError:
        return 2, "", "Error: 'node' executable not found in PATH\n"
    except Exception as e:
        return 2, "", f"Error running node verifier: {e}\n"
