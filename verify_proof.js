const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { ethers } = require('ethers');

// P0-1 & P0-2: Strict ECDSA public-key verification & release-pinned DID/signer identity binding
function verifyProof(reportPath, proofPath, expectedSignerAddress, identityConfigPath) {
  if (!fs.existsSync(reportPath)) throw new Error(`Report not found: ${reportPath}`);
  if (!fs.existsSync(proofPath)) throw new Error(`Proof not found: ${proofPath}`);

  const rawReport = fs.readFileSync(reportPath, 'utf8');
  const proof = JSON.parse(fs.readFileSync(proofPath, 'utf8'));

  const expectedHash = crypto.createHash('sha256').update(rawReport, 'utf8').digest('hex');

  // 1. Check report hash (Integrity)
  if (expectedHash !== proof.report_sha256) {
    return {
      valid: false,
      reason: `Report hash mismatch! Expected ${expectedHash}, proof has ${proof.report_sha256}. REPORT HAS BEEN TAMPERED WITH.`
    };
  }

  // 2. Recover signer address from ECDSA signature
  let recoveredAddress = null;
  try {
    recoveredAddress = ethers.verifyMessage(proof.report_sha256, proof.signature);
  } catch (err) {
    return {
      valid: false,
      reason: `Cryptographic signature malformed or invalid: ${err.message}`
    };
  }

  // 3. Check address match with proof record
  if (proof.signer_address && recoveredAddress.toLowerCase() !== proof.signer_address.toLowerCase()) {
    return {
      valid: false,
      reason: `Signer address mismatch! Proof claims ${proof.signer_address}, but recovered ${recoveredAddress}.`
    };
  }

  // 4. Identity Binding (Release-pinned DID/signer identity)
  // Default to agent_identity.json in project root if not explicitly provided
  const configPath = identityConfigPath || path.join(__dirname, 'agent_identity.json');
  let trustedIdentity = null;
  if (fs.existsSync(configPath)) {
    try {
      trustedIdentity = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    } catch (e) {
      return {
        valid: false,
        reason: `Failed to parse trusted identity config from ${configPath}: ${e.message}`
      };
    }
  }

  // Verify against authorized signer address:
  // Precedence: explicit CLI override -> agent_identity.json -> fail if strict required
  const authorizedSigner = expectedSignerAddress || (trustedIdentity ? trustedIdentity.authorized_signer_address : null);
  if (authorizedSigner && recoveredAddress.toLowerCase() !== authorizedSigner.toLowerCase()) {
    return {
      valid: false,
      reason: `Signer authority mismatch! Expected authorized signer ${authorizedSigner}, but got ${recoveredAddress}. FORGED SIGNER.`
    };
  }

  // Verify DID binding against canonical agent_identity.json
  if (trustedIdentity && trustedIdentity.agent_did) {
    if (!proof.agent_did || proof.agent_did !== trustedIdentity.agent_did) {
      return {
        valid: false,
        reason: `Agent DID mismatch! Expected canonical DID ${trustedIdentity.agent_did}, but got ${proof.agent_did}. UNTRUSTED AGENT DID.`
      };
    }
  }

  return {
    valid: true,
    hash_verified: true,
    signer_address: recoveredAddress,
    agent_did: proof.agent_did,
    report_sha256: proof.report_sha256,
    attested_at: proof.attested_at,
    standard: proof.verification_standard,
    identity_binding: trustedIdentity ? trustedIdentity.identity_binding_model : "unbound"
  };
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const reportPath = args[0] || path.join(__dirname, 'demo_reports', 'high_quality_clean_pr66.json');
  const proofPath = args[1] || path.join(__dirname, 'demo_reports', 'high_quality_clean_pr66.proof.json');
  const expectedSigner = args[2] || null;
  const identityConfig = args[3] || null;

  console.log(`[Verify] Verifying report ${reportPath} against proof ${proofPath}...`);
  const result = verifyProof(reportPath, proofPath, expectedSigner, identityConfig);
  if (result.valid) {
    console.log('[Verify] SUCCESS: Proof is cryptographically valid, untampered, and authorized.');
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.error('[Verify] FAILED:', result.reason);
    process.exit(1);
  }
}

module.exports = { verifyProof };
