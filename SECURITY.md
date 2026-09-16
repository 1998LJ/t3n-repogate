# Security Policy

RepoGate is an automated gatekeeper designed to inspect pull requests and enforce security and quality invariants. We treat the security of our own distribution pipeline, cryptographic attestation chain, and runtime dependencies with paramount seriousness.

---

## Supported Versions

Security fixes are released for the active stable release stream and developed on the default development branch (`main`).

| Version | Supported | Status |
| :--- | :--- | :--- |
| `1.1.x` (`v1.1.0`) | :white_check_mark: | Supported GA Release |
| `main` | :white_check_mark: | Active Development Branch |
| `< 1.1.0` (Prototype) | :x: | Legacy Hackathon Snapshot |

---

## Reporting a Vulnerability

If you discover a potential security vulnerability in RepoGate, **please do not open a public GitHub issue**. Publicly disclosing sensitive flaws can expose automated CI pipelines and cryptographic signers to adversarial abuse.

### Reporting Channels

1. **GitHub Security Advisory (Recommended)**: Submit an advisory privately via the repository's Security tab (Report a vulnerability).
2. **Private Disclosure**: If private vulnerability reporting is unavailable, reach out via private maintainer channels with a minimal reproducible proof-of-concept.

Please provide:
- Clear description of the vulnerability and attack vector.
- Affected component (`cli`, `engine`, `attestation`, `github_client`).
- Minimal reproduction steps and sample payload (with any tokens or private keys redacted).

---

## Security-Sensitive Areas

The following surfaces have heightened security invariants:

1. **Canonical Trust Anchor**: Packaged in `repogate.data/agent_identity.json`. Modification or tampering can alter authorized signer address or canonical DID.
2. **EIP-191 ECDSA Verification**: Verifier must fail closed on missing anchors, untrusted signers, wrong DIDs, or invalid hash lengths.
3. **Secret Isolation**: Zero secrets, private keys, or `.secret` files permitted in repository or build artifacts.
4. **CI Permissions**: GitHub Actions workflows strictly adhere to `permissions: contents: read`.
