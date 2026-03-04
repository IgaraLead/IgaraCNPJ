"""
SQLAlchemy ORM models for the CNPJ platform.
"""

import datetime
from datetime import timezone
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Text, Float,
    ForeignKey, BigInteger,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from .database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    telefone = Column(String(20), nullable=True)
    role = Column(String(20), default="user")  # user, super_admin
    ativo = Column(Boolean, default=True)
    criado_em = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))

    credito = relationship("Credito", back_populates="usuario", uselist=False)
    assinaturas = relationship("Assinatura", back_populates="usuario", order_by="Assinatura.criado_em.desc()")
    transacoes = relationship("CreditoTransacao", back_populates="usuario")
    logs = relationship("LogAcao", back_populates="usuario")


class Credito(Base):
    __tablename__ = "creditos"

    usuario_id = Column(Integer, ForeignKey("usuarios.id"), primary_key=True)
    saldo = Column(Integer, nullable=False, default=0)
    creditos_recebidos = Column(Integer, default=0)
    creditos_consumidos = Column(Integer, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), onupdate=lambda: datetime.datetime.now(timezone.utc))

    usuario = relationship("Usuario", back_populates="credito")


class CreditoTransacao(Base):
    __tablename__ = "creditos_transacoes"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    tipo = Column(String(30))  # recebimento_mensal, consumo, estorno, ajuste_manual
    quantidade = Column(Integer)
    motivo = Column(Text)
    metadata_extra = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))

    usuario = relationship("Usuario", back_populates="transacoes")


class Assinatura(Base):
    __tablename__ = "assinaturas"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    plano = Column(String(30), nullable=False)  # basico, profissional, negocios, corporativo, enterprise
    status = Column(String(20), default="ativa")  # ativa, cancelada, suspensa
    pagseguro_subscription_id = Column(String(100), nullable=True)
    manual = Column(Boolean, default=False)  # True if set by admin
    data_inicio = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    data_validade = Column(DateTime, nullable=True)  # null = permanente
    data_proximo_ciclo = Column(DateTime, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))
    atualizado_em = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), onupdate=lambda: datetime.datetime.now(timezone.utc))

    usuario = relationship("Usuario", back_populates="assinaturas")


class LogAcao(Base):
    __tablename__ = "logs_acoes"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    acao = Column(String(100), nullable=False)
    detalhes = Column(JSONB, nullable=True)
    ip_address = Column(String(45), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))

    usuario = relationship("Usuario", back_populates="logs")


class HistoricoBusca(Base):
    __tablename__ = "historico_buscas"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    search_id = Column(String(36), unique=True, nullable=False, index=True)
    params = Column(JSONB, nullable=False)
    total_results = Column(Integer, default=0)
    status = Column(String(30), default="realizada")  # realizada, processada, exportada
    credits_consumed = Column(Integer, default=0)
    file_id = Column(String(36), nullable=True)  # id for downloadable processed files
    quantidade_processada = Column(Integer, nullable=True)  # how many contacts were processed
    created_at = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc))

    usuario = relationship("Usuario")


class ConfigSistema(Base):
    __tablename__ = "config_sistema"

    chave = Column(String(100), primary_key=True)
    valor = Column(Text, nullable=False)
    atualizado_em = Column(DateTime, default=lambda: datetime.datetime.now(timezone.utc), onupdate=lambda: datetime.datetime.now(timezone.utc))
