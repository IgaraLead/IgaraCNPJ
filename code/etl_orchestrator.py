"""
Main ETL orchestrator for RFB data processing.
Coordinates all ETL operations following SOLID principles.
"""

import logging
import time
from typing import List
from config.settings import ETLConfig
from database.manager import DatabaseManager
from download.manager import FileDownloader, FileExtractor, RFBFileDiscovery
from processing.data_processor import FileClassifier, DataReader, ProcessorFactory


# Process each file type
processing_order = [
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


class ETLOrchestrator:
    """
    Main ETL orchestrator implementing single responsibility principle.
    Coordinates the entire ETL pipeline with proper error handling and logging.
    """

    def __init__(self, config: ETLConfig):
        self.config = config
        self._setup_logging()
        self._logger = logging.getLogger(__name__)

        # Initialize components
        self.database_manager = DatabaseManager(config.database)
        self.file_downloader = FileDownloader(
            max_workers=config.max_workers, max_retries=3, timeout=300
        )
        self.file_extractor = FileExtractor(max_workers=config.max_workers)
        self.file_discovery = RFBFileDiscovery(config.rfb_base_url)
        self.file_classifier = FileClassifier()
        self.data_reader = DataReader(batch_size=config.batch_size)

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

        try:
            # Phase 1: Download files
            self._logger.info("Phase 1: Discovering and downloading files")
            downloaded_files = self._download_phase()

            # Phase 2: Extract files
            self._logger.info("Phase 2: Extracting files")
            self._extract_phase(downloaded_files)

            # Phase 3: Process and load data
            self._logger.info("Phase 3: Processing and loading data")
            self._process_and_load_phase()

            # Phase 4: Create indexes
            self._logger.info("Phase 4: Creating database indexes")
            self._create_indexes_phase()

            end_time = time.time()
            total_time = end_time - start_time

            self._logger.info(
                f"ETL process completed successfully in {total_time:.2f} seconds "
                f"({total_time/60:.2f} minutes)"
            )

        except Exception as e:
            self._logger.error(f"ETL process failed: {e}")
            raise

    def _download_phase(self) -> List[str]:
        """
        Download phase: Discover and download RFB files.
        Returns list of downloaded file paths.
        """
        try:
            # Discover available files
            filenames = self.file_discovery.discover_zip_files()
            self._logger.info(f"Discovered {len(filenames)} files to download")

            # Create download tasks
            download_tasks = self.file_discovery.create_download_tasks(filenames)

            # Download files in parallel
            downloaded_files = self.file_downloader.download_files_parallel(
                download_tasks, self.config.output_files_path
            )

            self._logger.info(f"Successfully downloaded {len(downloaded_files)} files")
            return downloaded_files

        except Exception as e:
            self._logger.error(f"Download phase failed: {e}")
            raise

    def _extract_phase(self, downloaded_files: List[str]) -> None:
        """
        Extract phase: Extract all downloaded ZIP files.
        """
        try:
            successful_extractions = self.file_extractor.extract_all_files_parallel(
                downloaded_files, self.config.extracted_files_path
            )

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

            for file_type in processing_order:
                if classified_files[file_type]:
                    self._process_file_type(file_type, classified_files[file_type])

        except Exception as e:
            self._logger.error(f"Process and load phase failed: {e}")
            raise

    def _process_file_type(self, file_type: str, filenames: List[str]) -> None:
        """
        Process a specific file type and load to database.
        """
        self._logger.info(f"Processing {file_type} files: {len(filenames)} files")

        processor = ProcessorFactory.get_processor(file_type)
        processing_start = time.time()

        is_first_chunk = True
        for filename in filenames:
            file_path = f"{self.config.extracted_files_path}/{filename}"
            self._logger.info(f"Processing file: {filename}")

            try:
                # For large files (estabelecimento, simples), use chunked reading
                # if file_type in ["estabelecimento", "simples"]:
                self._process_large_file(
                    file_path, file_type, processor, is_first_chunk
                )
                # else:
                #     self._process_regular_file(file_path, file_type, processor)

                self._logger.info(f"Successfully processed {filename}")

            except Exception as e:
                self._logger.error(f"Error processing {filename}: {e}")
                raise
            finally:
                is_first_chunk = False

        processing_end = time.time()
        processing_time = processing_end - processing_start

        self._logger.info(
            f"Completed {file_type} processing in {processing_time:.2f} seconds"
        )

    def _process_large_file(
        self, file_path: str, table_name: str, processor, is_first_chunk: bool
    ) -> None:
        """
        Process large files using chunked reading and insertion.
        """
        chunk_count = 0
        for chunk in self.data_reader.read_file_in_chunks(file_path, processor):
            should_create_table = is_first_chunk and chunk_count == 0
            # For the first chunk, replace the table
            self.database_manager.optimized_bulk_insert(
                chunk,
                table_name,
                self.config.chunk_size,
                create_table=should_create_table,
            )

            chunk_count += 1
            self._logger.info(f"Processed chunk {chunk_count} for {table_name}")

    def _process_regular_file(self, file_path: str, table_name: str, processor) -> None:
        """
        Process regular-sized files.
        """
        dataframe = self.data_reader.read_simple_file(file_path, processor)
        self.database_manager.optimized_bulk_insert(
            dataframe, table_name, self.config.chunk_size
        )

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


def main():
    """
    Main entry point for the ETL process.
    """
    try:
        # Load configuration
        config = ETLConfig("D:\\sources\\RFB-_Dados_Publicos_CNPJ\\code\\.env")

        # Create and run ETL orchestrator
        etl = ETLOrchestrator(config)
        etl.run_complete_etl()

        print(
            """
Processo 100% finalizado! Você já pode usar seus dados no BD!
 - Desenvolvido por: Aphonso Henrique do Amaral Rafael
 - Melhorado com otimizações de performance e arquitetura
 - Contribua com esse projeto aqui: https://github.com/aphonsoar/Receita_Federal_do_Brasil_-_Dados_Publicos_CNPJ
        """
        )

    except Exception as e:
        logging.error(f"ETL process failed: {e}")
        raise


if __name__ == "__main__":
    main()
