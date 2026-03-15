"""Metrics endpoint consumed by Hub's aggregated dashboard."""

import os
import logging

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import Depends

from .database import get_db
from .models import Usuario, Credito, CreditoTransacao, Assinatura, HistoricoBusca

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["metrics"])

HUB_METRICS_KEY = os.getenv("HUB_METRICS_KEY", "")


def _check_metrics_key(request: Request):
    api_key = request.headers.get("X-Api-Key", "")
    if not HUB_METRICS_KEY or api_key != HUB_METRICS_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.get("/metrics")
def entity_metrics(request: Request, db: Session = Depends(get_db)):
    """Return Entity platform metrics for Hub dashboard."""
    _check_metrics_key(request)

    total_users = db.query(func.count(Usuario.id)).scalar() or 0
    active_subs = db.query(func.count(Assinatura.id)).filter(
        Assinatura.status == "ativa"
    ).scalar() or 0

    # Credit stats
    total_credits_consumed = db.query(
        func.coalesce(func.sum(Credito.creditos_consumidos), 0)
    ).scalar()
    total_credits_available = db.query(
        func.coalesce(func.sum(Credito.saldo), 0)
    ).scalar()

    # Search stats
    total_searches = db.query(func.count(HistoricoBusca.id)).scalar() or 0
    processed_searches = db.query(func.count(HistoricoBusca.id)).filter(
        HistoricoBusca.status == "processada"
    ).scalar() or 0
    exported_searches = db.query(func.count(HistoricoBusca.id)).filter(
        HistoricoBusca.status == "exportada"
    ).scalar() or 0

    # Total results found across all searches
    total_results_found = db.query(
        func.coalesce(func.sum(HistoricoBusca.total_results), 0)
    ).scalar()

    # Transaction count
    total_transactions = db.query(func.count(CreditoTransacao.id)).scalar() or 0

    return {
        "users": total_users,
        "active_subscriptions": active_subs,
        "credits_consumed": int(total_credits_consumed),
        "credits_available": int(total_credits_available),
        "total_searches": total_searches,
        "processed_searches": processed_searches,
        "exported_searches": exported_searches,
        "total_results_found": int(total_results_found),
        "total_transactions": total_transactions,
    }
