# RepoGate

Autonomous PR Quality & Cryptographic Attestation Gate Agent.

[![CI](https://github.com/1998LJ/t3n-repogate/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/1998LJ/t3n-repogate/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue)](https://www.python.org/downloads/)
[![Code Style: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

RepoGate is an enterprise-grade automated gatekeeper for GitHub Pull Requests. It evaluates code modifications across 6 rigorous safety gates, detects duplicate or superseded race-condition PRs, identifies silent regressions, and produces tamper-evident cryptographic proofs bound to a persistent Agent DID via EIP-191 ECDSA signatures.

---

## Quickstart (v1.1 Distribution Architecture)

### 1. Installation

RepoGate core is pure Python and runs independently of Node.js:

```bash
# Recommended for CLI usage (upcoming v1.1 PyPI release)
pipx install t3n-repogate

# Or install in your active Python environment
pip install t3n-repogate
```

> **Note**: For developers building from source or testing the development branch:
> ```bash
> pip install dist/*.whl
> ```

### 2. Audit a Pull Request

Run a comprehensive 6-gate audit against any public or private GitHub PR:

```bash
# Basic terminal output
repogate audit https://github.com/OWNER/REPO/pull/123

# Save machine-readable JSON report
repogate audit https://github.com/OWNER/REPO/pull/123 --output report.json

# Authenticate with GitHub Token (or set GITHUB_TOKEN environment variable)
export GITHUB_TOKEN="your_github_token"
repogate audit https://github.com/OWNER/REPO/pull/123
```

### 3. Verify Cryptographic Proof

RepoGate features a **Python-native EIP-191 proof verifier**. Proofs can be verified anywhere without Node.js or npm dependencies:

```bash
repogate verify report.json proof.json
```

- **Exit Code `0`**: Proof is valid, report is untampered, and signed by the canonical authorized identity.
- **Exit Code `1`**: Hash mismatch (tampering detected), wrong signer, invalid DID, or corrupted signature.
- **Exit Code `2`**: File I/O, network, or execution error.

---

## GitHub Action Integration

RepoGate can be integrated directly into your repository's PR workflows without cloning or running Node.js.

> **Note**: `@v1` becomes available after the v1.1 GA release. During pre-release, use `@main` or commit SHAs.

```yaml
name: RepoGate

on:
  pull_request:

permissions:
  actions: read
  contents: read
  issues: read
  pull-requests: read
  statuses: read

jobs:
  repogate:
    runs-on: ubuntu-latest
    steps:
      - id: repogate
        uses: 1998LJ/t3n-repogate@v1
        with:
          github-token: ${{ github.token }}
          fail-on-block: "true" # Default: fails the workflow if PR is marked BLOCKED

      - name: Inspect Verdict
        if: always()
        run: |
          echo "Target: ${{ steps.repogate.outputs.target }}"
          echo "Risk: ${{ steps.repogate.outputs.risk-score }}"
          echo "Decision: ${{ steps.repogate.outputs.recommended-action }}"
          echo "Report: ${{ steps.repogate.outputs.report-path }}"
```

### Action Modes
- **Enforcement Gate (`fail-on-block: "true"`)**: Automatically blocks the workflow (exit code 1) if RepoGate determines the PR is `BLOCKED`.
- **Advisory Mode (`fail-on-block: "false"`)**: Evaluates risk and exports machine-readable findings without breaking the CI pipeline.

---

## Architecture Overview

```
External Developer / CI
        │
        ▼
   repogate CLI
    ├── audit  ──> Python 6-Gate Engine ──> GitHub REST API ──> Machine-Readable Report
    └── verify ──> Python-Native EIP-191 Verifier ──> Packaged Trust Anchor (agent_identity.json)
                         │
                         └── (Optional Reference Oracle: Node/ethers verify_proof.js)
```

- **Python Execution Engine**: Evaluates PR diffs, commits, CI status, and regression risk.
- **Cryptographic Trust Anchor**: Encapsulated in `repogate.data/agent_identity.json` and permanently bound to canonical Agent DID (`did:t3n:78131a400e1762aeac8d86e90b76449e02cf8169`).
- **Node/T3N Layer**: Serves as a reference implementation, proof generator, and cross-language compatibility oracle (`verify_proof.js` / `t3n_auth.js`). Node.js 24 is **only** needed for attestation development, never for CLI execution.

---

## The 6 Enforcement Gates

1. **Duplicate PR Gate**: Identifies identical issue resolutions and previously closed/merged PR duplicates.
2. **Superseded Race Gate**: Flags competing PRs that modify identical target files within close intervals.
3. **CI Status Gate**: Validates head commit GitHub Actions runs (success / pending / failure).
4. **Regression Guard**: Intercepts removed tests, loosened assertions, and suppressed pytest markers.
5. **Scope Guard**: Detects out-of-scope modifications, massive multi-file changes, and unintended file mutations.
6. **Policy Guard**: Intercepts unconfirmed bounty claims, fake SLA commitments, leaked tokens, and unauthorized licenses.

---

## Development Setup

Requirements: **Python 3.10+** (and optionally **Node.js 24+** for reference oracle testing).

```bash
# 1. Clone repository
git clone https://github.com/1998LJ/t3n-repogate.git
cd t3n-repogate

# 2. Set up Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Optional: Set up Node oracle dependencies
npm ci
```

### Running Checks Locally

```bash
# Code formatting & static lint
ruff check .
ruff format --check .

# Full Python test suite (unit tests, CLI tests, adversarial tests)
python3 -m unittest discover -s tests -v

# Cross-language Node reference oracle test
npm test

# Standard isolated PEP 517 build
python3 -m build
```

---

## License

This project is licensed under the [MIT License](LICENSE).
