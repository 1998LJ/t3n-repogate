const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { ethers } = require('ethers');

// P0-1 & P0-2: Strict ECDSA public-key verification
function verifyProof(reportPath, proofPath, expectedSignerAddress) {
  if (!fs.existsSync(reportPath)) throw new Error(`Report not found: ${reportPath}`);
  if (!fs.existsSync(proofPath)) throw new Error(`Proof not found: ${proofPath}`);

  const rawReport = fs.readFileSync(reportPath, 'utf8');
  const proof = JSON.parse(fs.readFileSync(proofPath, 'utf8'));

  const expectedHash = crypto.createHash('sha256').update(rawReport, 'utf8').digest('hex');

  // 1. Check report hash
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

  // Check address match with proof record
  if (proof.signer_address && recoveredAddress.toLowerCase() !== proof.signer_address.toLowerCase()) {
    return {
      valid: false,
      reason: `Signer address mismatch! Proof claims ${proof.signer_address}, but recovered ${recoveredAddress}.`
    };
  }

  // Check against expected signer address (if provided for strict identity pinning)
  if (expectedSignerAddress && recoveredAddress.toLowerCase() !== expectedSignerAddress.toLowerCase()) {
    return {
      valid: false,
      reason: `Signer authority mismatch! Expected authorized signer ${expectedSignerAddress}, but got ${recoveredAddress}.`
    };
  }

  return {
    valid: true,
    hash_verified: true,
    signer_address: recoveredAddress,
    agent_did: proof.agent_did,
    report_sha256: proof.report_sha256,
    attested_at: proof.attested_at,
    standard: proof.verification_standard
  };
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const reportPath = args[0] || path.join(__dirname, 'demo_reports', 'high_quality_clean_pr66.json');
  const proofPath = args[1] || path.join(__dirname, 'demo_reports', 'high_quality_clean_pr66.proof.json');
  const expectedSigner = args[2] || null;

  console.log(`[Verify] Verifying report ${reportPath} against proof ${proofPath}...`);
  const result = verifyProof(reportPath, proofPath, expectedSigner);
  if (result.valid) {
    console.log('[Verify] SUCCESS: Proof is cryptographically valid and report is untampered.');
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.error('[Verify] FAILED:', result.reason);
    process.exit(1);
  }
}

module.exports = { verifyProof };
