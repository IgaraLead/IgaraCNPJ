"""
Plans and subscription management.
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user
from .models import Usuario, Assinatura, Credito, CreditoTransacao, LogAcao
from .schemas import PlanoOut, AssinaturaCreate, AssinaturaOut

router = APIRouter(tags=["plans"])

logger = logging.getLogger(__name__)

LIMITE_CREDITOS_MAXIMO = int(os.getenv("LIMITE_CREDITOS_MAXIMO", "100000"))

PLANS = {
    "basico": PlanoOut(id="basico", name="Básico", price=30, credits=1000, credit_price=0.03),
    "profissional": PlanoOut(id="profissional", name="Profissional", price=60, credits=2400, credit_price=0.025),
    "negocios": PlanoOut(id="negocios", name="Negócios", price=120, credits=6000, credit_price=0.02),
    "corporativo": PlanoOut(id="corporativo", name="Corporativo", price=250, credits=16500, credit_price=0.01515),
    "enterprise": PlanoOut(id="enterprise", name="Enterprise", price=500, credits=50000, credit_price=0.01),
}


@router.get("/plans", response_model=List[PlanoOut])
def get_plans():
    """List all available subscription plans."""
    return list(PLANS.values())


PAGSEGURO_EMAIL = os.getenv("PAGSEGURO_EMAIL", "")
PAGSEGURO_TOKEN = os.getenv("PAGSEGURO_TOKEN", "")
PAGSEGURO_API_URL = os.getenv(
    "PAGSEGURO_API_URL",
    "https://ws.pagseguro.uol.com.br/v2/pre-approvals/request",
)


@router.post("/subscription/create")
def create_subscription(
    data: AssinaturaCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Create a new subscription for the current user.
    Returns a PagSeguro checkout URL — credits are only added upon payment confirmation via webhook.
    """
    if data.plano not in PLANS:
        raise HTTPException(status_code=400, detail="Plano inválido")

    existing = db.query(Assinatura).filter(
        Assinatura.usuario_id == current_user.id,
        Assinatura.status == "ativa",
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Já existe uma assinatura ativa. Cancele antes de trocar.")

    plan = PLANS[data.plano]
    now = datetime.now(timezone.utc)

    # Create subscription with status "pendente" — will become "ativa" only after payment
    assinatura = Assinatura(
        usuario_id=current_user.id,
        plano=data.plano,
        status="pendente",
        data_inicio=now,
    )
    db.add(assinatura)
    db.flush()  # get assinatura.id

    # Ensure credit row exists (but do NOT add credits yet)
    credito = db.query(Credito).filter(Credito.usuario_id == current_user.id).first()
    if not credito:
        credito = Credito(usuario_id=current_user.id, saldo=0)
        db.add(credito)

    log = LogAcao(
        usuario_id=current_user.id,
        acao="assinatura_criada",
        detalhes={"plano": data.plano, "assinatura_id": assinatura.id},
    )
    db.add(log)
    db.commit()
    db.refresh(assinatura)

    # Build PagSeguro checkout URL via server-to-server call.
    # In production, POST to PagSeguro pre-approvals API and get a checkout code.
    # The token is NEVER exposed to the client.
    import requests as http_requests
    checkout_url = ""
    try:
        ps_response = http_requests.post(
            PAGSEGURO_API_URL,
            params={"email": PAGSEGURO_EMAIL, "token": PAGSEGURO_TOKEN},
            headers={"Content-Type": "application/xml; charset=UTF-8"},
            data=f'<preApprovalRequest><reference>sub_{assinatura.id}</reference>'
                 f'<preApproval><name>Plano {data.plano}</name>'
                 f'<charge>AUTO</charge><period>MONTHLY</period>'
                 f'<amountPerPayment>{plan.price:.2f}</amountPerPayment>'
                 f'</preApproval></preApprovalRequest>',
            timeout=15,
        )
        if ps_response.status_code == 200:
            import xml.etree.ElementTree as ET
            tree = ET.fromstring(ps_response.text)
            code_el = tree.find("code")
            if code_el is not None and code_el.text:
                checkout_url = f"https://pagseguro.uol.com.br/v2/pre-approvals/request.html?code={code_el.text}"
        if not checkout_url:
            logger.warning(f"PagSeguro checkout failed: {ps_response.status_code} {ps_response.text[:200]}")
            checkout_url = f"https://pagseguro.uol.com.br/v2/pre-approvals/request.html?reference=sub_{assinatura.id}"
    except Exception as e:
        logger.error(f"PagSeguro API error: {e}")
        checkout_url = f"https://pagseguro.uol.com.br/v2/pre-approvals/request.html?reference=sub_{assinatura.id}"

    return {
        "id": assinatura.id,
        "plano": assinatura.plano,
        "status": assinatura.status,
        "checkout_url": checkout_url,
    }


@router.post("/subscription/cancel")
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Cancel the current user's active subscription."""
    assinatura = db.query(Assinatura).filter(
        Assinatura.usuario_id == current_user.id,
        Assinatura.status == "ativa",
    ).first()
    if not assinatura:
        raise HTTPException(status_code=404, detail="Nenhuma assinatura ativa encontrada")

    assinatura.status = "cancelada"

    log = LogAcao(
        usuario_id=current_user.id,
        acao="cancelamento_assinatura",
        detalhes={"plano": assinatura.plano},
    )
    db.add(log)
    db.commit()

    return {"message": "Assinatura cancelada. Créditos ficam inacessíveis até reativação."}
