"""
Database management module for RFB ETL process.
Handles database connections, schema creation, and optimized data insertion.
"""

import logging
import time
import io
import threading
from contextlib import contextmanager
from typing import Dict
import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from config.settings import DatabaseConfig


class DatabaseInsertProgressTracker:
    """Progress tracker for database insertions."""

    def __init__(self):
        self._lock = threading.Lock()
        self._current_table = ""
        self._total_rows = 0
        self._processed_rows = 0
        self._start_time = 0
        self._chunk_count = 0

    def start_tracking(self, table_name: str, total_rows: int):
        """Start tracking progress for a table."""
        with self._lock:
            self._current_table = table_name
            self._total_rows = total_rows
            self._processed_rows = 0
            self._start_time = time.time()
            self._chunk_count = 0

    def update_progress(self, processed_rows: int):
        """Update progress."""
        with self._lock:
            self._processed_rows = processed_rows
            self._chunk_count += 1

    def get_progress_info(self) -> Dict:
        """Get current progress information."""
        with self._lock:
            elapsed = time.time() - self._start_time if self._start_time > 0 else 0
            rate = self._processed_rows / elapsed if elapsed > 0 else 0
            progress = (
                (self._processed_rows / self._total_rows * 100)
                if self._total_rows > 0
                else 0
            )

            return {
                "table": self._current_table,
                "total_rows": self._total_rows,
                "processed_rows": self._processed_rows,
                "progress_percent": progress,
                "rate_per_sec": rate,
                "elapsed_time": elapsed,
                "chunk_count": self._chunk_count,
            }


