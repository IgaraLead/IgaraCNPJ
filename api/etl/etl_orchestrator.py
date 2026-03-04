"""
Main ETL orchestrator for RFB data processing.
Coordinates all ETL operations following SOLID principles.
"""

import logging
from os import path
import os
import time
from typing import List
from .config.settings import ETLConfig
from .database.manager import DatabaseManager
from .download.manager import FileDownloader, FileExtractor, RFBFileDiscovery
from .processing.data_processor import FileClassifier, DataReader, ProcessorFactory


def _progress_update(phase: str, step: str, percent: float, detail: str = ""):
    """Push ETL progress to Redis (best-effort, never raises)."""
    try:
        from ..redis_queue import etl_progress_set
        etl_progress_set({
            "running": True,
            "phase": phase,
            "step": step,
            "percent": round(percent, 1),
            "detail": detail,
            "updated_at": time.time(),
        })
    except Exception:
        pass


class ETLOrchestrator:
    """
    Main ETL orchestrator implementing single responsibility principle.
    Coordinates the entire ETL pipeline with proper error handling and logging.
    """

    def __init__(self, config: ETLConfig):
        self.config = config
        self._setup_logging()
        self._logger = logging.getLogger(__name__)

        # Build auth headers for Nextcloud WebDAV downloads
        import base64
        auth = "Basic " + base64.b64encode(
            f"{config.rfb_share_token}:".encode()
        ).decode()
        auth_headers = {"Authorization": auth}

        # Initialize components
        self.database_manager = DatabaseManager(config.database)
        self.file_downloader = FileDownloader(
            max_workers=config.max_workers, max_retries=3, timeout=300,
            auth_headers=auth_headers
        )
        self.file_extractor = FileExtractor(max_workers=config.max_workers)
        self.file_discovery = RFBFileDiscovery(config.rfb_base_url, config.rfb_share_token)
        self.file_classifier = FileClassifier()
        self.data_reader = DataReader(batch_size=config.batch_size)

        # Get processing order from config
        self.processing_order = config.get_enabled_processing_order()
        self._logger.info(f"Processing order configured: {self.processing_order}")

    def _setup_logging(self) -> None:
        """Configure logging for the ETL process."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("etl_process.log"), logging.StreamHandler()],
        )

    def run_complete_etl(self) -> None:
        """
        Execute the complete ETL pipeline.
        """
        start_time = time.time()
        self._logger.info("Starting RFB ETL process")

        # Log processing configuration
        self._log_processing_configuration()

        try:
            # Phase 1: Download files
            _progress_update("download", "Iniciando downloads...", 0)
            self._logger.info("Phase 1: Discovering and downloading files")
            downloaded_files = self._download_phase()

            # Phase 2: Extract files
            _progress_update("extract", "Extraindo arquivos...", 25)
            self._logger.info("Phase 2: Extracting files")
            self._extract_phase(downloaded_files)

            # Phase 3: Process and load data
            _progress_update("process", "Processando dados...", 40)
            self._logger.info("Phase 3: Processing and loading data")
            self._process_and_load_phase()

            # Phase 4: Create indexes
            _progress_update("index", "Criando índices...", 95)
            self._logger.info("Phase 4: Creating database indexes")
            self._create_indexes_phase()

            end_time = time.time()
            total_time = end_time - start_time

            _progress_update("done", "Concluído!", 100,
                             f"Tempo total: {total_time/60:.1f} min")

            self._logger.info(
                f"ETL process completed successfully in {total_time:.2f} seconds "
                f"({total_time/60:.2f} minutes)"
            )

        except Exception as e:
            _progress_update("error", "Falha no ETL", -1, str(e)[:200])
            self._logger.error(f"ETL process failed: {e}")
            raise

    def _log_processing_configuration(self) -> None:
        """Log the current processing configuration."""
        self._logger.info("Processing Configuration:")
        for file_type, enabled in self.config.processing_config.items():
            status = "ENABLED" if enabled else "DISABLED"
            self._logger.info(f"  {file_type.upper()}: {status}")

    def _download_progress_cb(self, total_files: int):
        """Return a callback for download_files_parallel to report per-file progress."""
        def cb(completed: int, filename: str):
            pct = 5 + (completed / max(total_files, 1)) * 20  # 5% → 25%
            _progress_update("download", f"Baixando {filename}", pct,
                             f"{completed}/{total_files}")
        return cb

    def _download_phase(self) -> List[str]:
        """
        Download phase: Discover and download RFB files.
        Returns list of downloaded file paths.
        """
        try:
            # Discover available files
            filenames = self.file_discovery.discover_zip_files()
            self._logger.info(f"Discovered {len(filenames)} files to download")
            _progress_update("download", "Descobrindo arquivos...", 2,
                             f"{len(filenames)} arquivos encontrados")

            # Filter files based on processing configuration
            filtered_filenames = self._filter_files_by_config(filenames)
            self._logger.info(
                f"Filtered to {len(filtered_filenames)} files based on configuration"
            )

            # Create download tasks
            download_tasks = self.file_discovery.create_download_tasks(
                filtered_filenames
            )

            # Download files in parallel
            _progress_update("download", "Baixando arquivos...", 5,
                             f"0/{len(filtered_filenames)}")
            downloaded_files = self.file_downloader.download_files_parallel(
                download_tasks, self.config.output_files_path,
                progress_callback=self._download_progress_cb(len(filtered_filenames)),
            )

            self._logger.info(f"Successfully downloaded {len(downloaded_files)} files")
            return downloaded_files

        except Exception as e:
            self._logger.error(f"Download phase failed: {e}")
            raise

    def _filter_files_by_config(self, filenames: List[str]) -> List[str]:
        """
        Filter filenames based on processing configuration.
        Only include files for enabled file types.
        """
        filtered_files = []

        for filename in filenames:
            # Determine file type from filename
            file_type = self._determine_file_type_from_name(filename)

            if file_type and self.config.is_processing_enabled(file_type):
                filtered_files.append(filename)
            elif file_type:
                self._logger.info(
                    f"Skipping {filename} - {file_type.upper()} processing is disabled"
                )

        return filtered_files

    def _determine_file_type_from_name(self, filename: str) -> str:
        """
        Determine file type from filename.
        """
        filename_lower = filename.lower()

        # Map filename patterns to file types
        file_type_patterns = {
            "cnae": ["cnae"],
            "moti": ["moti"],
            "munic": ["munic"],
            "natju": ["natju"],
            "pais": ["pais"],
            "quals": ["quals"],
            "empresa": ["empresa", "emprecsv"],
            "estabelecimento": ["estabele"],
            "socios": ["socio"],
            "simples": ["simples"],
        }

        for file_type, patterns in file_type_patterns.items():
            if any(pattern in filename_lower for pattern in patterns):
                return file_type

        return None

    def _extract_phase(self, downloaded_files: List[str]) -> None:
        """
        Extract phase: Extract all downloaded ZIP files.
        """
        try:
            total = len(downloaded_files)
            _progress_update("extract", "Extraindo arquivos...", 25,
                             f"0/{total}")
            successful_extractions = self.file_extractor.extract_all_files_parallel(
                downloaded_files, self.config.extracted_files_path
            )
            _progress_update("extract", "Extração concluída", 40,
                             f"{successful_extractions}/{total}")

            self._logger.info(f"Successfully extracted {successful_extractions} files")

        except Exception as e:
            self._logger.error(f"Extract phase failed: {e}")
            raise

    def _process_and_load_phase(self) -> None:
        """
        Process and load phase: Classify files, process data, and load to database.
        """
        try:
            # Initialize database connection
            self.database_manager.initialize_connection()

            # Classify extracted files
            classified_files = self.file_classifier.classify_files(
                self.config.extracted_files_path
            )

            # Process only enabled file types in the configured order
            total_types = len(self.processing_order)
            for idx, file_type in enumerate(self.processing_order):
                pct = 40 + (idx / max(total_types, 1)) * 55  # 40% → 95%
                if classified_files.get(file_type):
                    _progress_update("process", f"Processando {file_type.upper()}...",
                                     pct, f"{idx+1}/{total_types}")
                    self._process_file_type(file_type, classified_files[file_type])
                else:
                    self._logger.info(f"No files found for {file_type.upper()}")

        except Exception as e:
            self._logger.error(f"Process and load phase failed: {e}")
            raise

    def _process_file_type(self, file_type: str, filenames: List[str]) -> None:
        """
        Process a specific file type and load to database.
        """
        if not self.config.is_processing_enabled(file_type):
            self._logger.info(f"Skipping {file_type.upper()} - processing disabled")
            return

        self._logger.info(
            f"Processing {file_type.upper()} files: {len(filenames)} files"
        )

        processor = ProcessorFactory.get_processor(file_type)
        processing_start = time.time()

        for filename in filenames:
            file_path = f"{self.config.extracted_files_path}/{filename}"
            self._logger.info(f"Processing file: {filename}")

            try:
                self._process_large_file(file_path, file_type, processor)
                self._logger.info(f"Successfully processed {filename}")

            except Exception as e:
                self._logger.error(f"Error processing {filename}: {e}")
                raise

        processing_end = time.time()
        processing_time = processing_end - processing_start

        self._logger.info(
            f"Completed {file_type.upper()} processing in {processing_time:.2f} seconds"
        )

    def _process_large_file(
        self, file_path: str, table_name: str, processor
    ) -> None:
        """
        Process large files using chunked reading and upsert insertion.
        """
        chunk_count = 0
        for chunk in self.data_reader.read_file_in_chunks(file_path, processor):
            self.database_manager.optimized_bulk_insert(
                chunk,
                table_name,
                self.config.chunk_size,
            )

            chunk_count += 1
            self._logger.info(f"Processed chunk {chunk_count} for {table_name}")

    def _create_indexes_phase(self) -> None:
        """
        Create database indexes for optimized query performance.
        """
        try:
            self.database_manager.create_optimized_indexes()
            self._logger.info("Database indexes created successfully")

        except Exception as e:
            self._logger.error(f"Index creation failed: {e}")
            raise

    def run_download_only(self) -> None:
        """Run only the download phase (useful for testing or partial runs)."""
        self._logger.info("Running download-only mode")
        self._download_phase()

    def run_from_extracted(self) -> None:
        """Run from extracted files (skip download and extract phases)."""
        self._logger.info("Running from extracted files")
        self._process_and_load_phase()
        self._create_indexes_phase()

    def run_recreate_etl(self) -> None:
        """
        Execute ETL pipeline in RECREATE mode: drops all RFB data tables
        and recreates them from scratch before importing.
        """
        start_time = time.time()
        self._logger.info("Starting RFB ETL process (RECREATE mode)")
        self._log_processing_configuration()

        try:
            # Phase 0: Drop and recreate tables
            _progress_update("recreate", "Recriando banco de dados...", 0,
                             "Removendo tabelas existentes")
            self._logger.info("Phase 0: Dropping and recreating tables")
            self._recreate_tables()

            # Phase 1: Download files
            _progress_update("download", "Iniciando downloads...", 5)
            self._logger.info("Phase 1: Discovering and downloading files")
            downloaded_files = self._download_phase()

            # Phase 2: Extract files
            _progress_update("extract", "Extraindo arquivos...", 25)
            self._logger.info("Phase 2: Extracting files")
            self._extract_phase(downloaded_files)

            # Phase 3: Process and load data
            _progress_update("process", "Processando dados...", 40)
            self._logger.info("Phase 3: Processing and loading data")
            self._process_and_load_phase()

            # Phase 4: Create indexes
            _progress_update("index", "Criando índices...", 95)
            self._logger.info("Phase 4: Creating database indexes")
            self._create_indexes_phase()

            end_time = time.time()
            total_time = end_time - start_time

            _progress_update("done", "Concluído!", 100,
                             f"Tempo total: {total_time/60:.1f} min (modo recriação)")

            self._logger.info(
                f"ETL RECREATE process completed in {total_time:.2f} seconds "
                f"({total_time/60:.2f} minutes)"
            )

        except Exception as e:
            _progress_update("error", "Falha no ETL", -1, str(e)[:200])
            self._logger.error(f"ETL RECREATE process failed: {e}")
            raise

    def _recreate_tables(self) -> None:
        """Drop all RFB data tables and recreate them empty."""
        tables = [
            "empresa", "estabelecimento", "socios", "simples",
            "cnae", "moti", "munic", "natju", "pais", "quals",
        ]
        self.database_manager.initialize_connection()
        with self.database_manager.get_connection() as conn:
            with conn.cursor() as cur:
                for tbl in tables:
                    self._logger.info(f"Dropping table {tbl}")
                    cur.execute(f"DROP TABLE IF EXISTS {tbl} CASCADE")
                conn.commit()
        self._logger.info("All RFB tables dropped. They will be recreated during processing.")


def main():
    """
    Main entry point for the ETL process.
    """
    try:
        # Load configuration
        env_path = path.join(os.getcwd(), "code", ".env")
        config = ETLConfig(env_path)

        # Create and run ETL orchestrator
        etl = ETLOrchestrator(config)
        etl.run_complete_etl()

        print(
            """
Processo 100% finalizado! Você já pode usar seus dados no BD!
 - Desenvolvido por: Judson Cairo (HEROw Code)
 - Melhorado com otimizações de performance e arquitetura
 - Contribua com esse projeto aqui: https://github.com/judsonjuniorr/Receita_Federal_do_Brasil_-_Dados_Publicos_CNPJ
        """
        )

    except Exception as e:
        logging.error(f"ETL process failed: {e}")
        raise


if __name__ == "__main__":
    main()
