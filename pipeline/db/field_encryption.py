"""
Transparent field-level encryption via SQLAlchemy ORM events.

Registers encrypt-on-write and decrypt-on-read hooks for sensitive columns.
Encryption uses Fernet (AES-128-CBC + HMAC-SHA256) via the DATA_ENCRYPTION_KEY
env var, falling back to PLAID_ENCRYPTION_KEY.

Usage:
    from pipeline.db.field_encryption import register_encryption_events
    register_encryption_events()  # call once at startup, before any DB operations
"""
import logging

from sqlalchemy import event

from pipeline.db.encryption import encrypt_field, decrypt_field

logger = logging.getLogger(__name__)

# Track whether events have been registered (prevent double-registration)
_registered = False

# Registry: Model class -> list of column names to encrypt/decrypt
# Only string fields — numeric fields are left plaintext (meaningless without identity context)
ENCRYPTED_FIELDS: dict[str, list[str]] = {
    "HouseholdProfile": [
        "spouse_a_name", "spouse_b_name",
        "spouse_a_employer", "spouse_b_employer",
        "other_income_sources_json", "dependents_json",
    ],
    "FamilyMember": [
        "name", "ssn_last4", "employer",
    ],
    "Document": [
        "raw_text",
    ],
    "TaxItem": [
        "payer_name", "payer_ein",
    ],
    "BusinessEntity": [
        "name", "ein",
    ],
    "BenefitPackage": [
        "employer_name",
    ],
    "InsurancePolicy": [
        "policy_number",
    ],
}

# Track which instances have already been decrypted (prevent double-decrypt)
_DECRYPTED_MARKER = "_field_encryption_decrypted"


def register_encryption_events() -> None:
    """Register SQLAlchemy event listeners for transparent field encryption.

    Must be called ONCE at startup, after models are imported but before
    any database operations.
    """
    global _registered
    if _registered:
        return
    _registered = True

    from pipeline.db.schema import (
        HouseholdProfile, FamilyMember, Document, TaxItem,
        BusinessEntity, BenefitPackage, InsurancePolicy,
    )

    model_map = {
        "HouseholdProfile": HouseholdProfile,
        "FamilyMember": FamilyMember,
        "Document": Document,
        "TaxItem": TaxItem,
        "BusinessEntity": BusinessEntity,
        "BenefitPackage": BenefitPackage,
        "InsurancePolicy": InsurancePolicy,
    }

    for model_name, field_names in ENCRYPTED_FIELDS.items():
        model_class = model_map.get(model_name)
        if model_class is None:
            logger.warning(f"Field encryption: model {model_name} not found, skipping")
            continue

        def make_encrypt_handler(fields):
            def encrypt_handler(mapper, connection, target):
                for col_name in fields:
                    val = getattr(target, col_name, None)
                    if val is not None and isinstance(val, str):
                        setattr(target, col_name, encrypt_field(val))
            return encrypt_handler

        def make_decrypt_handler(fields):
            def decrypt_handler(target, context):
                if getattr(target, _DECRYPTED_MARKER, False):
                    return
                for col_name in fields:
                    val = getattr(target, col_name, None)
                    if val is not None and isinstance(val, str):
                        setattr(target, col_name, decrypt_field(val))
                object.__setattr__(target, _DECRYPTED_MARKER, True)
            return decrypt_handler

        encrypt_handler = make_encrypt_handler(field_names)
        decrypt_handler = make_decrypt_handler(field_names)

        event.listen(model_class, "before_insert", encrypt_handler)
        event.listen(model_class, "before_update", encrypt_handler)
        event.listen(model_class, "load", decrypt_handler)

    logger.info(
        f"Field encryption registered for {len(ENCRYPTED_FIELDS)} models, "
        f"{sum(len(f) for f in ENCRYPTED_FIELDS.values())} fields"
    )
