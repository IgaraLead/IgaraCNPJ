"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ─── Auth ───────────────────────────────────────────────

class UsuarioCreate(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    telefone: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    senha: str


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: EmailStr
    role: str
    ativo: bool
    criado_em: Optional[datetime] = None

    class Config:
        from_attributes = True


class UsuarioMeOut(BaseModel):
    id: int
    nome: str
    email: EmailStr
    role: str
    ativo: bool
    saldo_creditos: int = 0
    plano: Optional[str] = None
    status_assinatura: Optional[str] = None

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    senha_atual: str
    nova_senha: str


# ─── Credits ────────────────────────────────────────────

class CreditoOut(BaseModel):
    usuario_id: int
    saldo: int
    creditos_recebidos: int
    creditos_consumidos: int

    class Config:
        from_attributes = True


class CreditoTransacaoOut(BaseModel):
    id: int
    usuario_id: int
    tipo: str
    quantidade: int
    motivo: Optional[str] = None
    metadata_extra: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ─── Plans / Subscriptions ──────────────────────────────

class PlanoOut(BaseModel):
    id: str
    name: str
    price: float
    credits: int
    credit_price: float
    max_accumulation: int = 100000


class AssinaturaCreate(BaseModel):
    plano: str  # basico, profissional, negocios, corporativo, enterprise


class AssinaturaOut(BaseModel):
    id: int
    usuario_id: int
    plano: str
    status: str
    data_inicio: Optional[datetime] = None
    data_proximo_ciclo: Optional[datetime] = None

    class Config:
        from_attributes = True


# ─── Search ─────────────────────────────────────────────

class SearchRequest(BaseModel):
    uf: str
    municipio: Optional[str] = None
    cnae: Optional[str] = None
    situacao: Optional[str] = None
    porte: Optional[str] = None
    q: Optional[str] = None
    page: int = 1
    limit: int = 50


class SearchResult(BaseModel):
    cnpj_basico: str
    cnpj_ordem: Optional[str] = None
    cnpj_dv: Optional[str] = None
    razao_social: Optional[str] = None
    nome_fantasia: Optional[str] = None
    situacao_cadastral: Optional[str] = None
    uf: str
    municipio: Optional[str] = None
    cnae_fiscal_principal: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    page: int
    limit: int
    credits_consumed: int
    task_id: Optional[str] = None


# ─── Export ──────────────────────────────────────────────

class ExportRequest(BaseModel):
    uf: str
    municipio: Optional[str] = None
    cnae: Optional[str] = None
    situacao: Optional[str] = None
    porte: Optional[str] = None
    q: Optional[str] = None
    formato: str = "csv"  # csv or xlsx


class ExportStatusOut(BaseModel):
    task_id: str
    status: str  # processing, ready, failed
    download_url: Optional[str] = None


# ─── Admin ───────────────────────────────────────────────

class AjusteCreditos(BaseModel):
    quantidade: int
    motivo: str


class ToggleUF(BaseModel):
    uf: str
    ativo: bool


class ToggleQueue(BaseModel):
    ativado: bool


class LogAcaoOut(BaseModel):
    id: int
    usuario_id: Optional[int] = None
    acao: str
    detalhes: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StatsOut(BaseModel):
    usuarios_ativos: int
    total_consultas: int
    creditos_consumidos_total: int
    fila_tamanho: int
