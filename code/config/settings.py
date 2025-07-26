"""
Configuration management module for RFB ETL process.
Handles environment variables and application settings.
"""

import os
import pathlib
from typing import Dict, List, Optional
from dotenv import load_dotenv


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

        # URLs and constants
        files_date = os.getenv("FILES_DATE")
        if not files_date:
            raise ValueError("FILES_DATE environment variable is not set. Please set it in your environment or .env file.")
        self.rfb_base_url = f"https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/{files_date}/"

        # Performance settings
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "4096"))
        self.batch_size = int(os.getenv("BATCH_SIZE", "2000000"))
        self.max_workers = int(os.getenv("MAX_WORKERS", "4"))

        # Processing order configuration
        self.processing_config = self._load_processing_config()

    def _load_environment(self, env_path: Optional[str] = None) -> None:
        """Load environment variables from .env file."""
        if env_path:
            dotenv_path = env_path
        else:
            dotenv_path = os.path.join(self.current_path, ".env")

        if not os.path.isfile(dotenv_path):
            print(
                'Especifique o local do seu arquivo de configuração ".env". '
                "Por exemplo: C:\\...\\Receita_Federal_do_Brasil_-_Dados_Publicos_CNPJ\\code"
            )
            local_env = input()
            dotenv_path = os.path.join(local_env, ".env")

        print(f"Loading environment from: {dotenv_path}")
        load_dotenv(dotenv_path=dotenv_path)

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
