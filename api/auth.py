"""
Authentication module with JWT tokens stored in httpOnly cookies.
Implements register, login, refresh, logout, and user profile endpoints.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import JWTError, jwt

from .database import get_db
from .models import Usuario, Credito
from .schemas import UsuarioCreate, UsuarioOut, LoginRequest, UsuarioMeOut, ChangePasswordRequest

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "chave_super_secreta")
REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY", "outra_chave")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7"))
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Usuario:
    """Extract and validate user from access_token cookie."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Não autenticado")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Token inválido")
        sub = payload.get("sub")
        if sub is None:
            raise HTTPException(status_code=401, detail="Token inválido")
        user_id = int(sub)
    except JWTError:
        raise HTTPException(status_code=401, detail="Token expirado ou inválido")

    user = db.query(Usuario).filter(Usuario.id == user_id, Usuario.ativo == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado ou inativo")
    return user


def require_super_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """Dependency that requires super_admin role."""
    if current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a super-admin")
    return current_user


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set httpOnly cookies with tokens."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=os.getenv("ENVIRONMENT", "development") == "production",
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    )


@router.post("/register", response_model=UsuarioOut, status_code=201)
def register(user: UsuarioCreate, response: Response, db: Session = Depends(get_db)):
    """Create a new user account with free plan."""
    if db.query(Usuario).filter(Usuario.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    db_user = Usuario(
        nome=user.nome,
        email=user.email,
        senha_hash=hash_password(user.senha),
        telefone=user.telefone,
        role="user",
        ativo=True,
    )
    db.add(db_user)
    db.flush()

    # Create credit record with 0 balance (free plan)
    credito = Credito(usuario_id=db_user.id, saldo=0)
    db.add(credito)
    db.commit()
    db.refresh(db_user)

    # Auto-login after registration
    access_token = create_access_token({"sub": str(db_user.id)})
    refresh_token = create_refresh_token({"sub": str(db_user.id)})
    _set_auth_cookies(response, access_token, refresh_token)

    return db_user


@router.post("/login")
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    """Authenticate user and set JWT cookies."""
    user = db.query(Usuario).filter(Usuario.email == data.email).first()
    if not user or not verify_password(data.senha, user.senha_hash):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    if not user.ativo:
        raise HTTPException(status_code=403, detail="Conta desativada")

    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})
    _set_auth_cookies(response, access_token, refresh_token)

    return {"message": "Login realizado com sucesso", "user_id": user.id}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Refresh access token using refresh_token cookie."""
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token ausente")
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Token inválido")
        user_id = int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Refresh token expirado ou inválido")

    user = db.query(Usuario).filter(Usuario.id == user_id, Usuario.ativo == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Usuário não encontrado")

    new_access = create_access_token({"sub": str(user.id)})
    new_refresh = create_refresh_token({"sub": str(user.id)})
    _set_auth_cookies(response, new_access, new_refresh)

    return {"message": "Tokens renovados"}


@router.post("/logout")
def logout(response: Response):
    """Clear authentication cookies."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logout realizado"}


@router.get("/me", response_model=UsuarioMeOut)
def me(current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)):
    """Return current user info including credits and subscription."""
    credito = db.query(Credito).filter(Credito.usuario_id == current_user.id).first()
    saldo = credito.saldo if credito else 0

    from .models import Assinatura
    assinatura = db.query(Assinatura).filter(
        Assinatura.usuario_id == current_user.id,
        Assinatura.status == "ativa",
    ).first()

    return UsuarioMeOut(
        id=current_user.id,
        nome=current_user.nome,
        email=current_user.email,
        role=current_user.role,
        ativo=current_user.ativo,
        saldo_creditos=saldo,
        plano=assinatura.plano if assinatura else None,
        status_assinatura=assinatura.status if assinatura else None,
    )


@router.post("/change-password")
def change_password(
    request_data: "ChangePasswordRequest",
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change password for the authenticated user."""
    if not request_data.senha_atual or not request_data.nova_senha:
        raise HTTPException(status_code=400, detail="Senha atual e nova senha são obrigatórias")

    if len(request_data.nova_senha) < 8:
        raise HTTPException(status_code=400, detail="Nova senha deve ter no mínimo 8 caracteres")

    if not verify_password(request_data.senha_atual, current_user.senha_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    current_user.senha_hash = hash_password(request_data.nova_senha)
    db.commit()

    return {"message": "Senha alterada com sucesso"}
