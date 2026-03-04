"""
Search endpoints: filtered search by UF and CNPJ lookup.
Consumes credits per result returned.
"""

import os
import csv
import io
import uuid
import time
import logging
import tempfile
from typing import Optional

from pydantic import BaseModel
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import get_db
from .auth import get_current_user
from .models import Usuario, Assinatura, HistoricoBusca, Credito
from .credits import check_active_subscription, debit_credits
from .schemas import SearchRequest, SearchResponse, SearchResult, HistoricoBuscaOut
from .redis_queue import redis_client, enqueue_task, set_task_status, get_task_status, set_process_progress, get_process_progress, clear_process_progress
from . import storage

router = APIRouter(tags=["search"])

logger = logging.getLogger(__name__)


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


@router.get("/search/cnaes")
def search_cnaes(
    q: str = "",
    limit: int = 30,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Search CNAE codes by code or description keyword.
    Returns matching items for autocomplete dropdown.
    """
    q = q.strip()
    if not q:
        # Return top-level CNAEs (first 30)
        sql = text("SELECT codigo, descricao FROM cnae ORDER BY codigo LIMIT :limit")
        rows = db.execute(sql, {"limit": limit}).fetchall()
    elif q.isdigit():
        # Search by code prefix
        sql = text("""
            SELECT codigo, descricao FROM cnae
            WHERE codigo LIKE :code_prefix
            ORDER BY codigo
            LIMIT :limit
        """)
        rows = db.execute(sql, {"code_prefix": f"{q}%", "limit": limit}).fetchall()
    else:
        # Search by description keyword
        sql = text("""
            SELECT codigo, descricao FROM cnae
            WHERE descricao ILIKE :keyword
            ORDER BY codigo
            LIMIT :limit
        """)
        rows = db.execute(sql, {"keyword": f"%{q}%", "limit": limit}).fetchall()

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
        # Support comma-separated CNAE codes for multi-select
        cnaes = [c.strip() for c in params.cnae.split(",") if c.strip()]
        if len(cnaes) == 1:
            conditions.append("CAST(e.cnae_fiscal_principal AS TEXT) = :cnae")
            bind_params["cnae"] = cnaes[0]
        elif len(cnaes) > 1:
            placeholders = [f":cnae_{i}" for i in range(len(cnaes))]
            conditions.append(f"CAST(e.cnae_fiscal_principal AS TEXT) IN ({', '.join(placeholders)})")
            for i, cod in enumerate(cnaes):
                bind_params[f"cnae_{i}"] = cod
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
               e.data_inicio_atividade, e.identificador_matriz_filial,
               m.descricao AS municipio_nome
        FROM estabelecimento e
        {join_clause}
        LEFT JOIN munic m ON e.municipio = m.codigo
        WHERE {where_clause}
        ORDER BY emp.razao_social NULLS LAST
        LIMIT :limit OFFSET :offset
    """

    return count_sql, data_sql, bind_params


def _batch_fetch_socios(db, cnpj_basicos: list[str]) -> dict[str, str]:
    """Fetch socios for a batch of cnpj_basico values in a single query.
    Returns a dict mapping cnpj_basico -> concatenated socios string.
    """
    if not cnpj_basicos:
        return {}
    # Process in chunks to avoid excessively long IN clauses
    CHUNK_SIZE = 5000
    result_map: dict[str, str] = {}
    for i in range(0, len(cnpj_basicos), CHUNK_SIZE):
        chunk = cnpj_basicos[i:i + CHUNK_SIZE]
        placeholders = [f":cnpj_{j}" for j in range(len(chunk))]
        sql = f"""
            SELECT cnpj_basico, string_agg(
                nome_socio_razao_social || ' (' || cpf_cnpj_socio || ')', '; '
            ) AS socios_lista
            FROM socios
            WHERE cnpj_basico IN ({', '.join(placeholders)})
            GROUP BY cnpj_basico
        """
        params = {f"cnpj_{j}": v for j, v in enumerate(chunk)}
        rows = db.execute(text(sql), params).fetchall()
        for row in rows:
            result_map[row[0]] = row[1]
    return result_map


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
            "params": {k: v for k, v in params.model_dump().items() if k not in ("search_id",)},
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

    # Use a single query with window function to avoid running count separately
    count_result = db.execute(text(count_sql), bind_params).scalar()
    total = count_result or 0

    if total == 0:
        return SearchResponse(
            results=[], total=0, page=params.page,
            limit=params.limit, credits_consumed=0,
        )

    rows = db.execute(text(data_sql), bind_params).fetchall()

    # Batch-fetch socios separately (avoids correlated subquery per row)
    cnpj_basicos = list({r[0] for r in rows})
    socios_map = _batch_fetch_socios(db, cnpj_basicos)

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
            municipio_nome=r[21] if r[21] else None,
            socios=socios_map.get(r[0]),
        )
        for r in rows
    ]

    # Search is free preview — no credits debited here.
    # User must use /search/process to pay credits and access full data.

    # A search_id represents the entire session (search → process → export).
    # If the frontend passes an existing search_id (e.g. pagination), reuse it.
    # Otherwise create a new entry — even if the filters are identical.
    search_id = None
    if params.search_id:
        existing = (
            db.query(HistoricoBusca)
            .filter(
                HistoricoBusca.search_id == params.search_id,
                HistoricoBusca.usuario_id == current_user.id,
            )
            .first()
        )
        if existing and existing.status == "realizada":
            search_id = existing.search_id
            existing.total_results = total

    if not search_id:
        search_id = str(uuid.uuid4())[:8]
        # Exclude transient fields from stored params
        stored_params = {k: v for k, v in params.model_dump().items() if k not in ("search_id",)}
        historico = HistoricoBusca(
            usuario_id=current_user.id,
            search_id=search_id,
            params=stored_params,
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


# ─── Processing Progress ────────────────────────────────

@router.get("/search/progress/{search_id}")
def get_processing_progress(
    search_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Return real-time processing progress for a search entry.
    Reads from Redis while processing is active, falls back to DB status.
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

    if entry.status == "processando":
        progress = get_process_progress(search_id)
        if progress:
            return {"status": "processando", "percent": progress["percent"], "phase": progress["phase"]}
        return {"status": "processando", "percent": 0, "phase": "Aguardando início..."}

    if entry.status == "processada":
        return {"status": "processada", "percent": 100, "phase": "Concluído"}

    if entry.status == "erro":
        return {"status": "erro", "percent": 0, "phase": "Falha no processamento"}

    return {"status": entry.status, "percent": 0, "phase": ""}


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
        .limit(min(limit, 200))
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


@router.delete("/search/history")
def delete_all_history(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Delete ALL search history entries for the current user.
    Also removes associated export files from S3 storage.
    """
    entries = (
        db.query(HistoricoBusca)
        .filter(HistoricoBusca.usuario_id == current_user.id)
        .all()
    )

    deleted_count = 0
    files_deleted = 0
    for entry in entries:
        if entry.file_id:
            try:
                storage.delete_object(f"{entry.file_id}.csv")
                storage.delete_object(f"{entry.file_id}.xlsx")
                files_deleted += 1
            except Exception:
                pass  # Best effort — file may already be gone
        db.delete(entry)
        deleted_count += 1

    db.commit()
    return {
        "message": f"{deleted_count} consulta(s) removida(s)",
        "files_deleted": files_deleted,
    }


@router.delete("/search/history/{search_id}")
def delete_search_history_entry(
    search_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """Delete a single search history entry and its export files."""
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

    if entry.file_id:
        try:
            storage.delete_object(f"{entry.file_id}.csv")
            storage.delete_object(f"{entry.file_id}.xlsx")
        except Exception:
            pass

    db.delete(entry)
    db.commit()
    return {"message": "Consulta removida com sucesso"}


# ─── Process (Credit-gated) ─────────────────────────────

class ProcessRequest(BaseModel):
    """Request to process (pay credits for) a search query."""
    search_params: SearchRequest
    quantidade: int  # How many CNPJs to process (1 credit each)
    search_id: Optional[str] = None  # Link to existing search session

class ProcessResponse(BaseModel):
    search_id: str
    status: str  # processando
    credits_consumed: int
    quantidade: int


# Column headers for export files
_CSV_HEADERS = [
    "CNPJ", "Razão Social", "Nome Fantasia", "Situação", "UF", "Município",
    "CNAE Principal", "Bairro", "Logradouro", "Número", "Complemento", "CEP",
    "Telefone", "Email", "Capital Social", "Natureza Jurídica", "Porte",
    "Data Início Atividade", "Matriz/Filial", "Sócios",
]


_SITUACAO_MAP = {"1": "Nula", "2": "Ativa", "3": "Suspensa", "4": "Inapta", "8": "Baixada"}
_PORTE_MAP = {1: "Não Informado", 2: "Micro Empresa", 3: "Empresa de Pequeno Porte", 5: "Demais"}
_MATRIZ_MAP = {1: "Matriz", 2: "Filial"}


def _format_date(value: str | None) -> str:
    """Convert date stored as 'YYYYMMDD' integer-string to DD/MM/YYYY."""
    if not value or len(value) != 8 or not value.isdigit():
        return value or ""
    return f"{value[6:8]}/{value[4:6]}/{value[:4]}"


def _format_capital(value: float | None) -> str:
    """Format capital_social as R$ X.XXX,XX."""
    if not value:
        return ""
    try:
        formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"R$ {formatted}"
    except (ValueError, TypeError):
        return str(value)


def _format_cnpj(basico: str, ordem: str, dv: str) -> str:
    """Format CNPJ as XX.XXX.XXX/XXXX-XX"""
    raw = f"{basico}{ordem}{dv}"
    if len(raw) == 14:
        return f"{raw[:2]}.{raw[2:5]}.{raw[5:8]}/{raw[8:12]}-{raw[12:14]}"
    return raw


def _results_to_rows(results: list[SearchResult]) -> list[list]:
    """Convert SearchResult list to plain rows for CSV/XLSX."""
    rows = []
    for r in results:
        rows.append([
            _format_cnpj(r.cnpj_basico, r.cnpj_ordem or "", r.cnpj_dv or ""),
            r.razao_social or "", r.nome_fantasia or "",
            _SITUACAO_MAP.get(r.situacao_cadastral, r.situacao_cadastral or ""),
            r.uf,
            r.municipio_nome or r.municipio or "",
            r.cnae_fiscal_principal or "", r.bairro or "",
            r.logradouro or "", r.numero or "", r.complemento or "",
            r.cep or "", r.telefone or "", r.email or "",
            _format_capital(r.capital_social),
            str(r.natureza_juridica) if r.natureza_juridica else "",
            _PORTE_MAP.get(r.porte_empresa, "") if r.porte_empresa else "",
            _format_date(r.data_inicio_atividade),
            _MATRIZ_MAP.get(r.identificador_matriz_filial, "") if r.identificador_matriz_filial else "",
            r.socios or "",
        ])
    return rows


def _save_processed_files(file_id: str, results: list[SearchResult], user_id: int):
    """Generate CSV and XLSX, upload both to S3 (MinIO)."""
    rows = _results_to_rows(results)

    # ── CSV → S3 ──
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";")
    writer.writerow(_CSV_HEADERS)
    writer.writerows(rows)
    csv_bytes = buf.getvalue().encode("utf-8-sig")
    storage.upload_bytes(
        f"{file_id}.csv", csv_bytes,
        content_type="text/csv; charset=utf-8",
    )

    # ── XLSX → S3 ──
    try:
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Contatos"
        ws.append(_CSV_HEADERS)
        for row in rows:
            ws.append(row)
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            wb.save(tmp.name)
            storage.upload_file(
                f"{file_id}.xlsx", tmp.name,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            os.unlink(tmp.name)
    except ImportError:
        logger.warning("openpyxl not installed; XLSX export unavailable")

    return file_id


def _debit_credits_background(db: Session, user_id: int, amount: int, motivo: str) -> int:
    """Debit credits inside a background task (no HTTPException)."""
    import datetime
    from .models import CreditoTransacao
    credito = db.query(Credito).filter(Credito.usuario_id == user_id).with_for_update().first()
    if not credito or credito.saldo < amount:
        raise RuntimeError(
            f"Créditos insuficientes. Necessário: {amount}, disponível: {credito.saldo if credito else 0}"
        )
    credito.saldo -= amount
    credito.creditos_consumidos += amount
    credito.updated_at = datetime.datetime.utcnow()
    db.add(CreditoTransacao(
        usuario_id=user_id,
        tipo="consumo",
        quantidade=-amount,
        motivo=motivo,
    ))
    return amount


def _update_progress(search_id: str, percent: int, phase: str):
    """Push a progress snapshot to Redis so the frontend can poll it."""
    set_process_progress(search_id, {"percent": percent, "phase": phase})


def _process_in_background(search_id: str, user_id: int, params_dict: dict, quantidade: int):
    """Background task: run the query, generate files, debit credits only on success, update history entry."""
    from .database import SessionLocal
    db = SessionLocal()
    file_id = None
    t_start = time.monotonic()
    try:
        _update_progress(search_id, 0, "Preparando consulta...")
        logger.info(f"[{search_id}] Processamento iniciado | user_id={user_id} quantidade={quantidade} UF={params_dict.get('uf', '?')}")

        params = SearchRequest(**params_dict)
        params.limit = quantidade
        params.page = 1

        count_sql, data_sql, bind_params = _build_search_query(params)

        _update_progress(search_id, 5, "Contando resultados...")
        t0 = time.monotonic()
        count_result = db.execute(text(count_sql), bind_params).scalar()
        total = count_result or 0
        logger.info(f"[{search_id}] COUNT concluído em {time.monotonic() - t0:.2f}s | total={total:,}")

        _update_progress(search_id, 15, "Consultando banco de dados...")
        t0 = time.monotonic()
        rows = db.execute(text(data_sql), bind_params).fetchall()
        actual_count = len(rows)
        query_elapsed = time.monotonic() - t0
        rate = (actual_count / query_elapsed * 60) if query_elapsed > 0 else 0
        logger.info(f"[{search_id}] Query concluída em {query_elapsed:.2f}s | {actual_count:,} linhas | {rate:,.0f} contatos/min")

        if actual_count == 0:
            _update_progress(search_id, 100, "Concluído")
            entry = db.query(HistoricoBusca).filter(
                HistoricoBusca.search_id == search_id,
            ).first()
            if entry:
                entry.status = "processada"
                entry.total_results = total
                entry.credits_consumed = 0
                entry.quantidade_processada = 0
            db.commit()
            clear_process_progress(search_id)
            logger.info(f"[{search_id}] Nenhum resultado encontrado, nenhum crédito debitado")
            return

        _update_progress(search_id, 35, f"Buscando sócios de {actual_count:,} contatos...")
        t0 = time.monotonic()
        cnpj_basicos = list({r[0] for r in rows})
        socios_map = _batch_fetch_socios(db, cnpj_basicos)
        socios_elapsed = time.monotonic() - t0
        logger.info(f"[{search_id}] Sócios buscados em {socios_elapsed:.2f}s | {len(socios_map):,} CNPJs com sócios")

        _update_progress(search_id, 45, f"Montando {actual_count:,} registros...")
        t0 = time.monotonic()
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
                municipio_nome=r[21] if r[21] else None,
                socios=socios_map.get(r[0]),
            )
            for r in rows
        ]
        parse_elapsed = time.monotonic() - t0
        parse_rate = (actual_count / parse_elapsed * 60) if parse_elapsed > 0 else 0
        logger.info(f"[{search_id}] Parsing concluído em {parse_elapsed:.2f}s | {parse_rate:,.0f} contatos/min")

        # Generate downloadable files (CSV + XLSX)
        file_id = str(uuid.uuid4())[:12]

        _update_progress(search_id, 50, "Gerando arquivo CSV...")
        t0 = time.monotonic()
        csv_rows = _results_to_rows(results)
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter=";")
        writer.writerow(_CSV_HEADERS)
        writer.writerows(csv_rows)
        csv_bytes = buf.getvalue().encode("utf-8-sig")
        csv_size_kb = len(csv_bytes) / 1024
        storage.upload_bytes(
            f"{file_id}.csv", csv_bytes,
            content_type="text/csv; charset=utf-8",
        )
        csv_elapsed = time.monotonic() - t0
        logger.info(f"[{search_id}] CSV gerado e enviado ao S3 em {csv_elapsed:.2f}s | {csv_size_kb:,.1f} KB")

        _update_progress(search_id, 70, "Gerando arquivo Excel...")
        t0 = time.monotonic()
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Contatos"
            ws.append(_CSV_HEADERS)
            for row in csv_rows:
                ws.append(row)
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
                wb.save(tmp.name)
                xlsx_size_kb = os.path.getsize(tmp.name) / 1024
                storage.upload_file(
                    f"{file_id}.xlsx", tmp.name,
                    content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                os.unlink(tmp.name)
            xlsx_elapsed = time.monotonic() - t0
            logger.info(f"[{search_id}] XLSX gerado e enviado ao S3 em {xlsx_elapsed:.2f}s | {xlsx_size_kb:,.1f} KB")
        except ImportError:
            logger.warning(f"[{search_id}] openpyxl não instalado; exportação XLSX indisponível")

        _update_progress(search_id, 90, "Debitando créditos...")
        credits_consumed = _debit_credits_background(
            db, user_id, actual_count,
            f"Processamento UF={params_dict.get('uf', '?')} - {actual_count} contatos",
        )

        _update_progress(search_id, 95, "Finalizando...")
        entry = db.query(HistoricoBusca).filter(
            HistoricoBusca.search_id == search_id,
        ).first()
        if entry:
            entry.status = "processada"
            entry.total_results = total
            entry.file_id = file_id
            entry.credits_consumed = credits_consumed
            entry.quantidade_processada = actual_count
        db.commit()

        _update_progress(search_id, 100, "Concluído")
        clear_process_progress(search_id)

        total_elapsed = time.monotonic() - t_start
        overall_rate = (actual_count / total_elapsed * 60) if total_elapsed > 0 else 0
        logger.info(
            f"[{search_id}] Processamento concluído em {total_elapsed:.2f}s | "
            f"{actual_count:,} contatos | {credits_consumed:,} créditos | "
            f"{overall_rate:,.0f} contatos/min | "
            f"CSV={csv_size_kb:,.1f}KB file_id={file_id}"
        )
    except Exception as e:
        total_elapsed = time.monotonic() - t_start
        logger.error(f"[{search_id}] Processamento falhou após {total_elapsed:.2f}s: {e}")
        db.rollback()
        if file_id:
            try:
                storage.delete_object(f"{file_id}.csv")
                storage.delete_object(f"{file_id}.xlsx")
            except Exception:
                pass
        try:
            entry = db.query(HistoricoBusca).filter(
                HistoricoBusca.search_id == search_id,
            ).first()
            if entry:
                entry.status = "erro"
                db.commit()
        except Exception:
            pass
        clear_process_progress(search_id)
    finally:
        db.close()


@router.post("/search/process", response_model=ProcessResponse)
def process_search(
    req: ProcessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Enqueue processing of search results.
    Credits are debited only after files are successfully generated.
    The user can track progress via the search history endpoint.
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

    # Validate user has enough credits (without debiting)
    credito = db.query(Credito).filter(Credito.usuario_id == current_user.id).first()
    if not credito or credito.saldo < quantidade:
        raise HTTPException(
            status_code=402,
            detail=f"Créditos insuficientes. Necessário: {quantidade}, disponível: {credito.saldo if credito else 0}",
        )

    # Reuse existing history entry if search_id provided, otherwise create new
    if req.search_id:
        existing_entry = (
            db.query(HistoricoBusca)
            .filter(
                HistoricoBusca.search_id == req.search_id,
                HistoricoBusca.usuario_id == current_user.id,
            )
            .first()
        )
        if existing_entry and existing_entry.status == "realizada":
            search_id = existing_entry.search_id
            existing_entry.status = "processando"
            existing_entry.quantidade_processada = quantidade
            existing_entry.credits_consumed = 0
            db.commit()
        else:
            # Entry not found or already processed — create new
            search_id = str(uuid.uuid4())[:8]
            stored_params = {k: v for k, v in req.search_params.model_dump().items() if k not in ("search_id",)}
            historico = HistoricoBusca(
                usuario_id=current_user.id,
                search_id=search_id,
                params=stored_params,
                total_results=0,
                status="processando",
                credits_consumed=0,
                quantidade_processada=quantidade,
            )
            db.add(historico)
            db.commit()
    else:
        search_id = str(uuid.uuid4())[:8]
        stored_params = {k: v for k, v in req.search_params.model_dump().items() if k not in ("search_id",)}
        historico = HistoricoBusca(
            usuario_id=current_user.id,
            search_id=search_id,
            params=stored_params,
            total_results=0,
            status="processando",
            credits_consumed=0,
            quantidade_processada=quantidade,
        )
        db.add(historico)
        db.commit()

    # Dispatch background processing (credits debited on success)
    params_for_bg = {k: v for k, v in req.search_params.model_dump().items() if k not in ("search_id",)}
    background_tasks.add_task(
        _process_in_background,
        search_id,
        current_user.id,
        params_for_bg,
        quantidade,
    )

    return ProcessResponse(
        search_id=search_id,
        status="processando",
        credits_consumed=0,
        quantidade=quantidade,
    )


# ─── File Download (streamed from S3) ───────────────────

@router.get("/search/download/{file_id}")
def download_processed_file(
    file_id: str,
    formato: str = Query("csv", pattern="^(csv|xlsx)$"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Stream a processed file from S3 (MinIO) to the client.
    Files are stored permanently.
    """
    # Verify ownership via database
    historico = db.query(HistoricoBusca).filter(
        HistoricoBusca.file_id == file_id,
        HistoricoBusca.usuario_id == current_user.id,
    ).first()
    if not historico:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    s3_key = f"{file_id}.{formato}"
    if not storage.object_exists(s3_key):
        raise HTTPException(
            status_code=404,
            detail="Formato XLSX não disponível" if formato == "xlsx" else "Arquivo não encontrado no storage",
        )

    body = storage.get_object_body(s3_key)
    filename = f"contatos_{file_id}.{formato}"
    media = "text/csv" if formato == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return StreamingResponse(
        body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
        "params": {k: v for k, v in req.search_params.model_dump().items() if k not in ("search_id",)},
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
