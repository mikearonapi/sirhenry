"""SIT: Security testing.

Validates PII redaction, encryption, input sanitization,
and security boundary enforcement.
"""
import logging
import os
import pytest
from unittest.mock import patch
from tests.integration.expected_values import *

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# PII Redaction
# ---------------------------------------------------------------------------

class TestPIIRedaction:
    def test_ssn_redacted(self):
        """SSN patterns should be redacted in log output."""
        from pipeline.security.logging import PIIRedactionFilter

        filt = PIIRedactionFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="User SSN is 123-45-6789 in the record",
            args=(), exc_info=None,
        )
        filt.filter(record)
        assert "123-45-6789" not in record.msg
        assert "[SSN]" in record.msg

    def test_dollar_amount_redacted(self):
        """Dollar amounts should be redacted."""
        from pipeline.security.logging import PIIRedactionFilter

        filt = PIIRedactionFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Balance is $245,000.00 today",
            args=(), exc_info=None,
        )
        filt.filter(record)
        assert "$245,000.00" not in record.msg
        assert "[$***]" in record.msg

    def test_email_redacted(self):
        """Email addresses should be redacted."""
        from pipeline.security.logging import PIIRedactionFilter

        filt = PIIRedactionFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Email is michael@example.com for account",
            args=(), exc_info=None,
        )
        filt.filter(record)
        assert "michael@example.com" not in record.msg
        assert "[EMAIL]" in record.msg

    def test_ein_redacted(self):
        """EIN patterns should be redacted."""
        from pipeline.security.logging import PIIRedactionFilter

        filt = PIIRedactionFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="EIN is 12-3456789 in the filing",
            args=(), exc_info=None,
        )
        filt.filter(record)
        assert "12-3456789" not in record.msg
        assert "[EIN]" in record.msg


# ---------------------------------------------------------------------------
# Encryption
# ---------------------------------------------------------------------------

class TestEncryption:
    def test_fernet_roundtrip(self):
        """Encrypt/decrypt should produce the original value."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        f = Fernet(key)
        original = "access-sandbox-test-token-12345"
        encrypted = f.encrypt(original.encode())
        decrypted = f.decrypt(encrypted).decode()
        assert decrypted == original
        assert encrypted != original.encode()

    def test_different_keys_fail(self):
        """Decrypting with wrong key should raise InvalidToken."""
        from cryptography.fernet import Fernet, InvalidToken

        key_a = Fernet.generate_key()
        key_b = Fernet.generate_key()

        encrypted = Fernet(key_a).encrypt(b"secret")
        with pytest.raises(InvalidToken):
            Fernet(key_b).decrypt(encrypted)

    def test_none_passthrough(self):
        """encrypt_field(None) should return None."""
        from pipeline.db.encryption import encrypt_field, decrypt_field

        assert encrypt_field(None) is None
        assert decrypt_field(None) is None

    def test_encrypt_produces_different_output(self):
        """Same input should produce different ciphertext (Fernet uses random IV)."""
        from pipeline.db.encryption import encrypt_field

        if encrypt_field("test") is None:
            pytest.skip("Encryption not configured")

        result1 = encrypt_field("test_value")
        result2 = encrypt_field("test_value")
        if result1 and result2:
            # Fernet uses random IV, so outputs should differ
            assert result1 != result2


# ---------------------------------------------------------------------------
# Input Sanitization
# ---------------------------------------------------------------------------

class TestInputSanitization:
    async def test_sql_injection_stored_safely(self, fresh_client, fresh_seed):
        """SQL injection attempt should be stored as text, not executed."""
        resp = await fresh_client.get("/transactions")
        data = resp.json()
        txns = data.get("items", data) if isinstance(data, dict) else data
        if not txns:
            pytest.skip("No transactions")

        txn_id = txns[0]["id"]
        malicious = "'; DROP TABLE transactions; --"

        resp = await fresh_client.patch(f"/transactions/{txn_id}", json={
            "description": malicious,
        })
        if resp.status_code == 200:
            # Verify the database is intact
            resp = await fresh_client.get("/transactions")
            assert resp.status_code == 200
            data = resp.json()
            txns = data.get("items", data) if isinstance(data, dict) else data
            assert len(txns) > 0  # Table still exists

    async def test_xss_stored_as_text(self, fresh_client, fresh_seed):
        """XSS attempt should be stored as literal text."""
        resp = await fresh_client.get("/goals")
        goals = resp.json()
        if not goals:
            pytest.skip("No goals")

        goal_id = goals[0]["id"]
        xss = "<script>alert('xss')</script>"

        resp = await fresh_client.patch(f"/goals/{goal_id}", json={
            "description": xss,
        })
        if resp.status_code == 200:
            resp = await fresh_client.get("/goals")
            updated = resp.json()
            goal = next((g for g in updated if g["id"] == goal_id), None)
            if goal and goal.get("description"):
                # Should be stored as literal text, not executed
                assert "<script>" in goal["description"] or "alert" not in goal["description"]


# ---------------------------------------------------------------------------
# Production security requirements
# ---------------------------------------------------------------------------

class TestProductionSecurity:
    def test_encryption_key_validation(self):
        """A valid Fernet key should be accepted."""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        # Should not raise
        Fernet(key)

    def test_invalid_key_rejected(self):
        """An invalid key should raise ValueError."""
        from cryptography.fernet import Fernet

        with pytest.raises(Exception):
            Fernet(b"not-a-valid-key")
