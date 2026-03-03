"""
Export endpoints: async CSV/XLSX generation from search results.
"""

import os
import uuid
import json
import csv
import io
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from .database import get_db
from .auth import get_current_user
from .models import Usuario
from .credits import check_active_subscription
from .schemas import ExportRequest, ExportStatusOut
from .redis_queue import redis_client, enqueue_task, set_task_status, get_task_status

router = APIRouter(tags=["export"])

EXPORT_DIR = Path(os.getenv("EXPORT_DIR", "./exports"))
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

CHUNK_SIZE_EXPORTACAO = int(os.getenv("CHUNK_SIZE_EXPORTACAO", "10000"))


@router.post("/export", response_model=ExportStatusOut)
def request_export(
    params: ExportRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Request export of search results as CSV or XLSX.
    The export is queued and processed asynchronously.
    Credits were already consumed during the search.
    """
    check_active_subscription(db, current_user.id)

    if params.formato not in ("csv", "xlsx"):
        raise HTTPException(status_code=400, detail="Formato deve ser 'csv' ou 'xlsx'")

    task_id = str(uuid.uuid4())

    task_data = {
        "task_id": task_id,
        "user_id": current_user.id,
        "params": params.model_dump(),
        "type": "export",
    }

    # Store task status in Redis
    set_task_status(f"export:{task_id}", {"status": "processing", "user_id": current_user.id}, ttl=3600)

    # Enqueue the export task
    enqueue_task(task_data)

    return ExportStatusOut(task_id=task_id, status="processing")


@router.get("/export/{task_id}", response_model=ExportStatusOut)
def get_export_status(
    task_id: str,
    current_user: Usuario = Depends(get_current_user),
):
    """Check export task status and get download URL when ready."""
    data = get_task_status(f"export:{task_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada ou expirada")

    # Ownership check: ensure the export belongs to the requesting user
    if data.get("user_id") and data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")

    status = data.get("status", "processing")

    download_url = None
    if status == "ready":
        download_url = f"/export/download/{task_id}"

    return ExportStatusOut(task_id=task_id, status=status, download_url=download_url)


@router.get("/export/download/{task_id}")
def download_export(
    task_id: str,
    current_user: Usuario = Depends(get_current_user),
):
    """Download a completed export file."""
    data = get_task_status(f"export:{task_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada ou expirada")
    if data.get("user_id") and data["user_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Acesso negado")
    if data.get("status") != "ready":
        raise HTTPException(status_code=400, detail="Exportação ainda não finalizada")

    filename = data.get("filename", f"{task_id}.csv")
    filepath = EXPORT_DIR / filename

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    return FileResponse(
        path=str(filepath),
        filename=filename,
        media_type="application/octet-stream",
    )
