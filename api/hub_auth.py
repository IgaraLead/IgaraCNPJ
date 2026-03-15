"""
Hub JWT validation middleware for Entity.
Validates JWTs issued by IgaraHub via JWKS, extracts client_slug,
and ensures URL-based client isolation.
"""

import os
import logging
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, Path, Request
from jose import JWTError, jwt, jwk
from sqlalchemy.orm import Session

from .database import get_db
from .models import Usuario

logger = logging.getLogger(__name__)

HUB_JWKS_URL = os.getenv("HUB_JWKS_URL", "")
HUB_ISSUER = os.getenv("HUB_ISSUER", "igarahub")
HUB_AUDIENCE = os.getenv("HUB_AUDIENCE", "igaralead")

# In-memory JWKS cache (refreshed on miss or after TTL)
_jwks_cache: dict = {}
_jwks_cache_time: float = 0
_JWKS_CACHE_TTL = 300  # 5 minutes


def _fetch_jwks() -> dict:
    """Fetch JWKS from Hub and cache it."""
    global _jwks_cache, _jwks_cache_time
    if not HUB_JWKS_URL:
        return {}
    try:
        resp = httpx.get(HUB_JWKS_URL, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        _jwks_cache = {k["kid"]: k for k in data.get("keys", [])}
        _jwks_cache_time = __import__("time").time()
        return _jwks_cache
    except Exception as e:
        logger.warning("Failed to fetch JWKS from Hub: %s", e)
        return _jwks_cache


def _get_signing_key(token: str) -> Optional[dict]:
    """Extract kid from token header and look up in JWKS."""
    import time as _time
    headers = jwt.get_unverified_headers(token)
    kid = headers.get("kid")
    if not kid:
        return None
    # Refresh cache if expired
    if _time.time() - _jwks_cache_time > _JWKS_CACHE_TTL:
        _fetch_jwks()
    key = _jwks_cache.get(kid)
    if not key:
        _fetch_jwks()
        key = _jwks_cache.get(kid)
    return key


def decode_hub_token(token: str) -> dict:
    """Decode and validate a Hub-issued JWT."""
    signing_key = _get_signing_key(token)
    if not signing_key:
        raise HTTPException(status_code=401, detail="Chave de assinatura Hub não encontrada")
    try:
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            audience=HUB_AUDIENCE,
            issuer=HUB_ISSUER,
        )
    except JWTError as e:
        logger.warning("Hub JWT validation failed: %s", e)
        raise HTTPException(status_code=401, detail="Token Hub inválido") from e


def get_hub_user(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """
    Extract Hub JWT from Authorization header, validate, and return local user.
    Falls back to looking up by hub_id. Creates a stub user if not found.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token Hub ausente")

    token = auth_header[7:]
    payload = decode_hub_token(token)

    hub_user_id = payload.get("user_id")
    client_slug = payload.get("client_slug")

    if not hub_user_id or not client_slug:
        raise HTTPException(status_code=401, detail="Token Hub incompleto")

    # Find local user by hub_id
    user = db.query(Usuario).filter(Usuario.hub_id == hub_user_id).first()
    if not user:
        # Auto-provision local user from Hub claims
        user = Usuario(
            nome=payload.get("name", payload.get("email", "Hub User")),
            email=payload.get("email", f"{hub_user_id}@hub.igaralead.com.br"),
            senha_hash="!",  # impossible-to-match sentinel — login is Hub-only
            role="user",
            ativo=True,
            hub_id=hub_user_id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user


def validate_entity_client_slug(
    cliente: str = Path(description="Client slug from URL"),
    request: Request = None,
) -> str:
    """
    Validates that {cliente} in the URL matches the client_slug in the Hub token.
    Use as a dependency on /c/{cliente}/... routes.
    """
    auth_header = request.headers.get("Authorization", "") if request else ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        try:
            # Try Hub token first
            payload = decode_hub_token(token)
            token_slug = payload.get("client_slug")
            if token_slug != cliente:
                raise HTTPException(status_code=403, detail="client_slug da URL não corresponde ao token")
            return cliente
        except HTTPException:
            raise
        except Exception:
            pass

    raise HTTPException(status_code=403, detail="Validação de client_slug falhou")
