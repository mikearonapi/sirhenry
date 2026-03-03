"""Tests for the encryption utility (Fernet-based token encryption)."""
import os
import pytest


class TestEncryptionWithKey:
    """Test encrypt/decrypt with a real Fernet key."""

    @pytest.fixture(autouse=True)
    def _setup_encryption_key(self, monkeypatch):
        """Generate a real Fernet key and reload the encryption module."""
        from cryptography.fernet import Fernet

        self.test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("PLAID_ENCRYPTION_KEY", self.test_key)

        # Force reload of the module to pick up the new env var
        import pipeline.db.encryption as enc_mod

        monkeypatch.setattr(enc_mod, "_KEY", self.test_key)
        monkeypatch.setattr(enc_mod, "_fernet", None)  # Reset cached Fernet
        self.enc = enc_mod

    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "access-sandbox-abc123-test-token"
        encrypted = self.enc.encrypt_token(plaintext)
        assert encrypted != plaintext  # Should be encrypted
        decrypted = self.enc.decrypt_token(encrypted)
        assert decrypted == plaintext

    def test_encrypted_value_is_different_each_time(self):
        plaintext = "test-token"
        enc1 = self.enc.encrypt_token(plaintext)
        enc2 = self.enc.encrypt_token(plaintext)
        # Fernet uses random IV so each encryption produces different output
        assert enc1 != enc2

    def test_decrypt_different_key_returns_ciphertext(self):
        plaintext = "sensitive-token"
        encrypted = self.enc.encrypt_token(plaintext)

        # Swap to a different key
        from cryptography.fernet import Fernet

        new_key = Fernet.generate_key().decode()
        self.enc._KEY = new_key
        self.enc._fernet = None  # Reset cached Fernet
        # Force new Fernet with different key
        self.enc._fernet = Fernet(new_key.encode())

        # Decryption with wrong key should fall back to returning ciphertext
        result = self.enc.decrypt_token(encrypted)
        assert result == encrypted  # Returns the raw ciphertext

    def test_empty_string_roundtrip(self):
        encrypted = self.enc.encrypt_token("")
        decrypted = self.enc.decrypt_token(encrypted)
        assert decrypted == ""

    def test_long_token_roundtrip(self):
        long_token = "a" * 1000
        encrypted = self.enc.encrypt_token(long_token)
        decrypted = self.enc.decrypt_token(encrypted)
        assert decrypted == long_token


class TestEncryptionWithoutKey:
    """Test behavior when no encryption key is set."""

    @pytest.fixture(autouse=True)
    def _clear_encryption_key(self, monkeypatch):
        """Ensure no encryption key is set."""
        monkeypatch.delenv("PLAID_ENCRYPTION_KEY", raising=False)

        import pipeline.db.encryption as enc_mod

        monkeypatch.setattr(enc_mod, "_KEY", "")
        monkeypatch.setattr(enc_mod, "_fernet", None)
        self.enc = enc_mod

    def test_encrypt_returns_plaintext_when_no_key(self):
        plaintext = "access-sandbox-abc123"
        result = self.enc.encrypt_token(plaintext)
        assert result == plaintext

    def test_decrypt_returns_input_when_no_key(self):
        value = "some-token-value"
        result = self.enc.decrypt_token(value)
        assert result == value


class TestBackwardCompatibility:
    """Test handling of plaintext values stored before encryption was enabled."""

    @pytest.fixture(autouse=True)
    def _setup_key(self, monkeypatch):
        from cryptography.fernet import Fernet

        self.test_key = Fernet.generate_key().decode()
        monkeypatch.setenv("PLAID_ENCRYPTION_KEY", self.test_key)

        import pipeline.db.encryption as enc_mod

        monkeypatch.setattr(enc_mod, "_KEY", self.test_key)
        monkeypatch.setattr(enc_mod, "_fernet", None)
        self.enc = enc_mod

    def test_plaintext_token_returned_as_is(self):
        # A plaintext token stored before encryption was enabled
        plaintext = "access-sandbox-old-token-123"
        # decrypt_token should gracefully return the plaintext
        result = self.enc.decrypt_token(plaintext)
        assert result == plaintext

    def test_garbled_data_returned_as_is(self):
        garbled = "not-valid-fernet-ciphertext!!!"
        result = self.enc.decrypt_token(garbled)
        assert result == garbled
