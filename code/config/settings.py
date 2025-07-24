"""
Configuration management module for RFB ETL process.
Handles environment variables and application settings.
"""

import os
import pathlib
from typing import Optional
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
    """Main ETL configuration class."""

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
        self.rfb_base_url = f"https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/{os.getenv("FILES_DATE")}/"

        # Performance settings
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "4096"))
        self.batch_size = int(os.getenv("BATCH_SIZE", "2000000"))
        self.max_workers = int(os.getenv("MAX_WORKERS", "4"))

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
