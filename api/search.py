"""
Search endpoints: filtered search by UF and CNPJ lookup.
Consumes credits per result returned.
"""

import os
import uuid
from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import get_db
from .auth import get_current_user
from .models import Usuario, Assinatura, HistoricoBusca
from .credits import check_active_subscription, debit_credits
from .schemas import SearchRequest, SearchResponse, SearchResult, HistoricoBuscaOut
from .redis_queue import redis_client, enqueue_task

router = APIRouter(tags=["search"])


@router.get("/search/municipios")
def get_municipios_by_uf(
    uf: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Return municipalities available for a given UF.
    Queries the munic reference table joined with distinct municipio codes
    found in estabelecimento for the requested UF.
    """
    if uf.upper() not in UFS_VALIDAS:
        raise HTTPException(status_code=400, detail=f"UF inválida: {uf}")

    sql = text("""
        SELECT DISTINCT m.codigo, m.descricao
        FROM munic m
        INNER JOIN estabelecimento e ON e.municipio = m.codigo
        WHERE e.uf = :uf
        ORDER BY m.descricao
    """)
    rows = db.execute(sql, {"uf": uf.upper()}).fetchall()
    return [{"codigo": r[0], "descricao": r[1]} for r in rows]

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
    joins = ["LEFT JOIN empresa emp ON e.cnpj_basico = emp.cnpj_basico"]

    if params.municipio:
        # Support comma-separated municipio codes for multi-select
        codigos = [c.strip() for c in params.municipio.split(",") if c.strip()]
        if len(codigos) == 1:
            conditions.append("e.municipio = CAST(:municipio AS INTEGER)")
            bind_params["municipio"] = codigos[0]
        elif len(codigos) > 1:
            placeholders = [f":mun_{i}" for i in range(len(codigos))]
            conditions.append(f"e.municipio IN ({', '.join(placeholders)})")
            for i, cod in enumerate(codigos):
                bind_params[f"mun_{i}"] = int(cod)
    if params.cnae:
        conditions.append("e.cnae_fiscal_principal = :cnae")
        bind_params["cnae"] = params.cnae
    if params.situacao:
        conditions.append("e.situacao_cadastral = :situacao")
        bind_params["situacao"] = params.situacao
    if params.porte:
        conditions.append("emp.porte_empresa = CAST(:porte AS INTEGER)")
        bind_params["porte"] = params.porte
    if params.natureza_juridica:
        conditions.append("emp.natureza_juridica = CAST(:natureza_juridica AS INTEGER)")
        bind_params["natureza_juridica"] = params.natureza_juridica
    if params.cep:
        conditions.append("e.cep = :cep")
        bind_params["cep"] = params.cep.replace("-", "")
    if params.bairro:
        conditions.append("e.bairro ILIKE :bairro")
        bind_params["bairro"] = f"%{params.bairro}%"
    if params.logradouro:
        conditions.append("e.logradouro ILIKE :logradouro")
        bind_params["logradouro"] = f"%{params.logradouro}%"
    if params.matriz_filial:
        conditions.append("e.identificador_matriz_filial = CAST(:matriz_filial AS INTEGER)")
        bind_params["matriz_filial"] = params.matriz_filial
    if params.capital_social_min is not None:
        conditions.append("emp.capital_social >= :capital_min")
        bind_params["capital_min"] = params.capital_social_min
    if params.capital_social_max is not None:
        conditions.append("emp.capital_social <= :capital_max")
        bind_params["capital_max"] = params.capital_social_max
    if params.data_abertura_inicio:
        conditions.append("e.data_inicio_atividade >= CAST(:data_inicio AS INTEGER)")
        bind_params["data_inicio"] = params.data_abertura_inicio
    if params.data_abertura_fim:
        conditions.append("e.data_inicio_atividade <= CAST(:data_fim AS INTEGER)")
        bind_params["data_fim"] = params.data_abertura_fim
    if params.ddd:
        conditions.append("e.ddd_1 = :ddd")
        bind_params["ddd"] = params.ddd
    if params.com_email is True:
        conditions.append("e.correio_eletronico IS NOT NULL AND e.correio_eletronico != ''")
    elif params.com_email is False:
        conditions.append("(e.correio_eletronico IS NULL OR e.correio_eletronico = '')")
    if params.com_telefone is True:
        conditions.append("e.telefone_1 IS NOT NULL AND e.telefone_1 != ''")
    elif params.com_telefone is False:
        conditions.append("(e.telefone_1 IS NULL OR e.telefone_1 = '')")
    if params.simples:
        joins.append("LEFT JOIN simples s ON e.cnpj_basico = s.cnpj_basico")
        conditions.append("s.opcao_pelo_simples = :simples")
        bind_params["simples"] = params.simples
    if params.mei:
        if "simples s" not in " ".join(joins):
            joins.append("LEFT JOIN simples s ON e.cnpj_basico = s.cnpj_basico")
        conditions.append("s.opcao_mei = :mei")
        bind_params["mei"] = params.mei
    if params.q:
        conditions.append("(emp.razao_social ILIKE :q OR e.nome_fantasia ILIKE :q)")
        bind_params["q"] = f"%{params.q}%"

    where_clause = " AND ".join(conditions)
    join_clause = " ".join(joins)
    offset = (params.page - 1) * params.limit
    bind_params["limit"] = params.limit
    bind_params["offset"] = offset

    count_sql = f"""
        SELECT COUNT(*) FROM estabelecimento e
        {join_clause}
        WHERE {where_clause}
    """

    data_sql = f"""
        SELECT e.cnpj_basico, e.cnpj_ordem, e.cnpj_dv,
               emp.razao_social, e.nome_fantasia,
               e.situacao_cadastral, e.uf, e.municipio,
               e.cnae_fiscal_principal,
               e.bairro, e.logradouro, e.numero, e.complemento, e.cep,
               CASE WHEN e.ddd_1 IS NOT NULL AND e.telefone_1 IS NOT NULL
                    THEN '(' || e.ddd_1 || ') ' || e.telefone_1
                    ELSE NULL END AS telefone,
               e.correio_eletronico AS email,
               emp.capital_social, emp.natureza_juridica, emp.porte_empresa,
               e.data_inicio_atividade, e.identificador_matriz_filial
        FROM estabelecimento e
        {join_clause}
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
            bairro=r[9], logradouro=r[10], numero=r[11],
            complemento=r[12], cep=r[13],
            telefone=r[14], email=r[15],
            capital_social=float(r[16]) if r[16] else None,
            natureza_juridica=int(r[17]) if r[17] else None,
            porte_empresa=int(r[18]) if r[18] else None,
            data_inicio_atividade=str(r[19]) if r[19] else None,
            identificador_matriz_filial=int(r[20]) if r[20] else None,
        )
        for r in rows
    ]

    # Search is free preview — no credits debited here.
    # User must use /search/process to pay credits and access full data.

    # Save to search history
    search_id = str(uuid.uuid4())[:8]
    historico = HistoricoBusca(
        usuario_id=current_user.id,
        search_id=search_id,
        params=params.model_dump(),
        total_results=total,
        status="realizada",
        credits_consumed=0,
    )
    db.add(historico)
    db.commit()

    return SearchResponse(
        results=results, total=total, page=params.page,
        limit=params.limit, credits_consumed=0,
        search_id=search_id,
    )


