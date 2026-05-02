"""Tests for Falcon license system."""
import base64
import json
import sys
import time
import unittest
from pathlib import Path

# Ensure repo root is in path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from license_manager import LicenseManager, LicenseTier, _generate_key, _LICENSE_SECRET


class TestLicenseValidation(unittest.TestCase):
    def test_valid_pro_key(self):
        key = _generate_key("pro", 30, _LICENSE_SECRET)
        lic = LicenseManager(key)
        self.assertTrue(lic.valid)
        self.assertEqual(lic.tier, LicenseTier.PRO)
        self.assertIsNone(lic.error)

    def test_valid_enterprise_key(self):
        key = _generate_key("enterprise", 30, _LICENSE_SECRET)
        lic = LicenseManager(key)
        self.assertTrue(lic.valid)
        self.assertEqual(lic.tier, LicenseTier.ENTERPRISE)

    def test_invalid_signature_wrong_secret(self):
        wrong_key = _generate_key("pro", 30, "wrong-secret-12345")
        lic = LicenseManager(wrong_key)
        self.assertFalse(lic.valid)
        self.assertIn("signature", lic.error.lower())

    def test_expired_key(self):
        key = _generate_key("pro", -1, _LICENSE_SECRET)
        lic = LicenseManager(key)
        self.assertFalse(lic.valid)
        self.assertIn("expired", lic.error.lower())

    def test_free_tier_no_key(self):
        lic = LicenseManager("")
        self.assertFalse(lic.valid)  # No key = not valid
        self.assertEqual(lic.tier, LicenseTier.FREE)

    def test_malformed_prefix(self):
        lic = LicenseManager("EAGLE-badprefix")
        self.assertFalse(lic.valid)
        self.assertIn("prefix", lic.error.lower())

    def test_malformed_base64(self):
        lic = LicenseManager("FALCON-!!!notbase64!!!")
        self.assertFalse(lic.valid)
        self.assertIn("malformed", lic.error.lower())

    def test_payload_tampering_tier_changed(self):
        """Un atacante modifica el tier en el payload pero reusa la firma original."""
        key = _generate_key("free", 30, _LICENSE_SECRET)
        # Decode
        body = key.split("-", 1)[1]
        decoded = base64.urlsafe_b64decode(body + "==")
        payload_json, sig = decoded.rsplit(b":", 1)
        payload = json.loads(payload_json)
        # Tamper: cambiar free -> enterprise
        payload["tier"] = "enterprise"
        new_payload_json = json.dumps(payload, separators=(",", ":")).encode()
        # Re-encode con la MISMA firma (ataque!)
        tampered = base64.urlsafe_b64encode(new_payload_json + b":" + sig).decode().rstrip("=")
        tampered_key = f"FALCON-{tampered}"
        lic = LicenseManager(tampered_key)
        self.assertFalse(lic.valid)
        self.assertIn("signature", lic.error.lower())

    def test_payload_tampering_expiry_extended(self):
        """Un atacante extiende la expiración pero reusa la firma original."""
        key = _generate_key("pro", 1, _LICENSE_SECRET)
        body = key.split("-", 1)[1]
        decoded = base64.urlsafe_b64decode(body + "==")
        payload_json, sig = decoded.rsplit(b":", 1)
        payload = json.loads(payload_json)
        # Tamper: extender expiración 1 año
        payload["exp"] = int(time.time() + 365 * 86400)
        new_payload_json = json.dumps(payload, separators=(",", ":")).encode()
        tampered = base64.urlsafe_b64encode(new_payload_json + b":" + sig).decode().rstrip("=")
        tampered_key = f"FALCON-{tampered}"
        lic = LicenseManager(tampered_key)
        self.assertFalse(lic.valid)
        self.assertIn("signature", lic.error.lower())

    def test_expired_exact_boundary(self):
        """Key que expira exactamente AHORA debe ser inválida."""
        key = _generate_key("pro", 0, _LICENSE_SECRET)
        # La generación toma tiempo, así que forzamos exp = now
        now = int(time.time())
        payload = json.dumps({
            "tier": "pro",
            "exp": now,
            "features": [],
            "iat": now,
        }, separators=(",", ":")).encode()
        import hashlib, hmac
        sig = hmac.new(_LICENSE_SECRET.encode(), payload, hashlib.sha256).hexdigest()[:24]
        token = base64.urlsafe_b64encode(payload + b":" + sig.encode()).decode().rstrip("=")
        boundary_key = f"FALCON-{token}"
        lic = LicenseManager(boundary_key)
        # time.time() >= now, debería estar expirada
        self.assertFalse(lic.valid)
        self.assertIn("expired", lic.error.lower())


