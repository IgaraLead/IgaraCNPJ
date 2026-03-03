"""
Utility functions for the CNPJ platform.
"""

import os
import logging

from .database import SessionLocal
from .models import Usuario, Credito

logger = logging.getLogger(__name__)


def create_first_superadmin():
    """Create the initial super-admin user if none exists."""
    db = SessionLocal()
    try:
        existing = db.query(Usuario).filter(Usuario.role == "super_admin").first()
        if existing:
            logger.info(f"Super-admin já existe: {existing.email}")
            return

        # Lazy import to avoid circular dependency
        from .auth import hash_password

        admin = Usuario(
            nome=os.getenv("ADMIN_NAME", "Administrador"),
            email=os.getenv("ADMIN_EMAIL", "admin@seudominio.com"),
            senha_hash=hash_password(os.getenv("ADMIN_PASSWORD", "s3nh@F0rt3!")),
            telefone=os.getenv("ADMIN_PHONE"),
            role="super_admin",
            ativo=True,
        )
        db.add(admin)
        db.flush()

        credito = Credito(usuario_id=admin.id, saldo=0)
        db.add(credito)
        db.commit()

        logger.info(f"Super-admin criado: {admin.email}")
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao criar super-admin: {e}")
    finally:
        db.close()
