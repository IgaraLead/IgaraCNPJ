"""
Configuration management module for RFB ETL process.
Handles environment variables and application settings.
"""

import os
import pathlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Receita Federal Nextcloud share
RFB_SHARE_TOKEN = "gn672Ad4CF8N6TK"
RFB_HOST = "https://arquivos.receitafederal.gov.br"
RFB_WEBDAV_BASE = f"{RFB_HOST}/public.php/webdav/Dados/Cadastros/CNPJ"


class DatabaseConfig:
    """Database configuration class following dependency inversion principle."""

    def __init__(self):
        self.user = os.getenv("DB_USER")
        self.password = os.getenv("DB_PASSWORD")
        self.host = os.getenv("DB_HOST", "localhost")
        self.port = os.getenv("DB_PORT", "5432")
        self.database = os.getenv("DB_NAME")

    def get_connection_string(self) -> str:
        """Generate PostgreSQL connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    def get_psycopg2_params(self) -> dict:
        """Generate psycopg2 connection parameters."""
        return {
            "dbname": self.database,
            "user": self.user,
            "host": self.host,
            "port": self.port,
            "password": self.password,
        }


class ETLConfig:
    """Configuration class for ETL process with environment variable support."""

    def __init__(self, env_path: Optional[str] = None):
        self.current_path = pathlib.Path().resolve()
        self._load_environment(env_path)
        self.database = DatabaseConfig()

        # File paths
        self.output_files_path = self._ensure_directory(os.getenv("OUTPUT_FILES_PATH"))
        self.extracted_files_path = self._ensure_directory(
            os.getenv("EXTRACTED_FILES_PATH")
        )

        # RFB Nextcloud WebDAV configuration
        self.rfb_share_token = os.getenv("RFB_SHARE_TOKEN", RFB_SHARE_TOKEN)
        self.rfb_webdav_base = os.getenv("RFB_WEBDAV_BASE", RFB_WEBDAV_BASE)

        # Auto-detect files_date: current month, fallback to previous
        self.files_date = self._resolve_files_date()
        self.rfb_base_url = f"{self.rfb_webdav_base}/{self.files_date}/"

        # Performance settings
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "4096"))
        self.batch_size = int(os.getenv("BATCH_SIZE", "2000000"))
        self.max_workers = int(os.getenv("MAX_WORKERS", "4"))

        # Processing order configuration
        self.processing_config = self._load_processing_config()

    def _resolve_files_date(self) -> str:
        """
        Determine which month/year to use for RFB data.
        1. If FILES_DATE env is set, use it directly.
        2. Otherwise, try current month via WebDAV PROPFIND.
        3. If current month doesn't exist, fall back to previous month.
        """
        manual = os.getenv("FILES_DATE", "").strip()
        if manual:
            logger.info(f"Using manually configured FILES_DATE: {manual}")
            return manual

        import urllib.request
        import xml.etree.ElementTree as ET

        now = datetime.now()
        candidates = [
            now.strftime("%Y-%m"),
            (now.replace(day=1) - timedelta(days=1)).strftime("%Y-%m"),
        ]

        for date_str in candidates:
            url = f"{self.rfb_webdav_base}/{date_str}/"
            logger.info(f"Checking RFB data availability for {date_str}...")
            try:
                req = urllib.request.Request(url, method="PROPFIND")
                req.add_header("Depth", "0")
                auth = __import__("base64").b64encode(
                    f"{self.rfb_share_token}:".encode()
                ).decode()
                req.add_header("Authorization", f"Basic {auth}")
                resp = urllib.request.urlopen(req, timeout=15)
                if resp.status == 207:  # Multi-Status = exists
                    logger.info(f"Found RFB data for {date_str}")
                    return date_str
            except Exception as e:
                logger.warning(f"RFB data not available for {date_str}: {e}")
                continue

        raise RuntimeError(
            f"No RFB data found for {candidates[0]} or {candidates[1]}. "
            "Set FILES_DATE manually in .env if needed."
        )

    def _load_environment(self, env_path: Optional[str] = None) -> None:
        """Load environment variables from .env file."""
        if env_path:
            dotenv_path = env_path
        else:
            dotenv_path = os.path.join(self.current_path, ".env")

        if os.path.isfile(dotenv_path):
            print(f"Loading environment from: {dotenv_path}")
            load_dotenv(dotenv_path=dotenv_path)
        elif os.getenv("DB_NAME"):
            # Environment variables already available (e.g. Docker env_file)
            print("Using existing environment variables (no .env file needed)")
        else:
            raise RuntimeError(
                "No .env file found and required environment variables are not set. "
                "Either provide a .env file or set DB_NAME, DB_USER, DB_PASSWORD, etc."
            )

    def _ensure_directory(self, path: Optional[str]) -> Optional[str]:
        """Create directory if it doesn't exist."""
        if path and not os.path.exists(path):
            os.makedirs(path)
        return path

    def _load_processing_config(self) -> Dict[str, bool]:
        """
        Load processing configuration from environment variables.
        Default is True for all file types if not specified.
        """
        default_processing_order = [
            "cnae",
            "moti",
            "munic",
            "natju",
            "pais",
            "quals",  # Reference data first
            "empresa",
            "estabelecimento",
            "socios",
            "simples",  # Main data tables
        ]

        processing_config = {}

        for file_type in default_processing_order:
            env_var = f"PROCESS_{file_type.upper()}"
            # Default to True if not specified, convert string to boolean
            value = os.getenv(env_var, "true").lower()
            processing_config[file_type] = value in ("true", "1", "yes", "on")

        return processing_config

    def get_enabled_processing_order(self) -> List[str]:
        """
        Get the list of file types that should be processed (enabled = True).
        """
        return [
            file_type
            for file_type, enabled in self.processing_config.items()
            if enabled
        ]

    def is_processing_enabled(self, file_type: str) -> bool:
        """
        Check if processing is enabled for a specific file type.
        """
        return self.processing_config.get(file_type, True)  # Default to True
