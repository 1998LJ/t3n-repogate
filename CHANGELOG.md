# Changelog

All notable changes to RepoGate are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - Unreleased

### Added
- **Standard Python Packaging**: Modernized to PEP 621 packaging with `pyproject.toml` and console entry point `repogate`.
- **Python-Native EIP-191 Verifier**: Implemented native verification using `eth-account` with zero Node.js runtime requirement for CLI usage.
- **Packaged Trust Anchor**: Packaged canonical `agent_identity.json` into `repogate.data` accessible via `importlib.resources`.
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
- **Fail-Closed Verification**: Ensured signature and hash verification abort immediately if trust anchors or credentials fail to resolve.
- **Least-Privilege Workflows**: Configured `permissions: contents: read` across all CI pipelines.
- **Action Pinning**: Pinned all GitHub Actions dependencies to immutable full 40-character commit SHAs.

---

## [1.0.1] - 2026-09-15

### Added
- Pinned Canonical DID (`did:t3n:78131a400e1762aeac8d86e90b76449e02cf8169`) and Authorized Signer address.
- Added Adversarial Test 4 verifying defense against attacker re-signing.
- Synchronized repository license to standard MIT.

---

## [1.0.0] - 2026-09-15

### Added
- Initial release of RepoGate: 6-Gate PR quality evaluation engine.
- T3N decentralized identity binding and ECDSA proof generation via Node.js SDK.
- Demo reports and automated markdown evaluation generation.
