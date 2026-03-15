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
    hub_id: Optional[str] = None
    hub_synced_at: Optional[datetime] = None

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
    natureza_juridica: Optional[str] = None
    cep: Optional[str] = None
    bairro: Optional[str] = None
    logradouro: Optional[str] = None
    matriz_filial: Optional[str] = None  # 1=Matriz, 2=Filial
    capital_social_min: Optional[float] = None
    capital_social_max: Optional[float] = None
    data_abertura_inicio: Optional[str] = None  # YYYYMMDD
    data_abertura_fim: Optional[str] = None
    ddd: Optional[str] = None
    com_email: Optional[bool] = None
    com_telefone: Optional[bool] = None
    simples: Optional[str] = None  # S, N
    mei: Optional[str] = None  # S, N
    q: Optional[str] = None
    page: int = 1
    limit: int = 50
    search_id: Optional[str] = None  # Pass existing search_id to reuse session (pagination)


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
    bairro: Optional[str] = None
    logradouro: Optional[str] = None
    numero: Optional[str] = None
    complemento: Optional[str] = None
    cep: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None
    capital_social: Optional[float] = None
    natureza_juridica: Optional[int] = None
    porte_empresa: Optional[int] = None
    data_inicio_atividade: Optional[str] = None
    identificador_matriz_filial: Optional[int] = None
    municipio_nome: Optional[str] = None
    socios: Optional[str] = None


class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    page: int
    limit: int
    credits_consumed: int
    task_id: Optional[str] = None
    search_id: Optional[str] = None


# ─── Export ──────────────────────────────────────────────

class ExportRequest(BaseModel):
    uf: str
    municipio: Optional[str] = None
    cnae: Optional[str] = None
    situacao: Optional[str] = None
    porte: Optional[str] = None
    natureza_juridica: Optional[str] = None
    cep: Optional[str] = None
    bairro: Optional[str] = None
    logradouro: Optional[str] = None
    matriz_filial: Optional[str] = None
    capital_social_min: Optional[float] = None
    capital_social_max: Optional[float] = None
    data_abertura_inicio: Optional[str] = None
    data_abertura_fim: Optional[str] = None
    ddd: Optional[str] = None
    com_email: Optional[bool] = None
    com_telefone: Optional[bool] = None
    simples: Optional[str] = None
    mei: Optional[str] = None
    q: Optional[str] = None
    formato: str = "csv"  # csv or xlsx


class ExportStatusOut(BaseModel):
    task_id: str
    status: str  # processing, ready, failed
    download_url: Optional[str] = None


# ─── History ─────────────────────────────────────────────

class HistoricoBuscaOut(BaseModel):
    id: int
    search_id: str
    params: dict
    total_results: int
    status: str
    credits_consumed: int
    file_id: Optional[str] = None
    quantidade_processada: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


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


# ─── Admin: user management ─────────────────────────────

class AdminCreateUser(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    role: str = "user"  # user, admin, super_admin
    telefone: Optional[str] = None


class AdminChangeRole(BaseModel):
    role: str  # user, admin


class AdminSetSubscription(BaseModel):
    plano: str  # basico, profissional, negocios, corporativo, enterprise
    permanente: bool = False  # True = sem validade
    dias_validade: Optional[int] = None  # only when permanente=False
    creditos: Optional[int] = None  # optional: grant credits too


class CnaeItem(BaseModel):
    codigo: str
    descricao: str
