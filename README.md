# T3N RepoGate: Autonomous PR Quality & Risk Gate Agent

[![T3N Compatible](https://img.shields.io/badge/T3N-Sandboxed%20Agent-blue)](https://terminal3.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen)](test_repogate.py)

**RepoGate** is an enterprise-grade autonomous pull request risk evaluation and quality gate agent powered by the **Terminal 3 Network (T3N)** decentralized agent infrastructure.

It bridges off-chain repository lifecycle telemetry with T3N-attested zero-trust verification, enabling organizations and autonomous DAOs to automatically evaluate, score, and gate pull requests before merge.

---

## 🏛 Architecture & T3N Trust Anchor

RepoGate integrates with the Terminal 3 Network (T3N) WebAssembly runtime (`@terminal3/t3n-sdk` 5.16.0) and Decentralized Identifier (DID) system:

```
                  ┌──────────────────────────────────────────────┐
                  │          Enterprise PR / CI Pipeline         │
                  └──────────────────────┬───────────────────────┘
                                         │
                       ┌─────────────────▼─────────────────┐
                       │    RepoGate Autonomous Engine     │
                       │    (6-Gate Risk & Quality Matrix) │
                       └─────────────────┬─────────────────┘
                                         │
                                         ▼
            ┌────────────────────────────────────────────────────────┐
            │             Terminal 3 Network (T3N ADK)               │
            │  - Cryptographic DID Attestation                       │
            │  - WASM Client Session & State Machine                 │
            │  - Multi-Party Trust Anchor Validation                 │
            └────────────────────────────┬───────────────────────────┘
                                         │
                                         ▼
                       ┌──────────────────────────────────┐
                       │ Tamper-Proof Audit Artifacts:    │
                       │ 1. Machine report.json           │
                       │ 2. Human REPORT.md (Evidence)    │
                       │ 3. Attested report.proof.json    │
                       └──────────────────────────────────┘
```

### Canonical Agent Identity & Verification Model
RepoGate binds audit reports cryptographically using standard ECDSA secp256k1 message signing. The official DID and authorized signer address are pinned in [`agent_identity.json`](agent_identity.json):
- **Agent DID**: `did:t3n:78131a400e1762aeac8d86e90b76449e02cf8169`
- **Authorized Signer**: `0x64c8C36d03f7deC27553AfF8d98d953D59b049FD`
- **Identity Binding Model**: Release-pinned DID/signer identity (`T3N-REPOGATE-v1-ECDSA`)

### The 6-Gate Evaluation Matrix

1. **Duplicate Gate (`A`)**:
   - Searches historical merged and open PRs for overlapping tool/function implementations.
   - Detects if the target functionality has already landed on the `upstream/main` branch.
   - Flags dirty or duplicate issues before developer effort is wasted.
2. **Issue State & Race Gate (`B`)**:
   - Validates if the linked Issue remains open and unassigned.
   - Executes **Post-Submit Race Detection** to detect if upstream maintainers concurrently closed or resolved the issue.
3. **True CI Gate (`C`)**:
   - Inspects real remote GitHub Actions workflow runs (`test`, `lint`, `typecheck`, `eval`).
   - Strictly distinguishes between local self-testing and authoritative remote CI green status.
4. **Regression Test Gate (`D`)**:
   - Enforces test coverage for bug fixes (Failing Test -> Regression Pass verification).
   - Flags instances where `@pytest.mark.xfail` or tests are removed without proper implementation.
5. **Scope & Hygiene Gate (`E`)**:
   - Enforces Minimal Correct Fix philosophy (flags abnormal diff bloat, extraneous file churn, dead residue).
6. **Policy Document Guard (`F`)**:
   - Restricts unvetted commitments in policy files (`SECURITY.md`, `SUPPORT.md`, `SLA`, `LICENSE`).
   - Prevents unauthorized SLAs, fabricated response turnaround times, and hardcoded external contact emails.

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
- Python 3.10+
- Node.js 18+ (for T3N WebAssembly / ADK runtime)

### 2. Setup
```bash
git clone https://github.com/1998LJ/t3n-repogate.git
cd t3n-repogate
npm install @terminal3/t3n-sdk ethers
pip install requests pytest
```

### 3. Environment Configuration
Set your T3N signer private key (or let RepoGate generate/load a persistent key at `~/.t3n_agent/repogate_signer.key`):
```bash
export T3N_SIGNER_PRIVATE_KEY="your_secp256k1_hex_key"
```

### 4. Running T3N DID Attestation
```bash
node t3n_auth.js
```

### 5. Running PR Evaluation
```bash
python repogate_engine.py --pr https://github.com/yunaremaia/driftcheck/pull/66
```

---

## 📊 Live PR Evaluation Demo Cases

RepoGate includes 3 real-world open source pull request evaluations demonstrating each risk profile:

| Demo Case | Repository / PR | Risk Score | Decision | Key Findings |
| :--- | :--- | :--- | :--- | :--- |
| **Case 1: Clean High-Quality PR** | [`yunaremaia/driftcheck#66`](https://github.com/yunaremaia/driftcheck/pull/66) | **0 / 100** | `MERGED` | Minimal fix (16 loc), regression tests added, CI fully green. |
| **Case 2: Duplicate Stale Issue** | [`abduznik/bitbox#482`](https://github.com/abduznik/bitbox/pull/482) | **65 / 100** | `CLOSE_DUPLICATE` | Function already implemented in upstream/main via PR #397, closed to avoid duplication. |
| **Case 3: Concurrently Superseded** | [`yunaremaia/driftcheck#68`](https://github.com/yunaremaia/driftcheck/pull/68) | **85 / 100** | `SUPERSEDED` | Upstream maintainer landed parallel commit on main; policy commitments flagged. |

Full markdown and JSON evidence reports are stored in [`demo_reports/`](demo_reports/).

---

## 🛠 Running Unit & Adversarial Tests
```bash
python test_repogate.py
```
Outputs:
```text
........
----------------------------------------------------------------------
Ran 8 tests in 11.215s

OK
```

---

## 🔐 Cryptographic Proof Verification

RepoGate signs audit reports using ECDSA secp256k1, generating an attested `proof.json`. The independent verifier validates:
1. Report integrity (SHA-256 hash match).
2. ECDSA signature recoverability.
3. Signer match against the authorized release-pinned identity (`agent_identity.json`).
4. Proof agent DID match against canonical DID.

Run verification:
```bash
node verify_proof.js demo_reports/high_quality_clean_pr66.json demo_reports/high_quality_clean_pr66.proof.json
```

Output:
```json
[Verify] SUCCESS: Proof is cryptographically valid, untampered, and authorized.
{
  "valid": true,
  "hash_verified": true,
  "signer_address": "0x64c8C36d03f7deC27553AfF8d98d953D59b049FD",
  "agent_did": "did:t3n:78131a400e1762aeac8d86e90b76449e02cf8169",
  "report_sha256": "8785db228cab96748c41f0586dfc2ad16f17b1132f7d65ce5757c8b2012bd441",
  "attested_at": "2026-09-15T08:13:16.815Z",
  "standard": "T3N-REPOGATE-v1-ECDSA",
  "identity_binding": "release-pinned DID/signer identity"
}
```

Negative & Adversarial testing is strictly enforced:
- **Tampered report**: Fails integrity check (Hash mismatch).
- **Wrong expected signer**: Fails authority check.
- **Attacker re-sign**: Fails identity binding check against `agent_identity.json`.

---

## 📝 T3N SDK Feedback & Observations

During the implementation and end-to-end integration with `@terminal3/t3n-sdk` (v5.16.0), the following operational observations were noted:
1. **ESM vs CJS Packaging**: `@terminal3/t3n-sdk` strictly requires ESM imports (`import()`); using standard CommonJS `require()` exports an empty object. Documenting this in the primary quickstart improves developer onboarding.
2. **WASM Component Initialization**: The `loadWasmComponent()` helper resolves cleanly in Node environments, providing reliable cryptographic handshakes.
3. **DID-Signer Binding**: T3N ADK client utilizes WASM for DID session handshakes. For standalone verifiable attestations, pairing ECDSA secp256k1 message signing with a release-pinned canonical identity manifest (`agent_identity.json`) allows external verifiers to independently confirm authenticity without running a live node daemon.

---

## 📄 License
[MIT License](LICENSE). Created by 1998LJ as an autonomous trusted agent on Terminal 3 Network.
