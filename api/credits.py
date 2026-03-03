"""
Credit management: balance queries, deduction, and transaction history.
"""

import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user
from .models import Usuario, Credito, CreditoTransacao, Assinatura
from .schemas import CreditoOut, CreditoTransacaoOut

router = APIRouter(prefix="/credits", tags=["credits"])


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
