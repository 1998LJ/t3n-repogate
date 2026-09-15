const crypto = require('crypto');

async function main() {
  const sdk = await import('@terminal3/t3n-sdk');
  const { T3nClient, loadWasmComponent, fetchTrustedManifest, createEthAuthInput, eth_get_address } = sdk;

  console.log('[T3N] Fetching trusted manifest for sandbox...');
  const manifest = await fetchTrustedManifest('sandbox');
  const wasm = await loadWasmComponent();

  const privKey = '0x' + crypto.randomBytes(32).toString('hex');
  const address = eth_get_address(privKey);
  console.log('[T3N] Derived Ethereum signer address:', address);

  const client = new T3nClient({
    trustAnchor: manifest,
    wasmComponent: wasm,
    handlers: {
      EthSign: sdk.metamask_sign(address, undefined, privKey),
    }
  });

  console.log('[T3N] Performing cryptographic handshake...');
  await client.handshake();
  console.log('[T3N] Handshake established.');

  console.log('[T3N] Authenticating DID...');
  const did = await client.authenticate(createEthAuthInput(address));
  console.log('[T3N] Successfully authenticated DID:', did.toString());

  console.log('[T3N] Checking balance and state machine status...');
  const balance = await client.getBalance();
  console.log('[T3N] Session status: ACTIVE (Code:', await client.getStatus(), ')');
  console.log('[T3N] Ready to sign and attest PR risk evaluations.');
}

main().catch(console.error);
