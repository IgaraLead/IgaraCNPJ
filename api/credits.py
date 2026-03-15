"""
Credit management: balance queries, deduction, transaction history, and Hub provisioning.
"""

import datetime
import os
from typing import List

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user
from .models import Usuario, Credito, CreditoTransacao, Assinatura
from .schemas import CreditoOut, CreditoTransacaoOut

router = APIRouter(prefix="/credits", tags=["credits"])

LIMITE_CREDITOS_MAXIMO = int(os.getenv("LIMITE_CREDITOS_MAXIMO", "100000"))
HUB_SERVICE_API_KEY = os.getenv("HUB_SERVICE_API_KEY", "")

PLAN_CREDITS = {
    "basico": 1000,
    "profissional": 2400,
    "negocios": 6000,
    "corporativo": 16500,
    "enterprise": 50000,
}


def _verify_service_key(x_api_key: str = Header(alias="X-Api-Key", default="")):
    if not HUB_SERVICE_API_KEY or not x_api_key:
        raise HTTPException(status_code=401, detail="API key ausente")
    if x_api_key != HUB_SERVICE_API_KEY:
        raise HTTPException(status_code=401, detail="API key inválida")


def check_active_subscription(db: Session, user_id: int) -> Assinatura:
    """Verify user has an active subscription. Raise 403 otherwise."""
    assinatura = db.query(Assinatura).filter(
        Assinatura.usuario_id == user_id,
        Assinatura.status == "ativa",
    ).first()
    if not assinatura:
        raise HTTPException(status_code=403, detail="Assinatura inativa. Créditos inacessíveis.")
    return assinatura


def debit_credits(db: Session, user_id: int, amount: int, motivo: str) -> int:
    """
    Debit credits from user account. Returns credits actually consumed.
    Raises HTTPException if insufficient credits.
    """
    credito = db.query(Credito).filter(Credito.usuario_id == user_id).with_for_update().first()
    if not credito or credito.saldo < amount:
        raise HTTPException(status_code=402, detail=f"Créditos insuficientes. Necessário: {amount}, disponível: {credito.saldo if credito else 0}")

    credito.saldo -= amount
    credito.creditos_consumidos += amount
    credito.updated_at = datetime.datetime.utcnow()

    transacao = CreditoTransacao(
        usuario_id=user_id,
        tipo="consumo",
        quantidade=-amount,
        motivo=motivo,
    )
    db.add(transacao)
    return amount


@router.get("/me", response_model=CreditoOut)
def get_my_credits(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Get current user's credit balance."""
    credito = db.query(Credito).filter(Credito.usuario_id == current_user.id).first()
    if not credito:
        raise HTTPException(status_code=404, detail="Registro de créditos não encontrado")
    return credito


@router.get("/me/transactions", response_model=List[CreditoTransacaoOut])
def get_my_transactions(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Get current user's credit transaction history."""
    transactions = (
        db.query(CreditoTransacao)
        .filter(CreditoTransacao.usuario_id == current_user.id)
        .order_by(CreditoTransacao.created_at.desc())
        .limit(100)
        .all()
    )
    return transactions


# ─── Hub Provisioning ──────────────────────────────


class ProvisionRequest(BaseModel):
    client_slug: str
    tier: str
    credits: int


@router.post("/provision", dependencies=[Depends(_verify_service_key)])
def provision_credits(data: ProvisionRequest, db: Session = Depends(get_db)):
    """
    Called by Hub when a subscription with Entity is activated or renewed.
    Creates/updates subscription and grants credits to all org users.
    """
    if data.tier not in PLAN_CREDITS:
        raise HTTPException(status_code=422, detail=f"Tier inválido: {data.tier}")

    # Find all users that belong to this organization (identified by hub tokens)
    # For now, provision to all users with hub_id set (org scoping via Hub)
    # In the future, we can add org_id to Usuario
    users = db.query(Usuario).filter(
        Usuario.hub_id.isnot(None),
        Usuario.ativo == True,
    ).all()

    provisioned = []
    for user in users:
        # Create or update subscription
        assinatura = db.query(Assinatura).filter(
            Assinatura.usuario_id == user.id,
            Assinatura.status == "ativa",
        ).first()

        if not assinatura:
            assinatura = Assinatura(
                usuario_id=user.id,
                plano=data.tier,
                status="ativa",
                manual=True,
            )
            db.add(assinatura)
        else:
            assinatura.plano = data.tier
            assinatura.atualizado_em = datetime.datetime.now(datetime.timezone.utc)

        # Grant credits (respecting max limit)
        credito = db.query(Credito).filter(Credito.usuario_id == user.id).with_for_update().first()
        if not credito:
            credito = Credito(usuario_id=user.id, saldo=0)
            db.add(credito)
            db.flush()

        new_saldo = min(credito.saldo + data.credits, LIMITE_CREDITOS_MAXIMO)
        added = new_saldo - credito.saldo
        if added > 0:
            credito.saldo = new_saldo
            credito.creditos_recebidos += added
            credito.updated_at = datetime.datetime.now(datetime.timezone.utc)

            transacao = CreditoTransacao(
                usuario_id=user.id,
                tipo="provisionamento_hub",
                quantidade=added,
                motivo=f"Provisionamento Hub: tier={data.tier}, slug={data.client_slug}",
            )
            db.add(transacao)

        provisioned.append({"user_id": user.id, "credits_added": added})

    db.commit()
    return {"provisioned": provisioned, "tier": data.tier, "total_users": len(provisioned)}
