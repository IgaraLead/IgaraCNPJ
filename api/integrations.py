"""
Cross-product integration endpoints for Entity.
Allows Nexus/Amplex/Hub to interact with Entity data.
"""

import os
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .database import get_db
from .auth import get_current_user
from .models import Usuario, HistoricoBusca

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integrations", tags=["integrations"])

HUB_API_KEY = os.getenv("HUB_API_KEY", "")
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "http://localhost:8001")
HUB_CLIENT_SLUG = os.getenv("HUB_CLIENT_SLUG", "demo")


def _check_api_key(request: Request):
    """Verify API key for cross-product calls."""
    api_key = request.headers.get("X-Api-Key", "")
    if not HUB_API_KEY or api_key != HUB_API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


class EnrichRequest(BaseModel):
    cnpj: str
    # Optional: caller context
    source: str | None = None  # "nexus", "amplex"
    source_id: str | None = None  # e.g., contact_id in the source system


@router.get("/actions/entity")
async def get_integration_actions():
    """Proxy to Hub to discover available integration actions for Entity."""
    url = f"{HUB_BASE_URL}/api/v1/integrations/{HUB_CLIENT_SLUG}/actions/entity"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={"X-Api-Key": HUB_API_KEY})
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.warning("Hub integration actions fetch failed: %s", e)
        return {"source": "entity", "organization": HUB_CLIENT_SLUG, "actions": []}


class BulkExportRequest(BaseModel):
    search_id: str
    target: str  # "nexus" or "amplex"
    client_slug: str | None = None
    # Optional filters
    with_phone: bool = False
    with_email: bool = False
    limit: int | None = None


@router.post("/enrich")
def enrich_cnpj(
    data: EnrichRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Look up CNPJ data and return enriched information.

    Called by Nexus/Amplex when a user clicks "Consultar CNPJ".
    This does NOT consume credits — it uses the internal data already extracted.
    For new lookups that consume credits, use the regular search endpoint.
    """
    _check_api_key(request)

    cnpj_clean = data.cnpj.replace(".", "").replace("/", "").replace("-", "")

    # Search in existing results (historico_buscas)
    from sqlalchemy import text
    result = db.execute(
        text("""
            SELECT params, total_results
            FROM historico_buscas
            WHERE params::text LIKE :cnpj_pattern
            ORDER BY created_at DESC LIMIT 1
        """),
        {"cnpj_pattern": f"%{cnpj_clean}%"},
    ).first()

    if not result:
        raise HTTPException(
            status_code=404,
            detail="CNPJ não encontrado nos dados extraídos. Use a busca regular para consultar.",
        )

    return {
        "cnpj": data.cnpj,
        "cnpj_clean": cnpj_clean,
        "data": result.params if result else {},
        "source": "entity_cache",
    }


@router.post("/export-for-import")
def export_for_cross_product_import(
    data: BulkExportRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Export search results formatted for import into Nexus or Amplex.

    Called when user clicks "Importar no Nexus" or "Importar no CRM" from Entity UI.
    Returns contacts in a format ready for the target product's import API.
    """
    _check_api_key(request)

    # Find the search results
    search = db.query(HistoricoBusca).filter(
        HistoricoBusca.search_id == data.search_id,
    ).first()

    if not search:
        raise HTTPException(status_code=404, detail="Busca não encontrada")

    # Parse results from params/stored data
    results = search.params if isinstance(search.params, list) else search.params.get("results", [])

    contacts = []
    for r in results:
        if isinstance(r, dict):
            contact = {
                "name": r.get("razao_social", r.get("nome_fantasia", "")),
                "cnpj": r.get("cnpj", ""),
                "phone": r.get("telefone", r.get("ddd_telefone_1", "")),
                "email": r.get("email", ""),
                "address": _build_address(r),
                "city": r.get("municipio", ""),
                "state": r.get("uf", ""),
            }

            # Apply filters
            if data.with_phone and not contact["phone"]:
                continue
            if data.with_email and not contact["email"]:
                continue

            contacts.append(contact)

    if data.limit and data.limit > 0:
        contacts = contacts[:data.limit]

    # Build target-specific URLs
    target_urls = _get_import_urls(data.target, data.client_slug)

    return {
        "search_id": data.search_id,
        "target": data.target,
        "total": len(contacts),
        "contacts": contacts,
        "import_url": target_urls.get("import_url", ""),
        "import_endpoint": target_urls.get("import_endpoint", ""),
    }


def _build_address(r: dict) -> str:
    parts = [
        r.get("logradouro", ""),
        r.get("numero", ""),
        r.get("complemento", ""),
        r.get("bairro", ""),
    ]
    return ", ".join(p for p in parts if p)


def _get_import_urls(target: str, client_slug: str | None) -> dict:
    if target == "nexus":
        nexus_url = os.getenv("NEXUS_BASE_URL", "http://localhost:3000")
        return {
            "import_url": f"{nexus_url}/igaralead/api/contacts/import",
            "import_endpoint": "/igaralead/api/contacts/import",
        }
    elif target == "amplex":
        amplex_url = os.getenv("AMPLEX_BASE_URL", "http://localhost:8069")
        return {
            "import_url": f"{amplex_url}/amplex/api/contacts/import",
            "import_endpoint": "/amplex/api/contacts/import",
        }
    return {}