class DatabaseManager:
    """
    Database manager implementing single responsibility and dependency inversion principles.
    Handles all database operations with optimizations for large datasets (22M+ records).
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.engine: Engine = None
        self._logger = logging.getLogger(__name__)
        self._progress_tracker = DatabaseInsertProgressTracker()

    def initialize_connection(self) -> None:
        """Initialize database connection with connection pooling optimized for large datasets."""
        try:
            self.engine = create_engine(
                self.config.get_connection_string(),
                pool_size=20,  # Increased for large operations
                max_overflow=40,  # Increased overflow
                pool_pre_ping=True,
                pool_recycle=1800,  # Shorter recycle time
                # Remove shared_buffers - it's a server-level parameter
                connect_args={
                    "options": "-c work_mem=256MB -c maintenance_work_mem=2GB"
                },
            )
            self._logger.info("Database connection initialized successfully")

            # Set session-level optimizations
            with self.engine.connect() as conn:
                conn.execute(text("SET synchronous_commit = off"))
                conn.commit()

        except Exception as e:
            self._logger.error(f"Failed to initialize database connection: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """Context manager for database connections with large dataset optimizations."""
        conn = None
        try:
            conn = psycopg2.connect(
                **self.config.get_psycopg2_params(),
                # Optimizations for large datasets
                options="-c work_mem=512MB -c maintenance_work_mem=2GB",
            )
            conn.autocommit = False
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            self._logger.error(f"Database connection error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def optimized_bulk_insert(
        self,
        dataframe: pd.DataFrame,
        table_name: str,
        chunk_size: int = 50000,
        create_table: bool = True,
    ) -> None:
        """
        Optimized bulk insert method for large datasets using COPY with progress tracking.
        """
        if dataframe.empty:
            self._logger.warning(f"Empty dataframe provided for table {table_name}")
            return

        total_rows = len(dataframe)
        self._logger.info(
            f"Starting optimized bulk insert of {total_rows:,} rows into {table_name}"
        )

        # Get table schema
        schema = self._get_table_schema(table_name)

        # Create table with optimizations
        if create_table:
            self.create_table_with_schema(table_name, schema)
        self.optimize_table_for_bulk_insert(table_name)

        # Start progress tracking
        self._progress_tracker.start_tracking(table_name, total_rows)

        start_time = time.time()
        processed_rows = 0

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Process in chunks
                    for i in range(0, total_rows, chunk_size):
                        chunk_start_time = time.time()
                        chunk = dataframe.iloc[i : i + chunk_size]

                        # Clean the data and handle semicolon-separated CSV format
                        chunk_cleaned = self._prepare_chunk_for_insert(chunk, schema)

                        # Use StringIO for COPY FROM with proper formatting
                        output = io.StringIO()

                        # Custom CSV writing to ensure all columns are present and properly formatted
                        rows = []
                        for _, row in chunk_cleaned.iterrows():
                            csv_row = []
                            for col, dtype in schema.items():
                                # Ensure we always get a value for every column in the schema
                                if col in row.index:
                                    value = row[col]
                                else:
                                    value = None
                                    self._logger.debug(
                                        f"Missing column {col} in row, using NULL"
                                    )

                                if pd.isna(value) or value is None or value == "":
                                    csv_row.append("\\N")
                                elif "INTEGER" in dtype:
                                    try:
                                        # Ensure integers are written as integers, not floats
                                        if (
                                            isinstance(value, str)
                                            and value.strip() == ""
                                        ):
                                            csv_row.append("\\N")
                                        else:
                                            int_value = int(float(value))
                                            csv_row.append(str(int_value))
                                    except (ValueError, TypeError):
                                        csv_row.append("\\N")
                                elif "DECIMAL" in dtype:
                                    try:
                                        if (
                                            isinstance(value, str)
                                            and value.strip() == ""
                                        ):
                                            csv_row.append("\\N")
                                        else:
                                            # Handle Brazilian decimal format
                                            str_val = str(value).replace(",", ".")
                                            decimal_value = float(str_val)
                                            csv_row.append(str(decimal_value))
                                    except (ValueError, TypeError):
                                        csv_row.append("\\N")
                                else:
                                    # Text fields - clean and escape
                                    str_value = str(value) if value is not None else ""
                                    if str_value == "nan":
                                        str_value = ""
                                    str_value = (
                                        str_value.replace("\t", " ")
                                        .replace("\n", " ")
                                        .replace("\r", " ")
                                        .replace("\\", "\\\\")  # Escape backslashes
                                    )
                                    csv_row.append(str_value)

                            # Ensure we have exactly the right number of columns
                            if len(csv_row) != len(schema):
                                self._logger.warning(
                                    f"Row has {len(csv_row)} columns, expected {len(schema)}. Padding with NULLs."
                                )
                                while len(csv_row) < len(schema):
                                    csv_row.append("\\N")
                                csv_row = csv_row[: len(schema)]  # Truncate if too many

                            rows.append("\t".join(csv_row))

                        output.write("\n".join(rows))
                        if rows:  # Add final newline if there are rows
                            output.write("\n")
                        output.seek(0)

                        # Use COPY for maximum speed
                        try:
                            cur.copy_from(
                                output,
                                table_name,
                                columns=list(schema.keys()),
                                sep="\t",
                                null="\\N",
                            )
                        except Exception as copy_error:
                            self._logger.error(
                                f"COPY error for chunk {i//chunk_size + 1}: {copy_error}"
                            )

                            # Log detailed debug information
                            self._logger.error(f"Schema: {schema}")
                            self._logger.error(f"Schema columns count: {len(schema)}")
                            self._logger.error(
                                f"Chunk columns: {list(chunk_cleaned.columns)}"
                            )
                            self._logger.error(
                                f"Chunk columns count: {len(chunk_cleaned.columns)}"
                            )

                            # Log sample of problematic data
                            output.seek(0)
                            sample_lines = output.read().split("\n")[:5]
                            self._logger.error("Sample CSV lines:")
                            for idx, line in enumerate(sample_lines):
                                if line.strip():  # Only log non-empty lines
                                    col_count = len(line.split("\t"))
                                    self._logger.error(
                                        f"Line {idx + 1} ({col_count} cols): {repr(line)}"
                                    )

                            # Log sample of cleaned dataframe with dtypes
                            self._logger.debug(
                                f"Cleaned chunk dtypes:\n{chunk_cleaned.dtypes}"
                            )
                            self._logger.debug("Sample values from problematic chunk:")
                            for col in chunk_cleaned.columns:
                                sample_vals = chunk_cleaned[col].head(3).tolist()
                                self._logger.debug(f"Column {col}: {sample_vals}")

                            raise

                        processed_rows += len(chunk)

                        # Update progress tracker
                        self._progress_tracker.update_progress(processed_rows)

                        # Commit every 10 chunks
                        if (i // chunk_size) % 10 == 0:
                            conn.commit()

                        # Log progress with detailed information
                        chunk_time = time.time() - chunk_start_time
                        chunk_rate = len(chunk) / chunk_time if chunk_time > 0 else 0

                        if (
                            processed_rows % 100000 == 0
                            or processed_rows == total_rows
                            or (i // chunk_size) % 5 == 0
                        ):  # Log every 5 chunks or 100k rows

                            progress_info = self._progress_tracker.get_progress_info()
                            self._logger.info(
                                f"PROGRESS {table_name}: Chunk {progress_info['chunk_count']:>3} | "
                                f"{progress_info['progress_percent']:>5.1f}% | "
                                f"{progress_info['processed_rows']:>8,}/{progress_info['total_rows']:,} rows | "
                                f"Rate: {progress_info['rate_per_sec']:>7,.0f} rows/sec | "
                                f"Chunk: {chunk_rate:>6,.0f} rows/sec | "
                                f"Elapsed: {progress_info['elapsed_time']:>6.1f}s"
                            )

                conn.commit()

                # Final progress log
                progress_info = self._progress_tracker.get_progress_info()
                self._logger.info(
                    f"SUCCESS {table_name}: INSERT COMPLETED | "
                    f"{progress_info['processed_rows']:,} rows | "
                    f"Avg Rate: {progress_info['rate_per_sec']:,.0f} rows/sec | "
                    f"Total Time: {progress_info['elapsed_time']:.1f}s"
                )

        except Exception as e:
            self._logger.error(f"ERROR during bulk insert for {table_name}: {e}")
            # Log more detailed error information
            import traceback

            self._logger.error(f"Full traceback: {traceback.format_exc()}")
            raise

        # Finalize table
        self._logger.info(f"FINALIZING table {table_name}...")
        self.finalize_table_after_bulk_insert(table_name)

        end_time = time.time()
        duration = end_time - start_time
        rate = total_rows / duration if duration > 0 else 0

        self._logger.info(
            f"COMPLETED: {table_name} | "
            f"{total_rows:,} rows inserted in {duration:.2f}s | "
            f"Final rate: {rate:,.0f} rows/sec"
        )

    def _prepare_chunk_for_insert(
        self, chunk: pd.DataFrame, schema: Dict[str, str]
    ) -> pd.DataFrame:
        """
        Prepare chunk data for database insertion, handling semicolon-separated values.
        """
        chunk_cleaned = chunk.copy()

        # Handle missing columns - ensure all schema columns exist
        for col in schema.keys():
            if col not in chunk_cleaned.columns:
                chunk_cleaned[col] = ""
                self._logger.debug(f"Added missing column '{col}' with empty values")

        # Ensure columns are in the correct order as per schema
        chunk_cleaned = chunk_cleaned[list(schema.keys())]

        # Clean data based on column types
        for col, dtype in schema.items():
            if col in chunk_cleaned.columns:
                # Special handling for UF column in estabelecimento table
                if col == "uf" and "VARCHAR(10)" in dtype:
                    # Clean UF values - handle both 2-letter codes and numeric values
                    chunk_cleaned[col] = chunk_cleaned[col].astype(str)
                    # For values longer than 10 chars, truncate
                    chunk_cleaned[col] = chunk_cleaned[col].str.slice(0, 10)

                # Special handling for DDD and phone columns
                elif col in ["ddd_1", "ddd_2", "ddd_fax"] and "VARCHAR(15)" in dtype:
                    chunk_cleaned[col] = chunk_cleaned[col].astype(str)
                    # Truncate to max length
                    chunk_cleaned[col] = chunk_cleaned[col].str.slice(0, 15)

                elif (
                    col in ["telefone_1", "telefone_2", "fax"]
                    and "VARCHAR(30)" in dtype
                ):
                    chunk_cleaned[col] = chunk_cleaned[col].astype(str)
                    # Truncate to max length
                    chunk_cleaned[col] = chunk_cleaned[col].str.slice(0, 30)

                elif "INTEGER" in dtype:
                    # Handle integer columns - clean and convert properly
                    chunk_cleaned[col] = chunk_cleaned[col].astype(str)
                    # Remove quotes and extra whitespace
                    chunk_cleaned[col] = chunk_cleaned[col].str.replace(
                        '"', "", regex=False
                    )
                    chunk_cleaned[col] = chunk_cleaned[col].str.replace(
                        "'", "", regex=False
                    )
                    chunk_cleaned[col] = chunk_cleaned[col].str.strip()
                    # Replace empty strings, 'nan', and 'None' with pd.NA for proper NULL handling
                    chunk_cleaned[col] = chunk_cleaned[col].replace(
                        ["", "nan", "None", "NaN", "null", "NULL"], pd.NA
                    )
                    # Convert to numeric, coercing errors to NaN
                    chunk_cleaned[col] = pd.to_numeric(
                        chunk_cleaned[col], errors="coerce"
                    )

                    # Convert to integer, handling NaN values properly
                    non_null_mask = chunk_cleaned[col].notna()
                    if non_null_mask.any():
                        chunk_cleaned.loc[non_null_mask, col] = chunk_cleaned.loc[
                            non_null_mask, col
                        ].astype(int)

                    # Keep as object type to allow mixing of integers and None/NaN
                    chunk_cleaned[col] = chunk_cleaned[col].where(non_null_mask, None)

                elif "DECIMAL" in dtype:
                    # Handle decimal columns
                    chunk_cleaned[col] = chunk_cleaned[col].astype(str)
                    # Remove quotes and clean decimal values
                    chunk_cleaned[col] = chunk_cleaned[col].str.replace(
                        '"', "", regex=False
                    )
                    chunk_cleaned[col] = chunk_cleaned[col].str.replace(
                        "'", "", regex=False
                    )
                    chunk_cleaned[col] = chunk_cleaned[col].str.strip()
                    # Replace comma with dot for decimal separator (Brazilian format)
                    chunk_cleaned[col] = chunk_cleaned[col].str.replace(
                        ",", ".", regex=False
                    )
                    chunk_cleaned[col] = chunk_cleaned[col].replace(
                        ["", "nan", "None", "NaN", "null", "NULL"], pd.NA
                    )
                    chunk_cleaned[col] = pd.to_numeric(
                        chunk_cleaned[col], errors="coerce"
                    )

                elif "VARCHAR" in dtype or "TEXT" in dtype:
                    # Handle text columns - ensure they're strings
                    chunk_cleaned[col] = chunk_cleaned[col].astype(str)
                    chunk_cleaned[col] = chunk_cleaned[col].replace("nan", "")
                    # Remove quotes that might interfere with COPY
                    chunk_cleaned[col] = chunk_cleaned[col].str.replace(
                        '"', "", regex=False
                    )
                    # Remove problematic characters
                    chunk_cleaned[col] = chunk_cleaned[col].str.replace(
                        "\t", " ", regex=False
                    )
                    chunk_cleaned[col] = chunk_cleaned[col].str.replace(
                        "\n", " ", regex=False
                    )
                    chunk_cleaned[col] = chunk_cleaned[col].str.replace(
                        "\r", " ", regex=False
                    )

                    # Limit length for VARCHAR fields
                    if "VARCHAR" in dtype:
                        import re

                        match = re.search(r"VARCHAR\((\d+)\)", dtype)
                        if match:
                            max_length = int(match.group(1))
                            chunk_cleaned[col] = chunk_cleaned[col].str.slice(
                                0, max_length
                            )

        # Fill remaining NaN/None values with appropriate defaults
        for col, dtype in schema.items():
            if col in chunk_cleaned.columns:
                if "VARCHAR" in dtype or "TEXT" in dtype:
                    chunk_cleaned[col] = chunk_cleaned[col].fillna("")
                # For INTEGER and DECIMAL, leave None as is for proper NULL handling

        return chunk_cleaned

    def process_csv_file_to_database(
        self,
        file_path: str,
        table_name: str,
        chunk_size: int = 10000,  # Reduced from 50000
    ) -> None:
        """
        Process a semicolon-separated CSV file directly to database in chunks.
        Optimized for very large files that may not fit in memory.
        """
        self._logger.info(f"PROCESSING CSV file: {file_path} -> {table_name}")

        # Get table schema
        schema = self._get_table_schema(table_name)
        expected_columns = list(schema.keys())

        # Create table with optimizations
        self.create_table_with_schema(table_name, schema)
        self.optimize_table_for_bulk_insert(table_name)

        # Count total rows for progress tracking (skip for very large files)
        try:
            # Only count if file is smaller than 1GB to avoid delays
            import os

            file_size = os.path.getsize(file_path)
            if file_size < 1_000_000_000:  # 1GB
                with open(file_path, "r", encoding="utf-8") as f:
                    total_rows = sum(1 for _ in f)
                self._logger.info(
                    f"FILE ANALYSIS: Contains approximately {total_rows:,} rows"
                )
            else:
                total_rows = 0
                self._logger.info(
                    f"FILE ANALYSIS: Large file ({file_size:,} bytes), skipping row count"
                )
        except Exception:
            total_rows = 0
            self._logger.warning(
                "Could not count file rows, progress will be approximate"
            )

        # Start progress tracking
        if total_rows > 0:
            self._progress_tracker.start_tracking(table_name, total_rows)

        start_time = time.time()
        processed_rows = 0
        chunk_count = 0

        try:
            # Read file in chunks with smaller chunk size for memory efficiency
            chunk_reader = pd.read_csv(
                file_path,
                chunksize=chunk_size,
                sep=";",  # RFB files use semicolon separator
                header=None,
                names=None,  # Don't assign names initially
                dtype="str",  # Read everything as string initially
                low_memory=True,  # Enable low memory mode
                na_values=[""],
                keep_default_na=False,
                encoding="utf-8",
                quoting=0,  # QUOTE_MINIMAL
                on_bad_lines="skip",  # Skip malformed lines
                engine="c",  # Use faster C engine
            )

            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    for chunk in chunk_reader:
                        chunk_count += 1
                        chunk_start_time = time.time()

                        # Handle variable column counts
                        actual_columns = len(chunk.columns)
                        expected_count = len(expected_columns)

                        # Adjust columns to match schema
                        if actual_columns < expected_count:
                            # Add missing columns with empty values
                            for i in range(actual_columns, expected_count):
                                chunk[i] = ""
                            if chunk_count <= 5:  # Only log for first few chunks
                                self._logger.debug(
                                    f"Added {expected_count - actual_columns} missing columns to chunk {chunk_count}"
                                )
                        elif actual_columns > expected_count:
                            # Drop extra columns
                            chunk = chunk.iloc[:, :expected_count]
                            if chunk_count <= 5:  # Only log for first few chunks
                                self._logger.debug(
                                    f"Dropped {actual_columns - expected_count} extra columns from chunk {chunk_count}"
                                )

                        # Assign proper column names
                        chunk.columns = expected_columns

                        # Clean and prepare chunk (optimized)
                        chunk_cleaned = self._prepare_chunk_for_insert_optimized(
                            chunk, schema
                        )

                        # Generate CSV data more efficiently
                        output = io.StringIO()

                        # Use vectorized operations for better performance
                        csv_data = self._generate_csv_data_optimized(
                            chunk_cleaned, schema
                        )
                        output.write(csv_data)
                        output.seek(0)

                        try:
                            cur.copy_from(
                                output,
                                table_name,
                                columns=expected_columns,
                                sep="\t",
                                null="\\N",
                            )
                        except Exception as copy_error:
                            self._logger.error(
                                f"COPY error in chunk {chunk_count}: {copy_error}"
                            )

                            # Debug output (limited)
                            output.seek(0)
                            sample_lines = output.read().split("\n")[:2]
                            self._logger.error("Sample problematic lines:")
                            for idx, line in enumerate(sample_lines):
                                if line.strip():
                                    self._logger.error(
                                        f"Line {idx + 1}: {repr(line[:200])}"
                                    )  # Limit output

                            raise

                        processed_rows += len(chunk)
                        chunk_time = time.time() - chunk_start_time

                        # Update progress
                        if total_rows > 0:
                            self._progress_tracker.update_progress(processed_rows)

                        # Commit more frequently for smaller chunks
                        if chunk_count % 50 == 0:  # Every 50 chunks instead of 20
                            conn.commit()

                        # Log progress more frequently
                        if (
                            chunk_count % 25 == 0 or chunk_count <= 10
                        ):  # More frequent logging
                            elapsed = time.time() - start_time
                            overall_rate = (
                                processed_rows / elapsed if elapsed > 0 else 0
                            )
                            chunk_rate = (
                                len(chunk) / chunk_time if chunk_time > 0 else 0
                            )

                            if total_rows > 0:
                                progress = (processed_rows / total_rows) * 100
                                self._logger.info(
                                    f"PROGRESS {table_name}: Chunk {chunk_count:>4} | "
                                    f"{progress:>5.1f}% | {processed_rows:>9,}/{total_rows:,} rows | "
                                    f"Rate: {overall_rate:>7,.0f} rows/sec | "
                                    f"Chunk: {chunk_rate:>6,.0f} rows/sec"
                                )
                            else:
                                self._logger.info(
                                    f"PROGRESS {table_name}: Chunk {chunk_count:>4} | "
                                    f"{processed_rows:>9,} rows | "
                                    f"Rate: {overall_rate:>7,.0f} rows/sec | "
                                    f"Chunk: {chunk_rate:>6,.0f} rows/sec"
                                )

                        # Force garbage collection every 100 chunks
                        if chunk_count % 100 == 0:
                            import gc

                            gc.collect()

                conn.commit()

        except Exception as e:
            self._logger.error(f"ERROR processing CSV file {file_path}: {e}")
            raise

        # Finalize table
        self._logger.info(f"FINALIZING table {table_name}...")
        self.finalize_table_after_bulk_insert(table_name)

        end_time = time.time()
        duration = end_time - start_time
        rate = processed_rows / duration if duration > 0 else 0

        self._logger.info(
            f"COMPLETED: {file_path} -> {table_name} | "
            f"{processed_rows:,} rows in {duration:.2f}s | "
            f"Rate: {rate:,.0f} rows/sec"
        )

    def _get_table_schema(self, table_name: str) -> Dict[str, str]:
        """Get table schema based on table name."""
        schema_mapping = {
            "empresa": TableSchema.get_empresa_schema(),
            "estabelecimento": TableSchema.get_estabelecimento_schema(),
            "socios": TableSchema.get_socios_schema(),
            "simples": TableSchema.get_simples_schema(),
            "cnae": TableSchema.get_cnae_schema(),
            "moti": TableSchema.get_moti_schema(),
            "munic": TableSchema.get_munic_schema(),
            "natju": TableSchema.get_natju_schema(),
            "pais": TableSchema.get_pais_schema(),
            "quals": TableSchema.get_quals_schema(),
        }

        return schema_mapping.get(table_name, {})

    def create_table_with_schema(self, table_name: str, schema: Dict[str, str]) -> None:
        """Create table with optimized settings for large datasets."""
        if not schema:
            self._logger.error(f"No schema found for table {table_name}")
            return

        columns_sql = ", ".join([f"{col} {dtype}" for col, dtype in schema.items()])

        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {columns_sql}
        ) WITH (
            autovacuum_enabled = false,
            fillfactor = 100
        )
        """

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {table_name}")
                cur.execute(create_table_sql)
                conn.commit()

        self._logger.info(f"Created table {table_name} with optimizations")

    def optimize_table_for_bulk_insert(self, table_name: str) -> None:
        """Optimize table settings before bulk insert."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Disable autovacuum and autoanalyze during bulk insert
                cur.execute(
                    f"ALTER TABLE {table_name} SET (autovacuum_enabled = false)"
                )
                cur.execute(
                    f"ALTER TABLE {table_name} SET (toast.autovacuum_enabled = false)"
                )
                conn.commit()

        self._logger.info(f"Table {table_name} optimized for bulk insert")

    def finalize_table_after_bulk_insert(self, table_name: str) -> None:
        """Re-enable optimizations and run maintenance after bulk insert."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Re-enable autovacuum
                cur.execute(f"ALTER TABLE {table_name} SET (autovacuum_enabled = true)")
                cur.execute(
                    f"ALTER TABLE {table_name} SET (toast.autovacuum_enabled = true)"
                )

                # Run VACUUM and ANALYZE
                conn.commit()
                conn.autocommit = True
                cur.execute(f"VACUUM ANALYZE {table_name}")
                conn.autocommit = False

        self._logger.info(f"Table {table_name} finalized after bulk insert")

    def create_optimized_indexes(self, table_name: str = None) -> None:
        """Create optimized indexes for better query performance on large tables."""
        index_configs = {
            "empresa": [
                ("idx_empresa_cnpj_basico", "cnpj_basico", "UNIQUE"),
                ("idx_empresa_porte", "porte_empresa", ""),
                ("idx_empresa_natureza", "natureza_juridica", ""),
            ],
            "estabelecimento": [
                ("idx_estabelecimento_cnpj_basico", "cnpj_basico", ""),
                (
                    "idx_estabelecimento_cnpj_full",
                    "(cnpj_basico, cnpj_ordem, cnpj_dv)",
                    "UNIQUE",
                ),
                ("idx_estabelecimento_situacao", "situacao_cadastral", ""),
                ("idx_estabelecimento_uf_municipio", "(uf, municipio)", ""),
                ("idx_estabelecimento_cnae", "cnae_fiscal_principal", ""),
                ("idx_estabelecimento_cep", "cep", ""),
            ],
            "socios": [
                ("idx_socios_cnpj_basico", "cnpj_basico", ""),
                ("idx_socios_cpf_cnpj", "cpf_cnpj_socio", ""),
                ("idx_socios_qualificacao", "qualificacao_socio", ""),
            ],
            "simples": [
                ("idx_simples_cnpj_basico", "cnpj_basico", "UNIQUE"),
                ("idx_simples_opcao", "opcao_pelo_simples", ""),
                ("idx_simples_mei", "opcao_mei", ""),
            ],
        }

        # If no specific table, create indexes for all tables
        tables_to_index = [table_name] if table_name else index_configs.keys()

        for table in tables_to_index:
            if table not in index_configs:
                continue

            start_time = time.time()
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    for index_name, columns, constraint in index_configs[table]:
                        try:
                            if constraint == "UNIQUE":
                                query = f"CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS {index_name} ON {table} ({columns})"
                            else:
                                query = f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} ON {table} ({columns})"

                            cur.execute(query)
                            conn.commit()
                            self._logger.info(f"Index created: {index_name}")
                        except Exception as e:
                            self._logger.warning(
                                f"Index creation failed: {index_name} - {e}"
                            )
                            conn.rollback()

            end_time = time.time()
            self._logger.info(
                f"Index creation for {table} completed in {end_time - start_time:.2f} seconds"
            )


