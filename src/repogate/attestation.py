"""Attestation and cryptographic proof verification for RepoGate."""

import hashlib
import importlib.resources
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

try:
    from eth_account import Account
    from eth_account.messages import encode_defunct

    ETH_ACCOUNT_AVAILABLE = True
except ImportError:
    ETH_ACCOUNT_AVAILABLE = False


@dataclass(frozen=True)
class VerificationResult:
    valid: bool
    reason: Optional[str] = None
    hash_verified: Optional[bool] = None
    signer_address: Optional[str] = None
    agent_did: Optional[str] = None
    report_sha256: Optional[str] = None
    attested_at: Optional[str] = None
    standard: Optional[str] = None
    identity_binding: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


def load_canonical_identity(
    identity_config_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Load canonical trust anchor.
    Precedence:
    1. Explicit path parameter
    2. src/repogate/data/agent_identity.json (packaged resource)
    3. agent_identity.json in project root
    """
    if identity_config_path:
        p = Path(identity_config_path)
        if not p.exists():
            raise FileNotFoundError(f"Identity config not found: {identity_config_path}")
        return json.loads(p.read_text(encoding="utf-8"))

    # Try importlib.resources
    try:
        data_pkg = importlib.resources.files("repogate.data")
        identity_file = data_pkg.joinpath("agent_identity.json")
        if identity_file.is_file():
            return json.loads(identity_file.read_text(encoding="utf-8"))
    except Exception:
        pass

    # Fallback to local repo root
    root_file = Path(__file__).resolve().parent.parent.parent / "agent_identity.json"
    if root_file.exists():
        return json.loads(root_file.read_text(encoding="utf-8"))

    raise RuntimeError(
        "Canonical identity anchor (agent_identity.json) not found in package data or workspace."
    )


def verify_proof_native(
    report_path: Union[str, Path],
    proof_path: Union[str, Path],
    expected_signer: Optional[str] = None,
    identity_config: Optional[Union[str, Path]] = None,
) -> VerificationResult:
    """Verify cryptographic proof using Python-native eth-account verifier.
    Matches ethers v6 verifyMessage(report_sha256, signature) 100% in parity.
    Fail-closed: if trust anchor cannot be loaded, verification fails immediately.
    """
    if not ETH_ACCOUNT_AVAILABLE:
        return VerificationResult(
            valid=False,
            reason="eth-account library not available. Install repogate[crypto] or eth-account.",
        )

    r_path = Path(report_path)
    p_path = Path(proof_path)

    # Gate A: File existence and JSON parse
    if not r_path.exists():
        return VerificationResult(valid=False, reason=f"Report not found: {r_path}")
    if not p_path.exists():
        return VerificationResult(valid=False, reason=f"Proof not found: {p_path}")

    try:
        proof_data = json.loads(p_path.read_text(encoding="utf-8"))
    except Exception as e:
        return VerificationResult(valid=False, reason=f"Malformed proof JSON: {e}")

    # Gate B: Report integrity (SHA256 of raw bytes)
    try:
        raw_report = r_path.read_bytes()
        expected_hash = hashlib.sha256(raw_report).hexdigest()
    except Exception as e:
        return VerificationResult(valid=False, reason=f"Failed to read report bytes: {e}")

    claimed_hash = proof_data.get("report_sha256")
    if expected_hash != claimed_hash:
        return VerificationResult(
            valid=False,
            reason=f"Report hash mismatch! Expected {expected_hash}, proof has {claimed_hash}. REPORT HAS BEEN TAMPERED WITH.",
        )

    # Gate C: EIP-191 personal_sign recovery
    sig = proof_data.get("signature")
    if not sig:
        return VerificationResult(valid=False, reason="Signature missing in proof record.")

    try:
        # ethers wallet.signMessage(report_sha256_hex) signs the 64-char UTF-8 text
        msg = encode_defunct(text=claimed_hash)
        recovered_address = Account.recover_message(msg, signature=sig)
    except Exception as e:
        return VerificationResult(
            valid=False,
            reason=f"Cryptographic signature malformed or invalid: {e}",
        )

    # Gate D: Claimed signer consistency
    claimed_signer = proof_data.get("signer_address")
    if claimed_signer and recovered_address.lower() != claimed_signer.lower():
        return VerificationResult(
            valid=False,
            reason=f"Signer address mismatch! Proof claims {claimed_signer}, but recovered {recovered_address}.",
        )

    # Gate E & F: Canonical trust anchor & identity binding (Fail-Closed)
    try:
        trusted_identity = load_canonical_identity(identity_config)
    except Exception as e:
        return VerificationResult(
            valid=False,
            reason=f"Trust anchor load failure: {e}",
        )

    authorized_signer = expected_signer or trusted_identity.get("authorized_signer_address")
    if authorized_signer and recovered_address.lower() != authorized_signer.lower():
        return VerificationResult(
            valid=False,
            reason=f"Signer authority mismatch! Expected authorized signer {authorized_signer}, but got {recovered_address}. FORGED SIGNER.",
        )

    canonical_did = trusted_identity.get("agent_did")
    if canonical_did:
        proof_did = proof_data.get("agent_did")
        if not proof_did or proof_did != canonical_did:
            return VerificationResult(
                valid=False,
                reason=f"Agent DID mismatch! Expected canonical DID {canonical_did}, but got {proof_did}. UNTRUSTED AGENT DID.",
            )

    return VerificationResult(
        valid=True,
        hash_verified=True,
        signer_address=recovered_address,
        agent_did=proof_data.get("agent_did"),
        report_sha256=claimed_hash,
        attested_at=proof_data.get("attested_at"),
        standard=proof_data.get("verification_standard"),
        identity_binding=trusted_identity.get("identity_binding_model", "unbound"),
    )


def _verify_proof_with_node_reference(
    report_path: Union[str, Path],
    proof_path: Union[str, Path],
) -> Tuple[int, str, str]:
    """Legacy Node/ethers bridge for cross-implementation contract verification."""
    r_path = Path(report_path)
    p_path = Path(proof_path)

    if not r_path.exists():
        return 2, "", f"Error: report file not found: {r_path}\n"
    if not p_path.exists():
        return 2, "", f"Error: proof file not found: {p_path}\n"

    # Locate verify_proof.js in repo root
    repo_root = Path(__file__).resolve().parent.parent.parent
    js_verifier = repo_root / "verify_proof.js"
    if not js_verifier.exists():
        return 2, "", f"Error: Node verifier script not found at {js_verifier}\n"

    cmd = ["node", str(js_verifier), str(r_path), str(p_path)]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        code = 0 if res.returncode == 0 else 1
        return code, res.stdout, res.stderr
    except FileNotFoundError:
        return 2, "", "Error: 'node' executable not found in PATH\n"


# Compatibility oracle alias
verify_proof_with_node = _verify_proof_with_node_reference
