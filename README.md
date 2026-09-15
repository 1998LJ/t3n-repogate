# T3N RepoGate: Autonomous PR Quality & Risk Gate Agent

[![T3N Compatible](https://img.shields.io/badge/T3N-Sandboxed%20Agent-blue)](https://terminal3.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen)](test_repogate.py)

**RepoGate** is an enterprise-grade autonomous pull request risk evaluation and quality gate agent powered by the **Terminal 3 Network (T3N)** decentralized agent infrastructure.

It bridges off-chain repository lifecycle telemetry with T3N-attested zero-trust verification, enabling organizations and autonomous DAOs to automatically evaluate, score, and gate pull requests before merge.

---

## 🏛 Architecture & T3N Trust Anchor

RepoGate integrates deeply with the Terminal 3 Network (T3N) WebAssembly runtime and Decentralized Identifier (DID) system:

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
                       └──────────────────────────────────┘
```

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
npm install @terminal3/t3n-sdk
pip install requests pytest
```

### 3. Running T3N DID Attestation
```bash
node t3n_auth.js
```

### 4. Running PR Evaluation
```bash
python repogate_engine.py --pr https://github.com/yunaremaia/driftcheck/pull/66
```

---

## 📊 Live PR Evaluation Demo Cases

RepoGate includes 3 real-world open source pull request evaluations demonstrating each risk profile:

| Demo Case | Repository / PR | Risk Score | Decision | Key Findings |
| :--- | :--- | :--- | :--- | :--- |
| **Case 1: Clean High-Quality PR** | [`yunaremaia/driftcheck#66`](https://github.com/yunaremaia/driftcheck/pull/66) | **0 / 100** | `MERGED` | Minimal fix (16 loc), regression tests added, CI fully green. |
| **Case 2: Duplicate Stale Issue** | [`abduznik/bitbox#482`](https://github.com/abduznik/bitbox/pull/482) | **20 / 100** | `WAIT_FOR_REVIEW` | Function already implemented in upstream/main, closed to avoid duplication. |
| **Case 3: Concurrently Superseded** | [`yunaremaia/driftcheck#68`](https://github.com/yunaremaia/driftcheck/pull/68) | **70 / 100** | `FIX_REQUIRED` | Upstream maintainer landed parallel commit; policy commitments flagged. |

Full markdown and JSON evidence reports are stored in [`demo_reports/`](demo_reports/).

---

## 🛠 Running Unit Tests
```bash
python test_repogate.py
```
Outputs:
```text
......
----------------------------------------------------------------------
Ran 6 tests in 0.001s

OK
```

---

## 📝 T3N SDK Feedback & Observations

During the implementation and end-to-end integration with `@terminal3/t3n-sdk`, the following operational observations were noted:
1. **ESM vs CJS Packaging**: `@terminal3/t3n-sdk` strictly requires ESM imports (`import()`); using standard CommonJS `require()` exports an empty object. Documenting this in the primary quickstart improves developer onboarding.
2. **WASM Component Initialization**: The `loadWasmComponent()` helper resolves cleanly in Node environments, providing reliable cryptographic handshakes.

---

## 📄 License
MIT License. Created by 1998LJ as an autonomous trusted agent on Terminal 3 Network.