class TableSchema:
    """Table schema definitions with optimized data types for large datasets."""

    @staticmethod
    def get_empresa_schema() -> Dict[str, str]:
        """Get empresa table schema with optimized data types."""
        return {
            "cnpj_basico": "VARCHAR(8) NOT NULL",
            "razao_social": "TEXT",
            "natureza_juridica": "INTEGER",
            "qualificacao_responsavel": "INTEGER",
            "capital_social": "DECIMAL(15,2)",
            "porte_empresa": "INTEGER",
            "ente_federativo_responsavel": "TEXT",
        }

    @staticmethod
    def get_estabelecimento_schema() -> Dict[str, str]:
        """Get estabelecimento table schema with optimized data types - matching RFB layout."""
        return {
            "cnpj_basico": "VARCHAR(8) NOT NULL",
            "cnpj_ordem": "VARCHAR(4) NOT NULL",
            "cnpj_dv": "VARCHAR(2) NOT NULL",
            "identificador_matriz_filial": "INTEGER",
            "nome_fantasia": "TEXT",
            "situacao_cadastral": "INTEGER",
            "data_situacao_cadastral": "INTEGER",
            "motivo_situacao_cadastral": "INTEGER",
            "nome_cidade_exterior": "TEXT",
            "pais": "INTEGER",
            "data_inicio_atividade": "INTEGER",
            "cnae_fiscal_principal": "INTEGER",
            "cnae_fiscal_secundaria": "TEXT",
            "tipo_logradouro": "TEXT",
            "logradouro": "TEXT",
            "numero": "TEXT",
            "complemento": "TEXT",
            "bairro": "TEXT",
            "cep": "VARCHAR(8)",
            "uf": "VARCHAR(10)",
            "municipio": "INTEGER",
            "ddd_1": "VARCHAR(15)",
            "telefone_1": "VARCHAR(30)",
            "ddd_2": "VARCHAR(15)",
            "telefone_2": "VARCHAR(30)",
            "ddd_fax": "VARCHAR(15)",
            "fax": "VARCHAR(30)",
            "correio_eletronico": "TEXT",
            "situacao_especial": "TEXT",
            "data_situacao_especial": "INTEGER",
        }

    @staticmethod
    def get_socios_schema() -> Dict[str, str]:
        """Get socios table schema with optimized data types."""
        return {
            "cnpj_basico": "VARCHAR(8) NOT NULL",
            "identificador_socio": "INTEGER",
            "nome_socio_razao_social": "TEXT",
            "cpf_cnpj_socio": "VARCHAR(14)",
            "qualificacao_socio": "INTEGER",
            "data_entrada_sociedade": "INTEGER",
            "pais": "INTEGER",
            "representante_legal": "TEXT",
            "nome_do_representante": "TEXT",
            "qualificacao_representante_legal": "INTEGER",
            "faixa_etaria": "INTEGER",
        }

    @staticmethod
    def get_simples_schema() -> Dict[str, str]:
        """Get simples table schema with optimized data types."""
        return {
            "cnpj_basico": "VARCHAR(8) NOT NULL",
            "opcao_pelo_simples": "VARCHAR(1)",
            "data_opcao_simples": "INTEGER",
            "data_exclusao_simples": "INTEGER",
            "opcao_mei": "VARCHAR(1)",
            "data_opcao_mei": "INTEGER",
            "data_exclusao_mei": "INTEGER",
        }

    @staticmethod
    def get_cnae_schema() -> Dict[str, str]:
        """Get CNAE table schema."""
        return {
            "codigo": "INTEGER NOT NULL",
            "descricao": "TEXT",
        }

    @staticmethod
    def get_moti_schema() -> Dict[str, str]:
        """Get motivo situacao cadastral table schema."""
        return {
            "codigo": "INTEGER NOT NULL",
            "descricao": "TEXT",
        }

    @staticmethod
    def get_munic_schema() -> Dict[str, str]:
        """Get municipio table schema."""
        return {
            "codigo": "INTEGER NOT NULL",
            "descricao": "TEXT",
        }

    @staticmethod
    def get_natju_schema() -> Dict[str, str]:
        """Get natureza juridica table schema."""
        return {
            "codigo": "INTEGER NOT NULL",
            "descricao": "TEXT",
        }

    @staticmethod
    def get_pais_schema() -> Dict[str, str]:
        """Get pais table schema."""
        return {
            "codigo": "INTEGER NOT NULL",
            "descricao": "TEXT",
        }

    @staticmethod
    def get_quals_schema() -> Dict[str, str]:
        """Get qualificacao socio table schema."""
        return {
            "codigo": "INTEGER NOT NULL",
            "descricao": "TEXT",
        }

    @staticmethod
    def get_dtype_mapping(table_name: str) -> Dict[str, str]:
        """Get pandas dtype mapping for efficient memory usage."""
        mappings = {
            "empresa": {
                "cnpj_basico": "str",
                "razao_social": "str",
                "natureza_juridica": "Int64",
                "qualificacao_responsavel": "Int64",
                "capital_social": "str",  # Parse separately to avoid issues
                "porte_empresa": "Int64",
                "ente_federativo_responsavel": "str",
            },
            "estabelecimento": {
                "cnpj_basico": "str",
                "cnpj_ordem": "str",
                "cnpj_dv": "str",
                "identificador_matriz_filial": "Int64",
                "situacao_cadastral": "Int64",
                "municipio": "Int64",
                "cnae_fiscal_principal": "Int64",
                "uf": "str",
                "cep": "str",
            },
            "socios": {
                "cnpj_basico": "str",
                "identificador_socio": "Int64",
                "cpf_cnpj_socio": "str",
                "qualificacao_socio": "Int64",
                "data_entrada_sociedade": "Int64",
                "pais": "Int64",
                "qualificacao_representante_legal": "Int64",
                "faixa_etaria": "Int64",
            },
            "simples": {
                "cnpj_basico": "str",
                "opcao_pelo_simples": "str",
                "data_opcao_simples": "Int64",
                "data_exclusao_simples": "Int64",
                "opcao_mei": "str",
                "data_opcao_mei": "Int64",
                "data_exclusao_mei": "Int64",
            },
            "cnae": {
                "codigo": "Int64",
                "descricao": "str",
            },
            "moti": {
                "codigo": "Int64",
                "descricao": "str",
            },
            "munic": {
                "codigo": "Int64",
                "descricao": "str",
            },
            "natju": {
                "codigo": "Int64",
                "descricao": "str",
            },
            "pais": {
                "codigo": "Int64",
                "descricao": "str",
            },
            "quals": {
                "codigo": "Int64",
                "descricao": "str",
            },
        }
        return mappings.get(table_name, {})