# ─── Search History ─────────────────────────────────────

@router.get("/search/history", response_model=list[HistoricoBuscaOut])
def list_search_history(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """List current user's search history, most recent first."""
    rows = (
        db.query(HistoricoBusca)
        .filter(HistoricoBusca.usuario_id == current_user.id)
        .order_by(HistoricoBusca.created_at.desc())
        .limit(limit)
        .all()
    )
    return rows


@router.get("/search/history/{search_id}")
def get_search_by_id(
    search_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Get a search history entry. Returns the saved params and total.
    The frontend can re-execute the search using these params.
    """
    entry = (
        db.query(HistoricoBusca)
        .filter(
            HistoricoBusca.search_id == search_id,
            HistoricoBusca.usuario_id == current_user.id,
        )
        .first()
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Busca não encontrada")

    return {
        "search_id": entry.search_id,
        "params": entry.params,
        "total_results": entry.total_results,
        "status": entry.status,
        "credits_consumed": entry.credits_consumed,
        "created_at": str(entry.created_at),
    }


# ─── Process (Credit-gated) ─────────────────────────────

class ProcessRequest(BaseModel):
    """Request to process (pay credits for) a search query."""
    search_params: SearchRequest
    quantidade: int  # How many CNPJs to process (1 credit each)

class ProcessResponse(BaseModel):
    results: list[SearchResult]
    total: int
    credits_consumed: int


@router.post("/search/process", response_model=ProcessResponse)
def process_search(
    req: ProcessRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Process (unlock) search results by paying credits.
    1 credit per CNPJ.
    Returns the requested number of full results.
    """
    assinatura = db.query(Assinatura).filter(
        Assinatura.usuario_id == current_user.id,
        Assinatura.status == "ativa",
    ).first()
    if not assinatura:
        raise HTTPException(status_code=403, detail="Assinatura inativa. Assine um plano para processar dados.")

    quantidade = req.quantidade
    if quantidade < 1:
        raise HTTPException(status_code=400, detail="Quantidade deve ser pelo menos 1")
    if quantidade > 50000:
        raise HTTPException(status_code=400, detail="Máximo de 50.000 contatos por processamento")

    params = req.search_params
    params.limit = quantidade
    params.page = 1

    count_sql, data_sql, bind_params = _build_search_query(params)

    count_result = db.execute(text(count_sql), bind_params).scalar()
    total = count_result or 0

    rows = db.execute(text(data_sql), bind_params).fetchall()
    actual_count = len(rows)

    if actual_count == 0:
        return ProcessResponse(results=[], total=total, credits_consumed=0)

    # Debit credits: 1 per CNPJ
    credits_consumed = debit_credits(
        db, current_user.id, actual_count,
        f"Processamento UF={params.uf} - {actual_count} contatos",
    )
    db.commit()

    results = [
        SearchResult(
            cnpj_basico=r[0], cnpj_ordem=r[1], cnpj_dv=r[2],
            razao_social=r[3], nome_fantasia=r[4],
            situacao_cadastral=str(r[5]) if r[5] else None,
            uf=r[6], municipio=str(r[7]) if r[7] else None,
            cnae_fiscal_principal=str(r[8]) if r[8] else None,
            bairro=r[9], logradouro=r[10], numero=r[11],
            complemento=r[12], cep=r[13],
            telefone=r[14], email=r[15],
            capital_social=float(r[16]) if r[16] else None,
            natureza_juridica=int(r[17]) if r[17] else None,
            porte_empresa=int(r[18]) if r[18] else None,
            data_inicio_atividade=str(r[19]) if r[19] else None,
            identificador_matriz_filial=int(r[20]) if r[20] else None,
        )
        for r in rows
    ]

    return ProcessResponse(results=results, total=total, credits_consumed=credits_consumed)


# ─── Export (Credit-gated, 10 credits) ──────────────────

class ExportCreditRequest(BaseModel):
    search_params: SearchRequest
    formato: str = "csv"  # csv or xlsx

class ExportCreditResponse(BaseModel):
    task_id: str
    status: str
    credits_consumed: int


@router.post("/search/export", response_model=ExportCreditResponse)
def export_with_credits(
    req: ExportCreditRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Export search results. Costs 10 credits flat fee.
    """
    assinatura = db.query(Assinatura).filter(
        Assinatura.usuario_id == current_user.id,
        Assinatura.status == "ativa",
    ).first()
    if not assinatura:
        raise HTTPException(status_code=403, detail="Assinatura inativa. Assine um plano para exportar.")

    if req.formato not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="Formato deve ser 'csv' ou 'xlsx'")

    EXPORT_COST = 10
    credits_consumed = debit_credits(
        db, current_user.id, EXPORT_COST,
        f"Exportação {req.formato.upper()} UF={req.search_params.uf}",
    )

    task_id = str(uuid.uuid4())
    task_data = {
        "task_id": task_id,
        "user_id": current_user.id,
        "params": req.search_params.model_dump(),
        "formato": req.formato,
        "type": "export",
    }
    enqueue_task(task_data)
    db.commit()

    return ExportCreditResponse(task_id=task_id, status="processing", credits_consumed=credits_consumed)


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
