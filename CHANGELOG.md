# Changelog

All notable changes to RepoGate are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

## [1.1.0] - Unreleased

### Added
- **Standard Python Packaging**: Modernized to PEP 621 packaging with `pyproject.toml` and console entry point `repogate`.
- **Python-Native EIP-191 Verifier**: Implemented native verification using `eth-account` with zero Node.js runtime requirement for CLI usage.
- **Packaged Trust Anchor**: Packaged canonical `agent_identity.json` into `repogate.data` accessible via `importlib.resources`.
- **Composite GitHub Action Adapter**: Added `action.yml` and `action_adapter.py` for read-only PR auditing in GitHub Actions.
- **Structured Action Outputs**: Exported `risk-score`, `merge-readiness`, `recommended-action`, `target`, `report-path`, and `audit-exit-code`.
- **Automated GitHub Step Summary**: Formatted Markdown table highlighting audit findings directly in GitHub Actions UI.
- **Multi-Python CI Matrix**: Added comprehensive GitHub Actions workflow testing Python 3.10, 3.11, 3.12, 3.13, and 3.14.
- **Ruff Code Style & Linting**: Established automated code format and style enforcement.
- **Artifact Security Audit**: Added CI supply chain checks guaranteeing zero secret leakage in wheels and sdist.
- **Cross-Implementation Contract Tests**: Added parity tests ensuring exact behavior between Node and Python verifiers across positive and negative vectors.

### Changed
- **Directory Layout**: Reorganized codebase into standard `src/repogate/` structure.
- **CLI Architecture**: Decoupled CLI into `src/repogate/cli.py` with distinct subcommands (`audit`, `verify`) and standardized exit codes (`0=pass`, `1=blocker`, `2=error`).
- **Node Layer Role**: Re-positioned Node/T3N code (`verify_proof.js`, `t3n_auth.js`) from a runtime dependency to a reference compatibility oracle.
- **Compatibility Shim**: Retained legacy `repogate_engine.py` at root to maintain full backwards compatibility for existing demo scripts.

### Security
- **Fail-Closed Verification**: Ensured signature and identity checks fail immediately if packaged identity or signatures are corrupted.
- **Immutable Actions Pinning**: Pinned all GitHub Action steps to 40-character immutable commit SHAs.
- **Zero Token in Command Args**: GitHub tokens passed strictly via environment variables, avoiding command-line exposure.
- **Read-Only Permissions**: Default CI and Action execution restricted to `contents: read` / read-only permissions.
