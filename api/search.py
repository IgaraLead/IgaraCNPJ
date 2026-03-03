"""
Search endpoints: filtered search by UF and CNPJ lookup.
Consumes credits per result returned.
"""

import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import get_db
from .auth import get_current_user
from .models import Usuario, Assinatura
from .credits import check_active_subscription, debit_credits
from .schemas import SearchRequest, SearchResponse, SearchResult
from .redis_queue import redis_client, enqueue_task

router = APIRouter(tags=["search"])

MODO_FILA = os.getenv("MODO_FILA_PADRAO", "false").lower() == "true"

UFS_VALIDAS = [
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
    "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
    "SE", "SP", "TO",
]

# Rate limit for free plan: max 5 per minute (tracked in Redis)
FREE_RATE_LIMIT = 5


def _is_queue_mode_active(db: Session) -> bool:
    """Check if queue mode is enabled in system config."""
    from .models import ConfigSistema
    config = db.query(ConfigSistema).filter(ConfigSistema.chave == "modo_fila").first()
    if config:
        return config.valor.lower() in ("true", "1", "yes")
    return MODO_FILA


def _build_search_query(params: SearchRequest) -> tuple:
    """Build parameterized SQL query for search."""
    conditions = ["e.uf = :uf"]
    bind_params = {"uf": params.uf.upper()}

    if params.municipio:
        conditions.append("e.municipio = :municipio")
        bind_params["municipio"] = params.municipio
    if params.cnae:
        conditions.append("e.cnae_fiscal_principal = :cnae")
        bind_params["cnae"] = params.cnae
    if params.situacao:
        conditions.append("e.situacao_cadastral = :situacao")
        bind_params["situacao"] = params.situacao
    if params.porte:
        conditions.append("emp.porte_empresa = CAST(:porte AS INTEGER)")
        bind_params["porte"] = params.porte
    if params.q:
        conditions.append("(emp.razao_social ILIKE :q OR e.nome_fantasia ILIKE :q)")
        bind_params["q"] = f"%{params.q}%"

    where_clause = " AND ".join(conditions)
    offset = (params.page - 1) * params.limit
    bind_params["limit"] = params.limit
    bind_params["offset"] = offset

    count_sql = f"""
        SELECT COUNT(*) FROM estabelecimento e
        LEFT JOIN empresa emp ON e.cnpj_basico = emp.cnpj_basico
        WHERE {where_clause}
    """

    data_sql = f"""
        SELECT e.cnpj_basico, e.cnpj_ordem, e.cnpj_dv,
               emp.razao_social, e.nome_fantasia,
               e.situacao_cadastral, e.uf, e.municipio,
               e.cnae_fiscal_principal
        FROM estabelecimento e
        LEFT JOIN empresa emp ON e.cnpj_basico = emp.cnpj_basico
        WHERE {where_clause}
        ORDER BY emp.razao_social
        LIMIT :limit OFFSET :offset
    """

    return count_sql, data_sql, bind_params


