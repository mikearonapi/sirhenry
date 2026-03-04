"""
Symmetric encryption for sensitive values stored at rest.

Two encryption contexts:
1. Plaid tokens — uses PLAID_ENCRYPTION_KEY (existing)
2. Data fields (names, SSNs, employers, etc.) — uses DATA_ENCRYPTION_KEY
   (falls back to PLAID_ENCRYPTION_KEY if not set separately)

Both use Fernet (AES-128-CBC + HMAC-SHA256) via the cryptography library.

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Plaid token encryption (existing)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Field-level data encryption (new)
# ---------------------------------------------------------------------------
_DATA_KEY = os.getenv("DATA_ENCRYPTION_KEY", "") or os.getenv("PLAID_ENCRYPTION_KEY", "")
_data_fernet = None


def _get_data_fernet():
    """Get Fernet instance for field-level data encryption."""
    global _data_fernet
    if _data_fernet is not None:
        return _data_fernet
    if not _DATA_KEY:
        return None
    from cryptography.fernet import Fernet
    try:
        _data_fernet = Fernet(_DATA_KEY.encode() if isinstance(_DATA_KEY, str) else _DATA_KEY)
    except Exception:
        logger.warning("DATA_ENCRYPTION_KEY is set but not a valid Fernet key")
        return None
    return _data_fernet


def encrypt_field(plaintext: Optional[str]) -> Optional[str]:
    """Encrypt a data field. Returns None if input is None."""
    if plaintext is None:
        return None
    f = _get_data_fernet()
    if f is None:
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_field(ciphertext: Optional[str]) -> Optional[str]:
    """Decrypt a data field. Falls back gracefully for unencrypted values."""
    if ciphertext is None:
        return None
    f = _get_data_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        # Plaintext from before encryption was enabled — return as-is
        return ciphertext
