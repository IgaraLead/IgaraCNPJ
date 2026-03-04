"""
Super-admin endpoints: stats, queue control, UF management, logs, user management, ETL.
All endpoints require super_admin role.
"""

import asyncio
import json
import os
import datetime
import time as _time
from typing import List

import redis
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import get_db
from .auth import require_super_admin, get_current_user
from .models import (
    Usuario, Credito, CreditoTransacao, Assinatura,
    LogAcao, ConfigSistema, HistoricoBusca,
)
from .schemas import (
    AjusteCreditos, ToggleUF, ToggleQueue, LogAcaoOut, StatsOut,
    AdminCreateUser, AdminChangeRole, AdminSetSubscription,
)
from .redis_queue import (
    redis_client, get_queue_size, cache_clear_all,
    etl_progress_get, etl_progress_set,
    ETL_PROGRESS_CHANNEL, REDIS_HOST, REDIS_PORT, REDIS_DB,
)

router = APIRouter(prefix="/admin", tags=["admin"])

LIMITE_CREDITOS_MAXIMO = int(os.getenv("LIMITE_CREDITOS_MAXIMO", "100000"))
ENV_ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@seudominio.com")


@router.get("/stats", response_model=StatsOut)
def admin_stats(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """System-wide metrics."""
    usuarios_ativos = db.query(func.count(Usuario.id)).filter(Usuario.ativo == True).scalar() or 0
    total_consultas = (
        db.query(func.count(CreditoTransacao.id))
        .filter(CreditoTransacao.tipo == "consumo")
        .scalar() or 0
    )
    creditos_consumidos = (
        db.query(func.sum(func.abs(CreditoTransacao.quantidade)))
        .filter(CreditoTransacao.tipo == "consumo")
        .scalar() or 0
    )
    fila_tamanho = get_queue_size()

    return StatsOut(
        usuarios_ativos=usuarios_ativos,
        total_consultas=total_consultas,
        creditos_consumidos_total=creditos_consumidos,
        fila_tamanho=fila_tamanho,
    )


# ─── Queue Control ──────────────────────────────────────

@router.get("/config/queue")
def get_queue_status(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Get current queue mode status."""
    config = db.query(ConfigSistema).filter(ConfigSistema.chave == "modo_fila").first()
    ativado = config.valor.lower() in ("true", "1") if config else False
    return {"queue_mode": ativado, "queue_size": get_queue_size()}


@router.post("/config/queue")
def toggle_queue(
    data: ToggleQueue,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Toggle queue mode on/off."""
    config = db.query(ConfigSistema).filter(ConfigSistema.chave == "modo_fila").first()
    if config:
        config.valor = str(data.ativado).lower()
    else:
        config = ConfigSistema(chave="modo_fila", valor=str(data.ativado).lower())
        db.add(config)

    log = LogAcao(
        usuario_id=admin.id,
        acao="toggle_fila",
        detalhes={"ativado": data.ativado},
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    db.commit()

    return {"queue_mode": data.ativado}


# ─── UF Management ──────────────────────────────────────

UF_LIST = [
    "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
    "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO",
]


@router.get("/ufs")
def get_ufs(
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Get active/inactive status for all UFs."""
    configs = db.query(ConfigSistema).filter(
        ConfigSistema.chave.like("uf_ativa_%")
    ).all()
    uf_map = {c.chave.replace("uf_ativa_", ""): c.valor.lower() in ("true", "1") for c in configs}
    return {uf: uf_map.get(uf, True) for uf in UF_LIST}


@router.post("/ufs/toggle")
def toggle_uf(
    data: ToggleUF,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Enable/disable a UF."""
    config_key = f"uf_ativa_{data.uf.upper()}"
    config = db.query(ConfigSistema).filter(ConfigSistema.chave == config_key).first()
    if config:
        config.valor = str(data.ativo).lower()
    else:
        config = ConfigSistema(chave=config_key, valor=str(data.ativo).lower())
        db.add(config)

    log = LogAcao(
        usuario_id=admin.id,
        acao="toggle_uf",
        detalhes={"uf": data.uf, "ativo": data.ativo},
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    db.commit()

    return {"uf": data.uf, "ativo": data.ativo}


# ─── Logs ─────────────────────────────────────────────

@router.get("/logs", response_model=List[LogAcaoOut])
def get_logs(
    limit: int = 100,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Get action logs."""
    logs = (
        db.query(LogAcao)
        .order_by(LogAcao.created_at.desc())
        .limit(limit)
        .all()
    )
    return logs


# ─── User Management ────────────────────────────────────

@router.post("/users/{user_id}/adjust-credits")
def adjust_credits(
    user_id: int,
    data: AjusteCreditos,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Manually adjust a user's credits."""
    credito = db.query(Credito).filter(Credito.usuario_id == user_id).first()
    if not credito:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    new_saldo = credito.saldo + data.quantidade
    if new_saldo < 0:
        raise HTTPException(status_code=400, detail="Saldo não pode ficar negativo")
    if new_saldo > LIMITE_CREDITOS_MAXIMO:
        raise HTTPException(status_code=400, detail=f"Saldo não pode exceder {LIMITE_CREDITOS_MAXIMO}")

    credito.saldo = new_saldo
    if data.quantidade > 0:
        credito.creditos_recebidos += data.quantidade

    transacao = CreditoTransacao(
        usuario_id=user_id,
        tipo="ajuste_manual",
        quantidade=data.quantidade,
        motivo=data.motivo,
        metadata_extra={"admin_id": admin.id},
    )
    db.add(transacao)

    log = LogAcao(
        usuario_id=admin.id,
        acao="ajuste_creditos",
        detalhes={"user_id": user_id, "quantidade": data.quantidade, "motivo": data.motivo},
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    db.commit()

    return {"user_id": user_id, "novo_saldo": credito.saldo}


@router.post("/users/{user_id}/block")
def block_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Block/unblock a user."""
    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if user.role == "super_admin" or user.email == ENV_ADMIN_EMAIL:
        raise HTTPException(status_code=400, detail="Não é possível bloquear esta conta")

    user.ativo = not user.ativo

    log = LogAcao(
        usuario_id=admin.id,
        acao="block_user" if not user.ativo else "unblock_user",
        detalhes={"user_id": user_id, "ativo": user.ativo},
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    db.commit()

    return {"user_id": user_id, "ativo": user.ativo}


@router.get("/users")
def list_users(
    page: int = 1,
    limit: int = 50,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """List all users with basic info."""
    offset = (page - 1) * limit
    users = db.query(Usuario).offset(offset).limit(limit).all()
    total = db.query(func.count(Usuario.id)).scalar()

    # Batch-load subscriptions and credits to avoid N+1 queries
    user_ids = [u.id for u in users]
    assinaturas = db.query(Assinatura).filter(
        Assinatura.usuario_id.in_(user_ids),
        Assinatura.status == "ativa",
    ).all()
    assinatura_map = {a.usuario_id: a for a in assinaturas}
    creditos = db.query(Credito).filter(Credito.usuario_id.in_(user_ids)).all()
    credito_map = {c.usuario_id: c for c in creditos}

    result = []
    for u in users:
        assinatura = assinatura_map.get(u.id)
        credito = credito_map.get(u.id)
        result.append({
            "id": u.id,
            "nome": u.nome,
            "email": u.email,
            "role": u.role,
            "ativo": u.ativo,
            "criado_em": str(u.criado_em),
            "plano": assinatura.plano if assinatura else None,
            "plano_permanente": assinatura.data_validade is None if assinatura else None,
            "plano_validade": str(assinatura.data_validade) if assinatura and assinatura.data_validade else None,
            "plano_manual": assinatura.manual if assinatura else False,
            "saldo_creditos": credito.saldo if credito else 0,
            "is_env_admin": u.email == ENV_ADMIN_EMAIL,
        })

    return {
        "users": result,
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.post("/users/create")
def create_user(
    data: AdminCreateUser,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Create a new user account (admin-only)."""
    from .auth import hash_password

    if data.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role deve ser 'user' ou 'admin'")

    existing = db.query(Usuario).filter(Usuario.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email já cadastrado")

    new_user = Usuario(
        nome=data.nome,
        email=data.email,
        senha_hash=hash_password(data.senha),
        telefone=data.telefone,
        role=data.role,
        ativo=True,
    )
    db.add(new_user)
    db.flush()

    credito = Credito(usuario_id=new_user.id, saldo=0)
    db.add(credito)

    log = LogAcao(
        usuario_id=admin.id,
        acao="admin_create_user",
        detalhes={"new_user_id": new_user.id, "email": data.email, "role": data.role},
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    db.commit()

    return {"id": new_user.id, "email": new_user.email, "role": new_user.role}


@router.post("/users/{user_id}/role")
def change_user_role(
    user_id: int,
    data: AdminChangeRole,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Change a user's role. Cannot change the env-configured admin."""
    if data.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role deve ser 'user' ou 'admin'")

    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    if user.email == ENV_ADMIN_EMAIL:
        raise HTTPException(status_code=403, detail="Não é possível alterar o nível da conta administrativa principal")

    if user.role == "super_admin":
        raise HTTPException(status_code=403, detail="Não é possível alterar o nível de um super-admin")

    user.role = data.role

    log = LogAcao(
        usuario_id=admin.id,
        acao="change_role",
        detalhes={"user_id": user_id, "new_role": data.role},
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    db.commit()

    return {"user_id": user_id, "role": user.role}


@router.post("/users/{user_id}/subscription")
def set_user_subscription(
    user_id: int,
    data: AdminSetSubscription,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Manually set a user's subscription plan with optional expiry."""
    from .plans import PLANS

    if data.plano not in PLANS:
        raise HTTPException(status_code=400, detail="Plano inválido")

    user = db.query(Usuario).filter(Usuario.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    # Deactivate existing active subscription
    existing = db.query(Assinatura).filter(
        Assinatura.usuario_id == user_id,
        Assinatura.status == "ativa",
    ).first()
    if existing:
        existing.status = "substituida"

    now = datetime.datetime.now(datetime.timezone.utc)
    data_validade = None
    if not data.permanente:
        if not data.dias_validade or data.dias_validade < 1:
            raise HTTPException(status_code=400, detail="Informe dias_validade para plano não-permanente")
        data_validade = now + datetime.timedelta(days=data.dias_validade)

    assinatura = Assinatura(
        usuario_id=user_id,
        plano=data.plano,
        status="ativa",
        manual=True,
        data_inicio=now,
        data_validade=data_validade,
    )
    db.add(assinatura)

    # Grant credits if specified
    credito = db.query(Credito).filter(Credito.usuario_id == user_id).first()
    if not credito:
        credito = Credito(usuario_id=user_id, saldo=0)
        db.add(credito)
        db.flush()

    if data.creditos and data.creditos > 0:
        plan_info = PLANS[data.plano]
        new_saldo = min(credito.saldo + data.creditos, LIMITE_CREDITOS_MAXIMO)
        added = new_saldo - credito.saldo
        credito.saldo = new_saldo
        credito.creditos_recebidos += added

        transacao = CreditoTransacao(
            usuario_id=user_id,
            tipo="ajuste_manual",
            quantidade=added,
            motivo=f"Ativação manual plano {data.plano} pelo admin",
            metadata_extra={"admin_id": admin.id},
        )
        db.add(transacao)

    log = LogAcao(
        usuario_id=admin.id,
        acao="admin_set_subscription",
        detalhes={
            "user_id": user_id,
            "plano": data.plano,
            "permanente": data.permanente,
            "dias_validade": data.dias_validade,
            "creditos": data.creditos,
        },
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    db.commit()

    return {
        "user_id": user_id,
        "plano": data.plano,
        "permanente": data.permanente,
        "data_validade": str(data_validade) if data_validade else None,
    }


# ─── ETL / Maintenance ──────────────────────────────────

def _check_stale_progress(data: dict) -> dict:
    """If progress is stale (no update in 2+ min), mark as error."""
    if data.get("running") and data.get("phase") not in ("done", "error"):
        updated_at = data.get("updated_at", 0)
        if _time.time() - updated_at > 120:
            data = {
                "running": False,
                "phase": "error",
                "step": "Processo interrompido (timeout)",
                "percent": 0,
                "detail": "O processo parou de reportar progresso e foi marcado como encerrado.",
                "updated_at": _time.time(),
            }
            etl_progress_set(data)
    return data


@router.get("/etl-progress")
def get_etl_progress(
    admin: Usuario = Depends(require_super_admin),
):
    """Return current ETL progress from Redis. Auto-resets stale runs."""
    data = etl_progress_get()
    if not data:
        return {"running": False}
    return _check_stale_progress(data)


@router.get("/etl-progress/stream")
async def etl_progress_stream(
    request: Request,
    admin: Usuario = Depends(require_super_admin),
):
    """SSE stream of ETL progress updates (replaces polling)."""

    async def event_generator():
        # 1) Send current state immediately
        data = etl_progress_get()
        if not data:
            data = {"running": False}
        else:
            data = _check_stale_progress(data)
        yield f"data: {json.dumps(data)}\n\n"

        # 2) Subscribe to Redis Pub/Sub for real-time updates
        if not redis_client:
            return

        sub_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            decode_responses=True, socket_connect_timeout=5,
        )
        pubsub = sub_client.pubsub()
        pubsub.subscribe(ETL_PROGRESS_CHANNEL)

        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                msg = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg["type"] == "message":
                    payload = msg["data"]
                    parsed = json.loads(payload)
                    parsed = _check_stale_progress(parsed)
                    yield f"data: {json.dumps(parsed)}\n\n"
                else:
                    # Send keepalive comment every ~15s to prevent proxy timeouts
                    yield ": keepalive\n\n"

                await asyncio.sleep(0.5)
        finally:
            pubsub.unsubscribe(ETL_PROGRESS_CHANNEL)
            pubsub.close()
            sub_client.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/run-etl")
def run_etl(
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Trigger ETL process as background task (super-admin only)."""
    from .etl.config.settings import ETLConfig
    from .etl.etl_orchestrator import ETLOrchestrator
    import threading
    import time as _time

    # Check if already running
    progress = etl_progress_get()
    if progress and progress.get("running") and progress.get("phase") not in ("done", "error"):
        raise HTTPException(status_code=409, detail="ETL já está em execução")

    log = LogAcao(
        usuario_id=admin.id,
        acao="run_etl",
        detalhes={},
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    db.commit()

    # Set initial progress
    etl_progress_set({
        "running": True,
        "phase": "init",
        "step": "Inicializando ETL...",
        "percent": 0,
        "detail": "",
        "updated_at": _time.time(),
    })

    def _run_etl_bg():
        try:
            config = ETLConfig()
            etl = ETLOrchestrator(config)
            etl.run_complete_etl()
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"ETL background error: {e}")

    thread = threading.Thread(target=_run_etl_bg, daemon=True)
    thread.start()

    return {"status": "ETL iniciado em background"}


@router.post("/reindex")
def reindex(
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Recreate database indexes in background (super-admin only)."""
    from .etl.config.settings import ETLConfig, DatabaseConfig
    from .etl.database.manager import DatabaseManager
    import threading
    import time as _time

    # Check if ETL is running
    progress = etl_progress_get()
    if progress and progress.get("running") and progress.get("phase") not in ("done", "error"):
        raise HTTPException(status_code=409, detail="ETL em execução — aguarde para reindexar")

    log = LogAcao(
        usuario_id=admin.id,
        acao="reindex",
        detalhes={},
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    db.commit()

    etl_progress_set({
        "running": True,
        "phase": "index",
        "step": "Recriando índices...",
        "percent": 50,
        "detail": "",
        "updated_at": _time.time(),
    })

    def _reindex_bg():
        import logging
        logger = logging.getLogger(__name__)
        try:
            db_config = DatabaseConfig()
            manager = DatabaseManager(db_config)
            manager.initialize_connection()
            manager.create_optimized_indexes()
            etl_progress_set({
                "running": False,
                "phase": "done",
                "step": "Índices recriados com sucesso",
                "percent": 100,
                "detail": "",
                "updated_at": _time.time(),
            })
            logger.info("Reindex completed successfully")
        except Exception as e:
            logger.error(f"Reindex background error: {e}")
            etl_progress_set({
                "running": False,
                "phase": "error",
                "step": f"Erro ao reindexar: {e}",
                "percent": 0,
                "detail": str(e),
                "updated_at": _time.time(),
            })

    thread = threading.Thread(target=_reindex_bg, daemon=True)
    thread.start()

    return {"status": "Reindexação iniciada em background"}


@router.post("/clear-cache")
def clear_cache(
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Flush Redis cache."""
    count = cache_clear_all()

    log = LogAcao(
        usuario_id=admin.id,
        acao="clear_cache",
        ip_address=request.client.host if request.client else None,
    )
    db.add(log)
    db.commit()

    return {"status": "Cache limpo"}


# ─── Extraction Lookup ────────────────────────────────────

@router.get("/extractions/{file_id}")
def get_extraction_by_file_id(
    file_id: str,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """Look up an extraction (processed search) by its file_id."""
    historico = db.query(HistoricoBusca).filter(HistoricoBusca.file_id == file_id).first()
    if not historico:
        raise HTTPException(status_code=404, detail="Extração não encontrada")

    usuario = db.query(Usuario).filter(Usuario.id == historico.usuario_id).first()

    return {
        "file_id": historico.file_id,
        "search_id": historico.search_id,
        "status": historico.status,
        "total_results": historico.total_results,
        "quantidade_processada": historico.quantidade_processada,
        "credits_consumed": historico.credits_consumed,
        "created_at": historico.created_at.isoformat() if historico.created_at else None,
        "params": historico.params,
        "usuario": {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "role": usuario.role,
        } if usuario else None,
    }


@router.get("/extractions")
def search_extractions(
    q: str = Query("", description="Search by file_id, search_id or user email"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_super_admin),
):
    """List / search all queries (not only processed ones) with pagination."""
    query = db.query(HistoricoBusca)

    if q:
        # Try matching file_id, search_id, or join to user email
        query = query.outerjoin(Usuario, Usuario.id == HistoricoBusca.usuario_id).filter(
            (HistoricoBusca.file_id.ilike(f"%{q}%"))
            | (HistoricoBusca.search_id.ilike(f"%{q}%"))
            | (Usuario.email.ilike(f"%{q}%"))
            | (Usuario.nome.ilike(f"%{q}%"))
        )

    total = query.count()
    items = (
        query.order_by(HistoricoBusca.created_at.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    # Batch-load users to avoid N+1 queries
    user_ids = list({h.usuario_id for h in items})
    users_map = {}
    if user_ids:
        users = db.query(Usuario).filter(Usuario.id.in_(user_ids)).all()
        users_map = {u.id: u for u in users}

    results = []
    for h in items:
        usuario = users_map.get(h.usuario_id)
        results.append({
            "file_id": h.file_id,
            "search_id": h.search_id,
            "status": h.status,
            "total_results": h.total_results,
            "quantidade_processada": h.quantidade_processada,
            "credits_consumed": h.credits_consumed,
            "created_at": h.created_at.isoformat() if h.created_at else None,
            "params": h.params,
            "usuario": {
                "id": usuario.id,
                "nome": usuario.nome,
                "email": usuario.email,
            } if usuario else None,
        })

    return {"extractions": results, "total": total}