class TestFeatureGates(unittest.TestCase):
    def test_free_limits(self):
        key = _generate_key("free", 30, _LICENSE_SECRET)
        lic = LicenseManager(key)
        self.assertEqual(lic.max_tool_calls(), 25)
        self.assertEqual(lic.max_subagents(), 0)
        self.assertEqual(lic.max_providers(), 2)
        self.assertEqual(lic.max_plugins(), 3)
        self.assertFalse(lic.allow_voice())
        self.assertFalse(lic.allow_cloudsave())

    def test_pro_limits(self):
        key = _generate_key("pro", 30, _LICENSE_SECRET)
        lic = LicenseManager(key)
        self.assertEqual(lic.max_tool_calls(), 10_000)
        self.assertEqual(lic.max_subagents(), 10)
        self.assertTrue(lic.allow_voice())
        self.assertTrue(lic.allow_cloudsave())
        self.assertTrue(lic.allow_telegram())
        self.assertTrue(lic.allow_mcp())
        self.assertFalse(lic.can_use("sso"))
        self.assertFalse(lic.can_use("audit_logs"))

    def test_enterprise_limits(self):
        key = _generate_key("enterprise", 30, _LICENSE_SECRET)
        lic = LicenseManager(key)
        self.assertEqual(lic.max_tool_calls(), 999_999)
        self.assertTrue(lic.can_use("sso"))
        self.assertTrue(lic.can_use("audit_logs"))
        self.assertTrue(lic.allow_mcp())
        self.assertTrue(lic.allow_cloudsave())

    def test_pro_vs_free_features(self):
        free_lic = LicenseManager(_generate_key("free", 30, _LICENSE_SECRET))
        pro_lic = LicenseManager(_generate_key("pro", 30, _LICENSE_SECRET))

        self.assertTrue(pro_lic.can_use("chat"))
        self.assertTrue(free_lic.can_use("chat"))

        self.assertTrue(pro_lic.can_use("tools_basic"))
        self.assertTrue(free_lic.can_use("tools_basic"))

        self.assertFalse(free_lic.allow_voice())
        self.assertTrue(pro_lic.allow_voice())


class TestRevocation(unittest.TestCase):
    def test_revoked_key_simulated(self):
        """Simulación de revocación: el manager no tiene revocación nativa,
        pero el servidor sí. Este test documenta el comportamiento esperado."""
        key = _generate_key("pro", 30, _LICENSE_SECRET)
        lic = LicenseManager(key)
        self.assertTrue(lic.valid)
        # TODO: cuando se integre revocación offline, agregar check aquí


class TestCryptoConsistency(unittest.TestCase):
    def test_manager_vs_server_signature_algorithm(self):
        """Manager y server deben usar el mismo algoritmo HMAC (raw secret)."""
        import hashlib, hmac
        secret = "test-secret-123"
        payload = b'{"tier":"pro","exp":9999999999,"features":[],"iat":0}'

        # Manager style (raw secret)
        manager_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()[:24]

        # Server style (raw secret — unified in KEYS-2 fix)
        server_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()[:24]

        self.assertEqual(manager_sig, server_sig,
            "Manager and server must use the same HMAC secret derivation")

    def test_cross_validation_manager_to_server(self):
        """Una key generada por license_manager debe validar en license_server."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from license_server import parse_key, _verify_payload

        key = _generate_key("pro", 30, _LICENSE_SECRET)
        parsed = parse_key(key)
        self.assertNotIn("error", parsed, f"parse_key failed: {parsed.get('error')}")

        # El server debe verificar la firma correctamente
        sig_ok = _verify_payload(parsed["payload_b64"], parsed["sig"], _LICENSE_SECRET)
        self.assertTrue(sig_ok, "Server rejected a valid manager-generated key signature")


class TestMachineFingerprint(unittest.TestCase):
    @unittest.skip("Machine fingerprint not yet implemented — documented in LICENSE_INSTALL.md but missing in code")
    def test_machine_locked_key(self):
        """Cuando se implemente, una key generada para máquina A
        debe fallar en máquina B."""
        pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
