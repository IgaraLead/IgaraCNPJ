"""
Main FastAPI application entry point.
Configures CORS, lifespan events, and includes all routers.
"""

import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import engine, Base, SessionLocal
from .auth import router as auth_router
from .credits import router as credits_router
from .search import router as search_router
from .export import router as export_router
from .admin import router as admin_router
from .integrations import router as integrations_router
from .metrics import router as metrics_router
from .utils import create_first_superadmin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def _run_column_migrations():
    """Add columns that may be missing on existing tables (idempotent)."""
    from sqlalchemy import text
    stmts = [
        "ALTER TABLE historico_buscas ADD COLUMN IF NOT EXISTS file_id VARCHAR(36)",
        "ALTER TABLE historico_buscas ADD COLUMN IF NOT EXISTS quantidade_processada INT",
    ]
    db = SessionLocal()
    try:
        for sql in stmts:
            db.execute(text(sql))
        db.commit()
        logger.info("Column migrations applied successfully.")
    except Exception as e:
        db.rollback()
        logger.warning("Column migrations skipped (table may not exist yet): %s", e)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Starting IgaraLead Entity API...")
    # Create tables if they don't exist (dev convenience)
    Base.metadata.create_all(bind=engine)
    # Add columns that may be missing on existing tables (idempotent)
    _run_column_migrations()
    create_first_superadmin()
    logger.info("API ready.")
    yield
    logger.info("Shutting down API...")


app = FastAPI(
    title="IgaraLead Entity",
    description="API para consulta de dados CNPJ da Receita Federal",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth_router)
app.include_router(credits_router)
app.include_router(search_router)
app.include_router(export_router)
app.include_router(admin_router)
app.include_router(integrations_router)
app.include_router(metrics_router)


@app.get("/")
def root():
    return {"message": "IgaraLead Entity API - OK", "version": "1.0.0"}


@app.get("/health")
def health_check():
    checks = {"api": "ok"}
    try:
        db = SessionLocal()
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
        db.close()
    except Exception:
        checks["database"] = "error"
    overall = all(v == "ok" for v in checks.values())
    return {"status": "ok" if overall else "degraded", "checks": checks}