@router.post("/search", response_model=SearchResponse)
def search(
    params: SearchRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Search establishments by UF with filters.
    Consumes 1 credit per CNPJ returned.
    """
    if params.uf.upper() not in UFS_VALIDAS:
        raise HTTPException(status_code=400, detail=f"UF inválida: {params.uf}")

    # Check subscription (free plan has limited access)
    assinatura = db.query(Assinatura).filter(
        Assinatura.usuario_id == current_user.id,
        Assinatura.status == "ativa",
    ).first()

    is_free = assinatura is None

    if is_free:
        # Free plan: rate limit, basic data only, max 5 results, page 1 only
        params.limit = min(params.limit, 5)
        params.page = 1  # Free users cannot paginate
        # Enforce rate limit for free users
        if redis_client:
            try:
                rate_key = f"rate:search:{current_user.id}"
                current_count = redis_client.get(rate_key)
                if current_count and int(current_count) >= FREE_RATE_LIMIT:
                    raise HTTPException(
                        status_code=429,
                        detail="Limite de consultas gratuitas atingido. Aguarde 1 minuto ou assine um plano.",
                    )
                pipe = redis_client.pipeline()
                pipe.incr(rate_key)
                pipe.expire(rate_key, 60)  # 1 minute window
                pipe.execute()
            except HTTPException:
                raise
            except Exception:
                pass  # Redis down — allow request without rate limiting
    else:
        check_active_subscription(db, current_user.id)

    # Check queue mode
    if _is_queue_mode_active(db):
        task_id = str(uuid.uuid4())
        task_data = {
            "task_id": task_id,
            "user_id": current_user.id,
            "params": params.model_dump(),
            "type": "search",
        }
        enqueue_task(task_data)
        return SearchResponse(
            results=[], total=0, page=params.page,
            limit=params.limit, credits_consumed=0,
            task_id=task_id,
        )

    # Execute search
    count_sql, data_sql, bind_params = _build_search_query(params)

    count_result = db.execute(text(count_sql), bind_params).scalar()
    total = count_result or 0

    rows = db.execute(text(data_sql), bind_params).fetchall()

    results = [
        SearchResult(
            cnpj_basico=r[0], cnpj_ordem=r[1], cnpj_dv=r[2],
            razao_social=r[3], nome_fantasia=r[4],
            situacao_cadastral=str(r[5]) if r[5] else None,
            uf=r[6], municipio=str(r[7]) if r[7] else None,
            cnae_fiscal_principal=str(r[8]) if r[8] else None,
        )
        for r in rows
    ]

    credits_consumed = 0
    if not is_free and len(results) > 0:
        credits_consumed = debit_credits(
            db, current_user.id, len(results),
            f"Busca UF={params.uf} - {len(results)} resultados",
        )
        db.commit()

    return SearchResponse(
        results=results, total=total, page=params.page,
        limit=params.limit, credits_consumed=credits_consumed,
    )


@router.get("/search/{cnpj}")
def search_cnpj(
    cnpj: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lookup a single CNPJ. Consumes 1 credit.
    CNPJ format: 14 digits (no punctuation).
    """
    cnpj_clean = cnpj.replace(".", "").replace("/", "").replace("-", "")
    if len(cnpj_clean) != 14:
        raise HTTPException(status_code=400, detail="CNPJ deve ter 14 dígitos")

    cnpj_basico = cnpj_clean[:8]
    cnpj_ordem = cnpj_clean[8:12]
    cnpj_dv = cnpj_clean[12:14]

    assinatura = db.query(Assinatura).filter(
        Assinatura.usuario_id == current_user.id,
        Assinatura.status == "ativa",
    ).first()
    is_free = assinatura is None

    # Rate limit free users on CNPJ lookup too
    if is_free and redis_client:
        try:
            rate_key = f"rate:cnpj:{current_user.id}"
            current_count = redis_client.get(rate_key)
            if current_count and int(current_count) >= FREE_RATE_LIMIT:
                raise HTTPException(
                    status_code=429,
                    detail="Limite de consultas gratuitas atingido. Aguarde 1 minuto ou assine um plano.",
                )
            pipe = redis_client.pipeline()
            pipe.incr(rate_key)
            pipe.expire(rate_key, 60)
            pipe.execute()
        except HTTPException:
            raise
        except Exception:
            pass  # Redis down — skip rate limiting

    sql = text("""
        SELECT e.*, emp.razao_social, emp.natureza_juridica,
               emp.capital_social, emp.porte_empresa
        FROM estabelecimento e
        LEFT JOIN empresa emp ON e.cnpj_basico = emp.cnpj_basico
        WHERE e.cnpj_basico = :basico AND e.cnpj_ordem = :ordem AND e.cnpj_dv = :dv
        LIMIT 1
    """)

    row = db.execute(sql, {"basico": cnpj_basico, "ordem": cnpj_ordem, "dv": cnpj_dv}).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="CNPJ não encontrado")

    result = dict(row._mapping)

    if not is_free:
        debit_credits(db, current_user.id, 1, f"Consulta CNPJ {cnpj_clean}")
        db.commit()

    # Attribution
    result["fonte"] = "Receita Federal do Brasil - Dados Públicos CNPJ"

    return result
