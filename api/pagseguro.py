"""
PagSeguro webhook integration for subscription payments.
Receives payment notifications and updates subscriptions/credits.
"""

import os
import logging
import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import Usuario, Assinatura, Credito, CreditoTransacao, LogAcao

router = APIRouter(tags=["pagseguro"])

logger = logging.getLogger(__name__)

PAGSEGURO_TOKEN = os.getenv("PAGSEGURO_TOKEN", "")
LIMITE_CREDITOS_MAXIMO = int(os.getenv("LIMITE_CREDITOS_MAXIMO", "100000"))

PLAN_CREDITS = {
    "basico": 1000,
    "profissional": 2400,
    "negocios": 6000,
    "corporativo": 16500,
    "enterprise": 50000,
}


def _verify_webhook_signature(payload: bytes, signature: str) -> bool:
    """Verify PagSeguro webhook signature for security."""
    if not PAGSEGURO_TOKEN:
        logger.error("PAGSEGURO_TOKEN not set — rejecting webhook for security")
        return False
    expected = hmac.new(PAGSEGURO_TOKEN.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhooks/pagseguro")
async def pagseguro_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Receive PagSeguro payment notifications.
    Updates subscription status and adds monthly credits.
    """
    body = await request.body()
    signature = request.headers.get("x-pagseguro-signature", "")

    # Verify webhook authenticity
    if not _verify_webhook_signature(body, signature):
        logger.warning("PagSeguro webhook signature verification failed")
        raise HTTPException(status_code=403, detail="Assinatura inválida")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload inválido")

    event_type = payload.get("event_type", "")
    reference = payload.get("reference", {})
    subscription_id = reference.get("id", "") if isinstance(reference, dict) else str(reference)

    logger.info(f"PagSeguro webhook: event={event_type}, subscription={subscription_id}")

    if event_type == "subscription.paid":
        # Monthly payment received — add credits
        assinatura = db.query(Assinatura).filter(
            Assinatura.pagseguro_subscription_id == subscription_id,
        ).first()

        if not assinatura:
            logger.warning(f"Assinatura não encontrada: {subscription_id}")
            return {"status": "ignored", "reason": "subscription not found"}

        if assinatura.status != "ativa":
            assinatura.status = "ativa"

        # Update next billing cycle
        assinatura.data_proximo_ciclo = datetime.now(timezone.utc) + timedelta(days=30)

        # Add monthly credits
        credits_to_add = PLAN_CREDITS.get(assinatura.plano, 0)
        if credits_to_add > 0:
            credito = db.query(Credito).filter(
                Credito.usuario_id == assinatura.usuario_id,
            ).first()

            if credito:
                actual_add = min(credits_to_add, LIMITE_CREDITOS_MAXIMO - credito.saldo)
                if actual_add > 0:
                    credito.saldo += actual_add
                    credito.creditos_recebidos += actual_add

                    transacao = CreditoTransacao(
                        usuario_id=assinatura.usuario_id,
                        tipo="recebimento_mensal",
                        quantidade=actual_add,
                        motivo=f"Pagamento mensal - plano {assinatura.plano}",
                        metadata_extra={"subscription_id": subscription_id},
                    )
                    db.add(transacao)

        db.commit()
        return {"status": "ok", "action": "credits_added"}

    elif event_type in ("subscription.cancelled", "subscription.suspended"):
        assinatura = db.query(Assinatura).filter(
            Assinatura.pagseguro_subscription_id == subscription_id,
        ).first()

        if assinatura:
            assinatura.status = "cancelada" if "cancelled" in event_type else "suspensa"
            log = LogAcao(
                acao=f"pagseguro_{event_type}",
                detalhes={"subscription_id": subscription_id},
            )
            db.add(log)
            db.commit()

        return {"status": "ok", "action": "subscription_updated"}

    return {"status": "ok", "action": "no_action"}
