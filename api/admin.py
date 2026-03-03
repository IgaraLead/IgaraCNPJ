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
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from .database import get_db
from .auth import require_super_admin, get_current_user
from .models import (
    Usuario, Credito, CreditoTransacao, Assinatura,
    LogAcao, ConfigSistema,
)
from .schemas import (
    AjusteCreditos, ToggleUF, ToggleQueue, LogAcaoOut, StatsOut,
)
from .redis_queue import (
    redis_client, get_queue_size, cache_clear_all,
    etl_progress_get, etl_progress_set,
    ETL_PROGRESS_CHANNEL, REDIS_HOST, REDIS_PORT, REDIS_DB,
)

router = APIRouter(prefix="/admin", tags=["admin"])

LIMITE_CREDITOS_MAXIMO = int(os.getenv("LIMITE_CREDITOS_MAXIMO", "100000"))


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
    if user.role == "super_admin":
        raise HTTPException(status_code=400, detail="Não é possível bloquear um super-admin")

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

    return {
        "users": [
            {
                "id": u.id,
                "nome": u.nome,
                "email": u.email,
                "role": u.role,
                "ativo": u.ativo,
                "criado_em": str(u.criado_em),
            }
            for u in users
        ],
        "total": total,
        "page": page,
        "limit": limit,
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
