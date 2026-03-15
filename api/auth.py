"""
Authentication module — Hub SSO only.
Users authenticate via Hub, which issues JWTs validated via JWKS.
The Entity frontend redirects to Hub login; Hub tokens are exchanged
for local httpOnly cookies for seamless API calls.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from .database import get_db
from .models import Usuario, Credito, Assinatura
from .hub_auth import decode_hub_token, _fetch_jwks, HUB_JWKS_URL

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# ── Password hashing (passlib + bcrypt) ─────────────────────

from passlib.context import CryptContext

_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if hashed == "!":
        return False
    return _pwd_ctx.verify(plain, hashed)

# Local session tokens (issued after Hub token exchange)
SESSION_SECRET = os.environ.get("ENTITY_SESSION_SECRET", "")
if not SESSION_SECRET:
    import warnings
    warnings.warn(
        "ENTITY_SESSION_SECRET not set — using insecure random secret (DO NOT use in production)",
        stacklevel=2,
    )
    import secrets as _secrets
    SESSION_SECRET = _secrets.token_urlsafe(64)
SESSION_EXPIRE_HOURS = int(os.getenv("ENTITY_SESSION_EXPIRE_HOURS", "12"))
ALGORITHM = "HS256"

HUB_LOGIN_URL = os.getenv("HUB_LOGIN_URL", "")


def _create_session_token(user_id: int) -> str:
    """Create a local session token after Hub authentication."""
    expire = datetime.now(timezone.utc) + timedelta(hours=SESSION_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": str(user_id), "exp": expire, "type": "entity_session"},
        SESSION_SECRET,
        algorithm=ALGORITHM,
    )


def _set_session_cookie(response: Response, token: str):
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="lax",
        max_age=SESSION_EXPIRE_HOURS * 3600,
    )


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """
    Extract user from session cookie (local token) or Authorization header (Hub JWT).
    Hub JWT takes priority if both are present.
    """
    # Try Hub JWT from Authorization header first
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer ") and HUB_JWKS_URL:
        token = auth_header[7:]
        try:
            payload = decode_hub_token(token)
            hub_user_id = payload.get("user_id")
            if hub_user_id:
                user = db.query(Usuario).filter(Usuario.hub_id == hub_user_id).first()
                if not user:
                    user = _provision_user_from_hub(payload, db)
                if user and user.ativo:
                    return user
        except HTTPException:
            pass

    # Fall back to local session cookie
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado. Faça login via Hub.")
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "entity_session":
            raise HTTPException(status_code=401, detail="Token inválido")
        user_id = int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Sessão expirada. Faça login novamente via Hub.")

    user = db.query(Usuario).filter(Usuario.id == user_id, Usuario.ativo == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado ou inativo")
    return user


def _provision_user_from_hub(payload: dict, db: Session) -> Usuario:
    """Create a local user from Hub JWT claims."""
    hub_user_id = payload.get("user_id")
    email = payload.get("email", f"{hub_user_id}@hub.igaralead.com.br")
    name = payload.get("name", email.split("@")[0])

    # Check if user exists by email
    user = db.query(Usuario).filter(Usuario.email == email).first()
    if user:
        user.hub_id = hub_user_id
        user.hub_synced_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
        return user

    user = Usuario(
        nome=name,
        email=email,
        senha_hash="!",  # impossible-to-match sentinel — login is Hub-only
        role="user",
        ativo=True,
        hub_id=hub_user_id,
        hub_synced_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.flush()

    credito = Credito(usuario_id=user.id, saldo=0)
    db.add(credito)
    db.commit()
    db.refresh(user)
    return user


def require_super_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user


class LoginRequest(BaseModel):
    email: str
    senha: str

class RegisterRequest(BaseModel):
    nome: str
    email: str
    senha: str
    telefone: Optional[str] = None


@router.post("/login")
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Direct email/password login. Sets a session cookie."""
    email = body.email.strip().lower()
    senha = body.senha
    if not email or not senha:
        raise HTTPException(status_code=422, detail="Email e senha são obrigatórios")

    user = db.query(Usuario).filter(Usuario.email == email, Usuario.ativo == True).first()
    if not user or not verify_password(senha, user.senha_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")

    session_token = _create_session_token(user.id)
    _set_session_cookie(response, session_token)
    return {"message": "Login realizado", "user_id": user.id}


@router.post("/register")
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    """Self-service registration with email/password."""
    nome = body.nome.strip()
    email = body.email.strip().lower()
    senha = body.senha
    telefone = (body.telefone or "").strip() or None

    if not nome or not email or len(senha) < 6:
        raise HTTPException(status_code=422, detail="Nome, email e senha (min 6 chars) são obrigatórios")

    existing = db.query(Usuario).filter(Usuario.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email já cadastrado")

    user = Usuario(
        nome=nome,
        email=email,
        senha_hash=hash_password(senha),
        telefone=telefone,
        role="user",
        ativo=True,
    )
    db.add(user)
    db.flush()

    credito = Credito(usuario_id=user.id, saldo=0)
    db.add(credito)
    db.commit()
    db.refresh(user)

    session_token = _create_session_token(user.id)
    _set_session_cookie(response, session_token)
    return {"message": "Conta criada", "user_id": user.id}


@router.post("/hub-exchange")
def hub_token_exchange(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    Exchange a Hub JWT for a local Entity session cookie.
    Called by the Entity frontend after Hub login redirect.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token Hub ausente")

    hub_token = auth_header[7:]
    payload = decode_hub_token(hub_token)

    hub_user_id = payload.get("user_id")
    if not hub_user_id:
        raise HTTPException(status_code=401, detail="Token Hub incompleto")

    # Find or create local user
    user = db.query(Usuario).filter(Usuario.hub_id == hub_user_id).first()
    if not user:
        user = _provision_user_from_hub(payload, db)
    if not user or not user.ativo:
        raise HTTPException(status_code=403, detail="Conta desativada")

    # Sync roles from Hub (bidirectional — set from Hub claims unconditionally)
    hub_roles = payload.get("roles", [])
    if "super_admin" in hub_roles:
        user.role = "super_admin"
    elif "admin" in hub_roles:
        user.role = "admin"
    else:
        user.role = "user"
    user.hub_synced_at = datetime.now(timezone.utc)
    db.commit()

    session_token = _create_session_token(user.id)
    _set_session_cookie(response, session_token)

    return {"message": "Sessão criada", "user_id": user.id}


@router.post("/oauth-exchange")
def oauth_code_exchange(request: Request, response: Response, db: Session = Depends(get_db)):
    """
    BFF endpoint: receives an OAuth authorization code from the frontend,
    exchanges it for tokens server-side (keeping client_secret on the backend),
    then creates a local session cookie.
    """
    import httpx as _httpx

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        import asyncio
        body = asyncio.get_event_loop().run_until_complete(request.json())
    else:
        raise HTTPException(status_code=400, detail="Content-Type must be application/json")

    code = body.get("code", "").strip()
    redirect_uri = body.get("redirect_uri", "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Código de autorização ausente")

    hub_url = os.getenv("HUB_URL", "http://localhost:8001")
    client_id = os.getenv("ENTITY_OAUTH_CLIENT_ID", "entity")
    client_secret = os.getenv("ENTITY_OAUTH_CLIENT_SECRET", "")
    if not client_secret:
        raise HTTPException(status_code=500, detail="OAuth client secret não configurado")

    # Exchange code for tokens at Hub (server-to-server, secret never leaves backend)
    try:
        resp = _httpx.post(
            f"{hub_url}/oauth/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            timeout=15,
        )
    except Exception:
        raise HTTPException(status_code=502, detail="Falha na comunicação com o Hub")

    if resp.status_code != 200:
        logger.warning("Hub token exchange failed: %d %s", resp.status_code, resp.text[:200])
        raise HTTPException(status_code=401, detail="Falha ao trocar código por token")

    tokens = resp.json()
    hub_token = tokens.get("access_token", "")
    if not hub_token:
        raise HTTPException(status_code=502, detail="Token de acesso não retornado pelo Hub")

    # Validate the Hub JWT and create local session
    payload = decode_hub_token(hub_token)

    hub_user_id = payload.get("user_id")
    if not hub_user_id:
        raise HTTPException(status_code=401, detail="Token Hub incompleto")

    user = db.query(Usuario).filter(Usuario.hub_id == hub_user_id).first()
    if not user:
        user = _provision_user_from_hub(payload, db)
    if not user or not user.ativo:
        raise HTTPException(status_code=403, detail="Conta desativada")

    # Sync roles from Hub (bidirectional — set from Hub claims unconditionally)
    hub_roles = payload.get("roles", [])
    if "super_admin" in hub_roles:
        user.role = "super_admin"
    elif "admin" in hub_roles:
        user.role = "admin"
    else:
        user.role = "user"
    user.hub_synced_at = datetime.now(timezone.utc)
    db.commit()

    session_token = _create_session_token(user.id)
    _set_session_cookie(response, session_token)

    return {"message": "Sessão criada", "user_id": user.id}

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logout realizado"}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Refresh session cookie if the current one is still valid."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="No session")
    try:
        payload = jwt.decode(token, SESSION_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "entity_session":
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Session expired")

    user = db.query(Usuario).filter(Usuario.id == user_id, Usuario.ativo == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    new_token = _create_session_token(user.id)
    _set_session_cookie(response, new_token)
    return {"message": "Sessão renovada"}


@router.get("/me")
def me(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return current user info including credits and subscription."""
    credito = db.query(Credito).filter(Credito.usuario_id == current_user.id).first()
    saldo = credito.saldo if credito else 0

    assinatura = db.query(Assinatura).filter(
        Assinatura.usuario_id == current_user.id,
        Assinatura.status == "ativa",
    ).first()

    return {
        "id": current_user.id,
        "nome": current_user.nome,
        "email": current_user.email,
        "role": current_user.role,
        "ativo": current_user.ativo,
        "saldo_creditos": saldo,
        "plano": assinatura.plano if assinatura else None,
        "status_assinatura": assinatura.status if assinatura else None,
        "hub_login_url": HUB_LOGIN_URL,
    }


@router.get("/login-url")
def get_login_url():
    """Return the Hub login URL for frontend redirect."""
    if not HUB_LOGIN_URL:
        raise HTTPException(status_code=503, detail="Login URL do Hub não configurada")
    return {"login_url": HUB_LOGIN_URL}
