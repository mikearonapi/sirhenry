"""
Supabase JWT validation for FastAPI.

Validates Bearer tokens from the frontend against Supabase's JWT secret.
Supports offline operation via cached JWKS keys.
"""
import logging
import os
import time

import httpx
import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

security = HTTPBearer(auto_error=False)

# Cache JWKS for 1 hour
_jwks_cache: dict = {"keys": [], "fetched_at": 0.0}


async def _get_jwks() -> list:
    """Fetch and cache Supabase JWKS public keys."""
    if time.time() - _jwks_cache["fetched_at"] < 3600 and _jwks_cache["keys"]:
        return _jwks_cache["keys"]
    if not SUPABASE_URL:
        return []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json",
                timeout=5.0,
            )
            resp.raise_for_status()
            _jwks_cache["keys"] = resp.json().get("keys", [])
            _jwks_cache["fetched_at"] = time.time()
    except Exception as e:
        logger.warning(f"Failed to fetch JWKS: {e}")
    return _jwks_cache["keys"]


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict | None:
    """
    Validate JWT and return user payload.

    Returns None when:
    - Demo mode is active (no auth required)
    - No SUPABASE_JWT_SECRET configured (dev mode — auth disabled)
    """
    # Demo mode: no auth required
    from api.database import get_active_mode
    if get_active_mode() == "demo":
        return None

    # Dev mode: no Supabase configured, skip auth
    if not SUPABASE_JWT_SECRET and not SUPABASE_URL:
        return None

    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = credentials.credentials
    try:
        # Primary: validate with JWT secret (HS256, no network call needed)
        if SUPABASE_JWT_SECRET:
            payload = jwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            # Fallback: validate with JWKS public keys
            jwks = await _get_jwks()
            if not jwks:
                raise HTTPException(
                    status_code=503,
                    detail="Auth service unavailable",
                )
            header = jwt.get_unverified_header(token)
            key_data = next(
                (k for k in jwks if k.get("kid") == header.get("kid")),
                None,
            )
            if not key_data:
                raise HTTPException(status_code=401, detail="Invalid token key")
            public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience="authenticated",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except StopIteration:
        raise HTTPException(status_code=401, detail="Invalid token key")
