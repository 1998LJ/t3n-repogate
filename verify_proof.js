const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { getOrCreateSignerKey } = require('./t3n_auth');

function verifyProof(reportPath, proofPath, privateKeyHex) {
  if (!fs.existsSync(reportPath)) throw new Error(`Report not found: ${reportPath}`);
  if (!fs.existsSync(proofPath)) throw new Error(`Proof not found: ${proofPath}`);

  const rawReport = fs.readFileSync(reportPath, 'utf8');
  const proof = JSON.parse(fs.readFileSync(proofPath, 'utf8'));

  const expectedHash = crypto.createHash('sha256').update(rawReport, 'utf8').digest('hex');
  if (expectedHash !== proof.report_sha256) {
    return {
      valid: false,
      reason: `Report hash mismatch! Expected ${expectedHash}, proof has ${proof.report_sha256}. REPORT HAS BEEN TAMPERED WITH.`
    };
  }

  const hmac = crypto.createHmac('sha256', Buffer.from(privateKeyHex.slice(2), 'hex'));
  hmac.update(expectedHash);
  const expectedSig = hmac.digest('hex');

  if (expectedSig !== proof.signature) {
    return {
      valid: false,
      reason: `Signature mismatch! Report was signed by a different key or corrupted.`
    };
  }

  return {
    valid: true,
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
  const privateKey = getOrCreateSignerKey();

  console.log(`[Verify] Verifying report ${reportPath} against proof ${proofPath}...`);
  const result = verifyProof(reportPath, proofPath, privateKey);
  if (result.valid) {
    console.log('[Verify] SUCCESS: Proof is cryptographically valid and report is untampered.');
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.error('[Verify] FAILED:', result.reason);
    process.exit(1);
  }
}

module.exports = { verifyProof };
