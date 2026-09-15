# T3N Public Submission & Verification Document: RepoGate

**Challenge Name:** Try out new docs to build a trusted agent with T3N that we can distribute / host  
**Sponsor:** Terminal 3 Network (T3N) via Superteam Earn  
**Prize Pool:** 290 USDC  
**Agent Name:** RepoGate Enterprise PR Quality & Risk Agent  
**Author:** 1998LJ (`0xEe265246639eb56cECF8AD2e2186644A47FCFb7A`)  
**Public Repository:** [https://github.com/1998LJ/t3n-repogate](https://github.com/1998LJ/t3n-repogate)  
**Verified Release Snapshot:** `v1.0.0` (Tagged Git Release)  
**Persistent Agent DID:** `did:t3n:78131a400e1762aeac8d86e90b76449e02cf8169`

---

## 1. Executive Summary

**RepoGate** is an enterprise-grade autonomous pull request risk evaluation and quality gate agent powered by the **Terminal 3 Network (T3N)** decentralized agent infrastructure.

In modern software development, development teams and autonomous coding agents face significant risks of duplicate submissions, stealth regression bugs, false-positive CI approvals, race conditions where PRs are superseded by concurrent commits, and unapproved legal/policy commitments. 

RepoGate acts as an autonomous zero-trust sentinel. It cryptographically authenticates via T3N's WebAssembly and Decentralized Identifier (DID) system, evaluates any public or enterprise GitHub PR through a rigorous **6-Gate Evaluation Matrix**, and produces tamper-proof, auditable JSON and markdown risk reports.

---

## 2. Technical Architecture & T3N Integration

RepoGate integrates with the newly updated Terminal 3 Network documentation and ADK (`@terminal3/t3n-sdk` v0.1.0-alpha.5):

1. **WASM-Powered Session**: Uses `loadWasmComponent()` to initialize the sandboxed cryptographic agent state machine.
2. **Multi-Party Trust Anchor**: Fetches the trusted manifest dynamically (`fetchTrustedManifest('sandbox')`) from `cn-api.sg.testnet.t3n.terminal3.io`.
3. **Decentralized Identifier (DID)**: Authenticates an on-chain keypair and generates an attested DID identity:
   - Authenticated Persistent DID: `did:t3n:78131a400e1762aeac8d86e90b76449e02cf8169`
   - Signer Key Persistence: Controlled via `process.env.T3N_SIGNER_PRIVATE_KEY` or local secure store; verified idempotent across runs.
   - State machine verification: Status Code `2` (ACTIVE)
4. **Autonomous Execution Pipeline**:
   - `Duplicate Gate (A)`: Deep search across GitHub API for merged/open PRs and target branches to prevent wasted cycles.
   - `Issue State & Race Gate (B)`: Detects open issue status and catches post-submit upstream race conditions.
   - `True CI Gate (C)`: Audits real remote GitHub Actions suites (`lint`, `test`, `typecheck`, `eval`), refusing to conflate local test passing with authoritative CI.
   - `Regression Test Gate (D)`: Validates TDD contracts and flags unverified logic changes or removed xfail flags.
   - `Scope Gate (E)`: Calculates Diff Churn Ratios and enforces the Minimal Correct Fix standard.
   - `Policy Document Guard (F)`: Scans legal/governance files (`SECURITY.md`, `SLA`, `SUPPORT.md`) for unapproved SLAs, turnaround promises, or contact addresses.

---

## 3. Real-World Demo Cases & Evidence

RepoGate was exercised against three real-world pull requests representing distinct lifecycle challenges:

### Case 1: High Quality Clean PR (Benchmark Pass)
- **PR:** [`yunaremaia/driftcheck#66`](https://github.com/yunaremaia/driftcheck/pull/66)
- **Risk Score:** **0 / 100** (Low Risk)
- **Decision:** `MERGED`
- **Telemetry:** 16 lines changed, dedicated unit test added, 1,089 tests passing, remote CI fully green.
- **Artifact:** [`demo_reports/high_quality_clean_pr66.md`](https://github.com/1998LJ/t3n-repogate/blob/main/demo_reports/high_quality_clean_pr66.md)

### Case 2: Duplicate Stale Issue PR (Duplicate Detection)
- **PR:** [`abduznik/bitbox#482`](https://github.com/abduznik/bitbox/pull/482)
- **Risk Score:** **65 / 100**
- **Decision:** `CLOSE_DUPLICATE` (Flagged Duplicate of Merged Feature)
- **Telemetry:** Deep GitHub search flagged that linked Issue #379 was already completed and merged into main via PR #397; identified target file presence on main branch and recommended immediate closure.
- **Artifact:** [`demo_reports/duplicate_dirty_pr_pr482.md`](https://github.com/1998LJ/t3n-repogate/blob/main/demo_reports/duplicate_dirty_pr_pr482.md)

### Case 3: Concurrently Superseded PR (Post-Submit Race & Policy Guard)
- **PR:** [`yunaremaia/driftcheck#68`](https://github.com/yunaremaia/driftcheck/pull/68)
- **Risk Score:** **85 / 100** (High Risk)
- **Decision:** `SUPERSEDED` (Superseded by Upstream)
- **Telemetry:** Detected that upstream maintainer landed a parallel commit directly on main resolving the same security doc; Policy Guard independently flagged unapproved response SLA promises.
- **Artifact:** [`demo_reports/superseded_race_pr_pr68.md`](https://github.com/1998LJ/t3n-repogate/blob/main/demo_reports/superseded_race_pr_pr68.md)

---

## 4. Documentation & Developer Experience Feedback (Real Bugs Noted)

In compliance with the challenge objective ("Try out new docs to build a trusted agent..."), here are concrete observations and bugs identified during the build:

1. **CommonJS vs ESM Import Incompatibility**:
   - *Observation:* The documentation showcases `const { T3nClient } = require('@terminal3/t3n-sdk')`. However, running CommonJS `require()` exports an empty object (`{}`) because the package only exports ESM modules via `./dist/esm/index.js`.
   - *Fix Needed in Docs:* Recommend `import` syntax or async `await import('@terminal3/t3n-sdk')` for Node runtimes.
2. **Claim Portal Form Validation**:
   - *Observation:* On `https://www.terminal3.io/claim-page`, certain dynamic dropdown selections for role/industry can intercept standard form submission without surfacing visible validation errors when scripted.

---

## 5. Verification & How to Run

Clone and run the complete test suite and demo suite in under 60 seconds:

```bash
git clone https://github.com/1998LJ/t3n-repogate.git
cd t3n-repogate
npm install
python test_repogate.py
node t3n_auth.js
node verify_proof.js
```
