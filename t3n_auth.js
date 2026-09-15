const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// P0-2: Deterministic, persistent signer key for T3N DID persistence
function getOrCreateSignerKey() {
  if (process.env.T3N_SIGNER_PRIVATE_KEY) {
    let key = process.env.T3N_SIGNER_PRIVATE_KEY.trim();
    if (!key.startsWith('0x')) key = '0x' + key;
    return key;
  }
  const secretPath = path.join(__dirname, '.t3n_signer.secret');
  if (fs.existsSync(secretPath)) {
    const raw = fs.readFileSync(secretPath, 'utf8').trim();
    if (raw.length === 64 || raw.length === 66) {
      return raw.startsWith('0x') ? raw : '0x' + raw;
    }
  }
  const generated = '0x' + crypto.randomBytes(32).toString('hex');
  fs.writeFileSync(secretPath, generated, { mode: 0o600 });
  return generated;
}

// P0-3: Sign & Attest PR evaluation report
function attestReport(reportJsonStr, privateKeyHex, didString) {
  const hash = crypto.createHash('sha256').update(reportJsonStr, 'utf8').digest('hex');
  const hmac = crypto.createHmac('sha256', Buffer.from(privateKeyHex.slice(2), 'hex'));
  hmac.update(hash);
  const signature = hmac.digest('hex');
  
  return {
    report_sha256: hash,
    agent_did: didString,
    attestation_type: "t3n_hmac_sha256_attestation",
    signature: signature,
    attested_at: new Date().toISOString(),
    verification_standard: "T3N-REPOGATE-v1-CANONICAL"
  };
}

async function main() {
  const sdk = await import('@terminal3/t3n-sdk');
  const { T3nClient, loadWasmComponent, fetchTrustedManifest, metamask_sign, eth_get_address, createEthAuthInput } = sdk;

  console.log('[T3N] Loading cryptographic components and WASM...');
  const wasmComponent = await loadWasmComponent();

  console.log('[T3N] Fetching trusted manifest for sandbox...');
  const manifest = await fetchTrustedManifest('sandbox');

  const privateKey = getOrCreateSignerKey();
  const address = eth_get_address(privateKey);
  console.log(`[T3N] Derived persistent Ethereum signer address: ${address}`);

  console.log('[T3N] Initializing T3N client with pinned trust anchor...');
  const client = new T3nClient({
    trustAnchor: manifest,
    wasmComponent,
    environment: 'sandbox',
    handlers: {
      EthSign: metamask_sign(address, undefined, privateKey)
    }
  });

  console.log('[T3N] Performing cryptographic handshake with sandbox node...');
  await client.handshake();
  console.log('[T3N] Handshake established.');

  console.log('[T3N] Authenticating DID...');
  const authInput = createEthAuthInput(address);
  const didObj = await client.authenticate(authInput);
  const did = didObj.value || didObj.toString();
  console.log(`[T3N] Successfully authenticated persistent DID: ${did}`);

  // Test report attestation on demo reports if present
  const demoReportPath = path.join(__dirname, 'demo_reports', 'high_quality_clean_pr66.json');
  if (fs.existsSync(demoReportPath)) {
    const rawReport = fs.readFileSync(demoReportPath, 'utf8');
    const proof = attestReport(rawReport, privateKey, did);
    const proofPath = path.join(__dirname, 'demo_reports', 'high_quality_clean_pr66.proof.json');
    fs.writeFileSync(proofPath, JSON.stringify(proof, null, 2));
    console.log(`[T3N] Cryptographically signed demo report -> ${proofPath}`);
  }

  return { did, address };
}

if (require.main === module) {
  main().catch(err => {
    console.error('[T3N Error]:', err.message || err);
    process.exit(1);
  });
}

module.exports = { getOrCreateSignerKey, attestReport, main };
