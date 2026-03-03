"""
Symmetric encryption for sensitive values stored at rest (e.g. Plaid access tokens).
Uses Fernet (AES-128-CBC + HMAC-SHA256) via the cryptography library.

Set PLAID_ENCRYPTION_KEY env var to a Fernet key. Generate one with:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import logging
import os

logger = logging.getLogger(__name__)

_KEY = os.getenv("PLAID_ENCRYPTION_KEY", "")
_fernet = None


def _get_fernet():
    global _fernet
    if _fernet is not None:
        return _fernet
    if not _KEY:
        logger.warning(
            "PLAID_ENCRYPTION_KEY not set — tokens will be stored in plaintext. "
            "Generate a key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        return None
    from cryptography.fernet import Fernet
    _fernet = Fernet(_KEY.encode() if isinstance(_KEY, str) else _KEY)
    return _fernet


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token. Falls back to plaintext if no key is configured."""
    f = _get_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a token. Falls back to returning the raw value if no key or decryption fails."""
    f = _get_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Likely a plaintext value stored before encryption was enabled
        return ciphertext
