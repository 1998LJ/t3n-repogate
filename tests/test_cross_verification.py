"""Cross-implementation and contract parity tests between Node and Python verifiers."""

import json
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from repogate.attestation import (
    load_canonical_identity,
    verify_proof_native,
    _verify_proof_with_node_reference,
    verify_proof_with_node,
)


class TestCrossImplementationContract(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent
        self.clean_report = self.repo_root / "demo_reports" / "high_quality_clean_pr66.json"
        self.clean_proof = self.repo_root / "demo_reports" / "high_quality_clean_pr66.proof.json"
        self.tampered_report = self.repo_root / "demo_reports" / "duplicate_dirty_pr_pr482.json"
        self.root_identity = self.repo_root / "agent_identity.json"

    def test_trust_anchor_packaged_resource_matches_root(self):
        """Verify that packaged agent_identity.json matches root agent_identity.json exactly."""
        root_data = json.loads(self.root_identity.read_text(encoding="utf-8"))
        packaged_data = load_canonical_identity()

        keys = (
            "agent_did",
            "authorized_signer_address",
            "identity_binding_model",
            "standard",
        )

        self.assertEqual(
            {k: root_data[k] for k in keys},
            {k: packaged_data[k] for k in keys},
        )

    def test_positive_vector_parity(self):
        """Verify that positive demo report succeeds on both Python and Node with identical fields."""
        py_res = verify_proof_native(self.clean_report, self.clean_proof)
        self.assertTrue(py_res.valid)
        self.assertTrue(py_res.hash_verified)

        node_code, node_out, _ = verify_proof_with_node(self.clean_report, self.clean_proof)
        self.assertEqual(node_code, 0)
        self.assertIn("SUCCESS", node_out)

        # Compare extracted payload
        self.assertEqual(
            py_res.signer_address.lower(),
            "0x64c8c36d03f7dec27553aff8d98d953d59b049fd".lower()
        )
        self.assertEqual(
            py_res.agent_did,
            "did:t3n:78131a400e1762aeac8d86e90b76449e02cf8169"
        )

    def test_tampered_report_parity(self):
        """Verify that tampered report fails on both Python and Node with expected hash mismatch."""
        py_res = verify_proof_native(self.tampered_report, self.clean_proof)
        self.assertFalse(py_res.valid)
        self.assertIn("REPORT HAS BEEN TAMPERED WITH", py_res.reason)

        node_code, _, node_err = verify_proof_with_node(self.tampered_report, self.clean_proof)
        self.assertEqual(node_code, 1)
        self.assertIn("REPORT HAS BEEN TAMPERED WITH", node_err)

    def test_wrong_signer_rejection(self):
        """Verify that proof with wrong claimed/authorized signer is rejected."""
        # Mutate proof with foreign signer
        raw_proof = json.loads(self.clean_proof.read_text(encoding="utf-8"))
        raw_proof["signer_address"] = "0x000000000000000000000000000000000000dead"

        temp_proof = self.repo_root / "demo_reports" / "_temp_wrong_signer.proof.json"
        try:
            temp_proof.write_text(json.dumps(raw_proof), encoding="utf-8")
            py_res = verify_proof_native(self.clean_report, temp_proof)
            self.assertFalse(py_res.valid)
            self.assertIn("Signer address mismatch", py_res.reason)
        finally:
            if temp_proof.exists():
                temp_proof.unlink()

    def test_untrusted_did_rejection(self):
        """Verify that proof with untrusted agent DID is rejected."""
        raw_proof = json.loads(self.clean_proof.read_text(encoding="utf-8"))
        raw_proof["agent_did"] = "did:t3n:attacker_unauthorized_did"

        temp_proof = self.repo_root / "demo_reports" / "_temp_untrusted_did.proof.json"
        try:
            temp_proof.write_text(json.dumps(raw_proof), encoding="utf-8")
            py_res = verify_proof_native(self.clean_report, temp_proof)
            self.assertFalse(py_res.valid)
            self.assertIn("UNTRUSTED AGENT DID", py_res.reason)
        finally:
            if temp_proof.exists():
                temp_proof.unlink()

    def test_cross_verification_comprehensive_negative_vectors(self):
        """Exhaustive negative vector parity: Node and Python must both fail."""
        clean_rep_path = self.clean_report
        clean_prf_path = self.clean_proof
        base_proof = json.loads(clean_prf_path.read_text(encoding="utf-8"))

        vectors = [
            ("signature_malformed", clean_rep_path.read_bytes(), {**base_proof, "signature": "0x1234deadbeef"}),
            ("hash_mismatch", clean_rep_path.read_bytes(), {**base_proof, "report_sha256": "0" * 64}),
            ("missing_signature", clean_rep_path.read_bytes(), {k: v for k, v in base_proof.items() if k != "signature"}),
            ("missing_did", clean_rep_path.read_bytes(), {k: v for k, v in base_proof.items() if k != "agent_did"}),
            ("invalid_json_proof", clean_rep_path.read_bytes(), "{not_valid_json"),
        ]

        import tempfile
        for name, rep_bytes, prf_data in vectors:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf_rep, \
                 tempfile.NamedTemporaryFile(suffix=".proof.json", delete=False) as tf_prf:
                tf_rep.write(rep_bytes)
                tf_rep.close()
                if isinstance(prf_data, dict):
                    tf_prf.write(json.dumps(prf_data).encode("utf-8"))
                else:
                    tf_prf.write(prf_data.encode("utf-8"))
                tf_prf.close()

                try:
                    py_res = verify_proof_native(tf_rep.name, tf_prf.name)
                    self.assertFalse(py_res.valid, f"Python should fail for {name}")

                    node_code, _, _ = _verify_proof_with_node_reference(tf_rep.name, tf_prf.name)
                    self.assertNotEqual(node_code, 0, f"Node should fail for {name}")
                finally:
                    Path(tf_rep.name).unlink(missing_ok=True)
                    Path(tf_prf.name).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
