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

from .database import engine, Base
from .auth import router as auth_router
from .plans import router as plans_router
from .credits import router as credits_router
from .search import router as search_router
from .export import router as export_router
from .admin import router as admin_router
from .pagseguro import router as pagseguro_router
from .utils import create_first_superadmin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    logger.info("Starting CNPJ Platform API...")
    # Create tables if they don't exist (dev convenience)
    Base.metadata.create_all(bind=engine)
    create_first_superadmin()
    logger.info("API ready.")
    yield
    logger.info("Shutting down API...")


app = FastAPI(
    title="Plataforma CNPJ - igarateca",
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
app.include_router(plans_router)
app.include_router(credits_router)
app.include_router(search_router)
app.include_router(export_router)
app.include_router(admin_router)
app.include_router(pagseguro_router)


@app.get("/")
def root():
    return {"message": "API da Plataforma CNPJ - OK", "version": "1.0.0"}


@app.get("/health")
def health_check():
    return {"status": "healthy"}
