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
# Helpers
# ---------------------------------------------------------------------------
_PLAID_ENV = os.getenv("PLAID_ENV", "sandbox").lower()
_IS_PRODUCTION = _PLAID_ENV == "production"

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
        if _IS_PRODUCTION:
            raise RuntimeError(
                "PLAID_ENCRYPTION_KEY is required in production. "
                "Generate one: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        logger.warning(
            "PLAID_ENCRYPTION_KEY not set — tokens will be stored in plaintext. "
            "Generate a key: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
        return None
    from cryptography.fernet import Fernet
    _fernet = Fernet(_KEY.encode() if isinstance(_KEY, str) else _KEY)
    return _fernet


def encrypt_token(plaintext: str) -> str:
    """Encrypt a Plaid token. Raises in production if no key is configured."""
    f = _get_fernet()
    if f is None:
        # Dev/sandbox only — production raises in _get_fernet()
        logger.warning("Storing Plaid token WITHOUT encryption (dev mode)")
        return plaintext
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a Plaid token. Raises on failure instead of silently returning ciphertext."""
    f = _get_fernet()
    if f is None:
        # Dev/sandbox — assume plaintext
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        logger.error(
            "Failed to decrypt Plaid token — possible key mismatch or data corruption: %s",
            e,
        )
        if _IS_PRODUCTION:
            raise ValueError("Failed to decrypt Plaid token") from e
        # Dev fallback: may be plaintext from before encryption was enabled
        logger.warning("Returning raw value as fallback (dev mode)")
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
    """Decrypt a data field. Falls back gracefully for unencrypted values in dev mode."""
    if ciphertext is None:
        return None
    f = _get_data_fernet()
    if f is None:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception as e:
        if _IS_PRODUCTION:
            logger.error("Failed to decrypt field data: %s", e)
            raise ValueError("Failed to decrypt field data") from e
        # Dev: plaintext from before encryption was enabled — return as-is
        return ciphertext
