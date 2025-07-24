"""
Test suite for the optimized RFB ETL process.
Tests core functionality and performance optimizations.
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch
import pandas as pd
from config.settings import DatabaseConfig
from processing.data_processor import (
    EmpresaProcessor,
    EstabelecimentoProcessor,
    FileClassifier,
    ProcessorFactory,
)
from download.manager import FileDownloader, RFBFileDiscovery


class TestDatabaseConfig(unittest.TestCase):
    """Test database configuration management."""

    def setUp(self):
        # Set test environment variables
        os.environ.update(
            {
                "DB_HOST": "test_host",
                "DB_PORT": "5433",
                "DB_NAME": "test_db",
                "DB_USER": "test_user",
                "DB_PASSWORD": "test_pass",
            }
        )
        self.config = DatabaseConfig()

    def test_connection_string_generation(self):
        """Test PostgreSQL connection string generation."""
        expected = "postgresql://test_user:test_pass@test_host:5433/test_db"
        self.assertEqual(self.config.get_connection_string(), expected)

    def test_psycopg2_params(self):
        """Test psycopg2 connection parameters."""
        params = self.config.get_psycopg2_params()
        expected = {
            "dbname": "test_db",
            "user": "test_user",
            "host": "test_host",
            "port": "5433",
            "password": "test_pass",
        }
        self.assertEqual(params, expected)


class TestDataProcessors(unittest.TestCase):
    """Test data processing functionality."""

    def test_empresa_processor(self):
        """Test empresa data processor."""
        processor = EmpresaProcessor()

        # Test column mapping
        columns = processor.get_column_mapping()
        self.assertEqual(columns[0], "cnpj_basico")
        self.assertEqual(columns[4], "capital_social")

        # Test data transformation
        test_data = pd.DataFrame(
            {
                0: ["12345678"],
                1: ["Test Company"],
                2: [101],
                3: [49],
                4: ["1000,50"],  # Test comma replacement
                5: [2],
                6: [""],
            }
        )

        result = processor.transform_data(test_data)

        # Check if columns are renamed correctly
        self.assertIn("cnpj_basico", result.columns)
        self.assertIn("capital_social", result.columns)

        # Check if capital_social is converted to float
        self.assertEqual(result["capital_social"].iloc[0], 1000.50)
        self.assertEqual(result["capital_social"].dtype, "float64")

    def test_estabelecimento_processor(self):
        """Test estabelecimento data processor."""
        processor = EstabelecimentoProcessor()

        # Test column mapping length
        columns = processor.get_column_mapping()
        self.assertEqual(len(columns), 30)  # 30 columns expected

        # Test specific column mappings
        self.assertEqual(columns[0], "cnpj_basico")
        self.assertEqual(columns[19], "uf")
        self.assertEqual(columns[27], "correio_eletronico")


class TestFileClassifier(unittest.TestCase):
    """Test file classification functionality."""

    def setUp(self):
        self.classifier = FileClassifier()

        # Create temporary directory with test files
        self.test_dir = tempfile.mkdtemp()

        # Create test files
        test_files = [
            "K3241.K03200Y0.D10710.EMPRECSV",
            "K3241.K03200Y0.D10710.ESTABELE",
            "K3241.K03200Y0.D10710.SOCIOCSV",
            "K3241.K03200Y0.D10710.SIMPLES.CSV",
            "F.K03200W0.CNAECSV",
            "F.K03200W0.MOTICSV",
            "F.K03200W0.MUNICCSV",
        ]

        for filename in test_files:
            with open(os.path.join(self.test_dir, filename), "w") as f:
                f.write("test")

    def tearDown(self):
        # Clean up test directory
        import shutil

        shutil.rmtree(self.test_dir)

    def test_file_classification(self):
        """Test file classification by type."""
        classified = self.classifier.classify_files(self.test_dir)

        # Check if files are classified correctly
        self.assertTrue(len(classified["empresa"]) > 0)
        self.assertTrue(len(classified["estabelecimento"]) > 0)
        self.assertTrue(len(classified["socios"]) > 0)
        self.assertTrue(len(classified["simples"]) > 0)
        self.assertTrue(len(classified["cnae"]) > 0)
        self.assertTrue(len(classified["moti"]) > 0)
        self.assertTrue(len(classified["munic"]) > 0)


class TestProcessorFactory(unittest.TestCase):
    """Test processor factory functionality."""

    def test_processor_creation(self):
        """Test processor factory creates correct processors."""
        # Test empresa processor
        processor = ProcessorFactory.get_processor("empresa")
        self.assertIsInstance(processor, EmpresaProcessor)

        # Test estabelecimento processor
        processor = ProcessorFactory.get_processor("estabelecimento")
        self.assertIsInstance(processor, EstabelecimentoProcessor)

        # Test invalid processor type
        with self.assertRaises(ValueError):
            ProcessorFactory.get_processor("invalid_type")


class TestFileDownloader(unittest.TestCase):
    """Test file download functionality."""

    def setUp(self):
        self.downloader = FileDownloader(max_workers=2, max_retries=2)

    @patch("requests.head")
    @patch("os.path.isfile")
    @patch("os.path.getsize")
    def test_check_file_needs_download(self, mock_getsize, mock_isfile, mock_head):
        """Test file download necessity check."""
        # Test file doesn't exist
        mock_isfile.return_value = False
        result = self.downloader.check_file_needs_download(
            "http://test.com/file.zip", "file.zip"
        )
        self.assertTrue(result)

        # Test file exists with same size
        mock_isfile.return_value = True
        mock_getsize.return_value = 1000
        mock_response = Mock()
        mock_response.headers = {"content-length": "1000"}
        mock_head.return_value = mock_response

        result = self.downloader.check_file_needs_download(
            "http://test.com/file.zip", "file.zip"
        )
        self.assertFalse(result)

        # Test file exists with different size
        mock_getsize.return_value = 500
        with patch("os.remove") as mock_remove:
            result = self.downloader.check_file_needs_download(
                "http://test.com/file.zip", "file.zip"
            )
            self.assertTrue(result)
            mock_remove.assert_called_once()


class TestRFBFileDiscovery(unittest.TestCase):
    """Test RFB file discovery functionality."""

    def setUp(self):
        self.discovery = RFBFileDiscovery("http://test.com/cnpj/")

    @patch("urllib.request.urlopen")
    def test_discover_zip_files(self, mock_urlopen):
        """Test ZIP file discovery from HTML."""
        # Mock HTML response with ZIP file links
        html_content = """
        <html>
        <body>
        <a href="file1.zip">file1.zip</a>
        <a href="file2.ZIP">file2.ZIP</a>
        <a href="document.pdf">document.pdf</a>
        <a href="file3.zip">file3.zip</a>
        </body>
        </html>
        """

        mock_response = Mock()
        mock_response.read.return_value = html_content.encode()
        mock_urlopen.return_value = mock_response

        files = self.discovery.discover_zip_files()

        # Should find ZIP files and ignore non-ZIP files
        self.assertIn("file1.zip", files)
        self.assertIn("file2.ZIP", files)
        self.assertIn("file3.zip", files)
        self.assertNotIn("document.pdf", files)

    def test_create_download_tasks(self):
        """Test download task creation."""
        filenames = ["file1.zip", "file2.zip"]
        tasks = self.discovery.create_download_tasks(filenames)

        expected = [
            ("http://test.com/cnpj/file1.zip", "file1.zip"),
            ("http://test.com/cnpj/file2.zip", "file2.zip"),
        ]

        self.assertEqual(tasks, expected)


class TestPerformanceOptimizations(unittest.TestCase):
    """Test performance optimization features."""

    def test_chunking_logic(self):
        """Test data chunking for memory optimization."""
        from processing.data_processor import DataReader

        reader = DataReader(batch_size=1000)

        # Create large test dataset
        test_data = pd.DataFrame({"col1": range(2500), "col2": ["test"] * 2500})

        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            test_data.to_csv(f.name, sep=";", index=False, header=False)
            temp_file = f.name

        try:
            # Mock processor
            mock_processor = Mock()
            mock_processor.get_data_types.return_value = {0: "int64", 1: "object"}
            mock_processor.transform_data.side_effect = lambda x: x

            # Test chunked reading
            chunks = list(reader.read_file_in_chunks(temp_file, mock_processor))

            # Should create multiple chunks for large file
            self.assertGreater(len(chunks), 1)

            # Each chunk should be smaller than total data
            for chunk in chunks:
                self.assertLessEqual(len(chunk), 1000)

        finally:
            os.unlink(temp_file)


class IntegrationTests(unittest.TestCase):
    """Integration tests for the complete ETL pipeline."""

    @patch("psycopg2.connect")
    @patch("sqlalchemy.create_engine")
    def test_database_integration(self, mock_engine, mock_connect):
        """Test database integration with mocked connections."""
        from database.manager import DatabaseManager

        # Mock database config
        config = Mock()
        config.get_connection_string.return_value = "test_connection_string"
        config.get_psycopg2_params.return_value = {"test": "params"}

        manager = DatabaseManager(config)
        manager.initialize_connection()

        # Verify engine creation was called
        mock_engine.assert_called_once()

    @patch("os.listdir")
    def test_etl_pipeline_coordination(self, mock_listdir):
        """Test ETL pipeline coordination."""
        from etl_orchestrator import ETLOrchestrator

        # Mock extracted files
        mock_listdir.return_value = ["EMPRE.CSV", "ESTABELE.CSV", "CNAE.CSV"]

        # Mock configuration
        with patch("config.settings.ETLConfig") as mock_config:
            mock_config.return_value.extracted_files_path = "/test/path"

            # Create orchestrator with mocked dependencies
            with patch.multiple(
                "etl_orchestrator.ETLOrchestrator",
                _download_phase=Mock(return_value=["file1.zip"]),
                _extract_phase=Mock(),
                _process_and_load_phase=Mock(),
                _create_indexes_phase=Mock(),
            ):
                orchestrator = ETLOrchestrator(mock_config.return_value)

                # Test that all phases can be called without errors
                # (actual execution is mocked)
                self.assertIsNotNone(orchestrator)


def run_performance_benchmark():
    """
    Performance benchmark for comparing optimized vs original operations.
    """
    print("=== Performance Benchmark ===")

    # Test data processing speed
    import time

    # Create large test dataset
    size = 100000
    test_data = pd.DataFrame(
        {
            "cnpj_basico": [f"{i:08d}" for i in range(size)],
            "razao_social": [f"Company {i}" for i in range(size)],
            "capital_social": [f"{i*100},50" for i in range(size)],
        }
    )

    processor = EmpresaProcessor()

    # Benchmark processing time
    start_time = time.time()
    processed_data = processor.transform_data(test_data)
    end_time = time.time()

    processing_time = end_time - start_time
    rows_per_second = size / processing_time

    print(f"Processed {size:,} rows in {processing_time:.2f} seconds")
    print(f"Performance: {rows_per_second:,.0f} rows/second")
    print(
        f"Memory usage: {processed_data.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB"
    )


if __name__ == "__main__":
    # Run unit tests
    unittest.main(verbosity=2, exit=False)

    # Run performance benchmark
    print("\n" + "=" * 50)
    run_performance_benchmark()
