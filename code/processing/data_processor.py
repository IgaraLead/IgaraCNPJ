"""
Data processing module for RFB ETL process.
Handles file parsing, data transformation, and validation.
"""

import gc
import logging
import os
from typing import Dict, List, Generator
import pandas as pd
from abc import ABC, abstractmethod


class DataProcessor(ABC):
    """
    Abstract base class for data processors.
    Implements interface segregation principle.
    """

    @abstractmethod
    def get_column_mapping(self) -> Dict[int, str]:
        """Return column mapping for the data type."""
        pass

    @abstractmethod
    def get_data_types(self) -> Dict[int, str]:
        """Return pandas data types for columns."""
        pass

    @abstractmethod
    def transform_data(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Apply specific transformations to the dataframe."""
        pass


class EmpresaProcessor(DataProcessor):
    """Processor for empresa (company) data files."""

    def get_column_mapping(self) -> Dict[int, str]:
        return {
            0: "cnpj_basico",
            1: "razao_social",
            2: "natureza_juridica",
            3: "qualificacao_responsavel",
            4: "capital_social",
            5: "porte_empresa",
            6: "ente_federativo_responsavel",
        }

    def get_data_types(self) -> Dict[int, str]:
        return {
            0: "object",
            1: "object",
            2: "Int32",
            3: "Int32",
            4: "object",
            5: "Int32",
            6: "object",
        }

    def transform_data(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Transform empresa data with capital_social formatting."""
        # Apply column mapping
        dataframe.columns = list(self.get_column_mapping().values())

        # Transform capital_social: replace comma with dot and convert to float
        if "capital_social" in dataframe.columns:
            dataframe["capital_social"] = (
                dataframe["capital_social"]
                .astype(str)
                .str.replace(",", ".")
                .astype(float)
            )

        return dataframe


class EstabelecimentoProcessor(DataProcessor):
    """Processor for estabelecimento (establishment) data files."""

    def get_column_mapping(self) -> Dict[int, str]:
        return {
            0: "cnpj_basico",
            1: "cnpj_ordem",
            2: "cnpj_dv",
            3: "identificador_matriz_filial",
            4: "nome_fantasia",
            5: "situacao_cadastral",
            6: "data_situacao_cadastral",
            7: "motivo_situacao_cadastral",
            8: "nome_cidade_exterior",
            9: "pais",
            10: "data_inicio_atividade",
            11: "cnae_fiscal_principal",
            12: "cnae_fiscal_secundaria",
            13: "tipo_logradouro",
            14: "logradouro",
            15: "numero",
            16: "complemento",
            17: "bairro",
            18: "cep",
            19: "uf",
            20: "municipio",
            21: "ddd_1",
            22: "telefone_1",
            23: "ddd_2",
            24: "telefone_2",
            25: "ddd_fax",
            26: "fax",
            27: "correio_eletronico",
            28: "situacao_especial",
            29: "data_situacao_especial",
        }

    def get_data_types(self) -> Dict[int, str]:
        return {
            0: "object",
            1: "object",
            2: "object",
            3: "Int32",
            4: "object",
            5: "Int32",
            6: "Int32",
            7: "Int32",
            8: "object",
            9: "object",
            10: "Int32",
            11: "Int32",
            12: "object",
            13: "object",
            14: "object",
            15: "object",
            16: "object",
            17: "object",
            18: "object",
            19: "object",
            20: "Int32",
            21: "object",
            22: "object",
            23: "object",
            24: "object",
            25: "object",
            26: "object",
            27: "object",
            28: "object",
            29: "Int32",
        }

    def transform_data(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Transform estabelecimento data."""
        dataframe.columns = list(self.get_column_mapping().values())
        return dataframe


class SociosProcessor(DataProcessor):
    """Processor for socios (partners) data files."""

    def get_column_mapping(self) -> Dict[int, str]:
        return {
            0: "cnpj_basico",
            1: "identificador_socio",
            2: "nome_socio_razao_social",
            3: "cpf_cnpj_socio",
            4: "qualificacao_socio",
            5: "data_entrada_sociedade",
            6: "pais",
            7: "representante_legal",
            8: "nome_do_representante",
            9: "qualificacao_representante_legal",
            10: "faixa_etaria",
        }

    def get_data_types(self) -> Dict[int, str]:
        return {
            0: "object",
            1: "Int32",
            2: "object",
            3: "object",
            4: "Int32",
            5: "Int32",
            6: "Int32",
            7: "object",
            8: "object",
            9: "Int32",
            10: "Int32",
        }

    def transform_data(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Transform socios data."""
        dataframe.columns = list(self.get_column_mapping().values())
        return dataframe


class SimplesProcessor(DataProcessor):
    """Processor for simples (simplified tax regime) data files."""

    def get_column_mapping(self) -> Dict[int, str]:
        return {
            0: "cnpj_basico",
            1: "opcao_pelo_simples",
            2: "data_opcao_simples",
            3: "data_exclusao_simples",
            4: "opcao_mei",
            5: "data_opcao_mei",
            6: "data_exclusao_mei",
        }

    def get_data_types(self) -> Dict[int, str]:
        return {
            0: "object",
            1: "object",
            2: "Int32",
            3: "Int32",
            4: "object",
            5: "Int32",
            6: "Int32",
        }

    def transform_data(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Transform simples data."""
        dataframe.columns = list(self.get_column_mapping().values())
        return dataframe


class ReferenceDataProcessor(DataProcessor):
    """Processor for reference/lookup data files (CNAE, MOTI, MUNIC, etc.)."""

    def get_column_mapping(self) -> Dict[int, str]:
        return {0: "codigo", 1: "descricao"}

    def get_data_types(self) -> Dict[int, str]:
        return {0: "object", 1: "object"}

    def transform_data(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Transform reference data."""
        dataframe.columns = list(self.get_column_mapping().values())
        return dataframe


class FileClassifier:
    """
    Classifies extracted files by type based on filename patterns.
    Implements single responsibility principle.
    """

    def __init__(self):
        self._logger = logging.getLogger(__name__)
        self.file_patterns = {
            "empresa": "EMPRE",
            "estabelecimento": "ESTABELE",
            "socios": "SOCIO",
            "simples": "SIMPLES",
            "cnae": "CNAE",
            "moti": "MOTI",
            "munic": "MUNIC",
            "natju": "NATJU",
            "pais": "PAIS",
            "quals": "QUALS",
        }

    def classify_files(self, extracted_directory: str) -> Dict[str, List[str]]:
        """
        Classify extracted files by type.
        Returns dictionary with file type as key and list of filenames as value.
        """
        all_files = [
            name
            for name in os.listdir(extracted_directory)
            if os.path.isfile(os.path.join(extracted_directory, name))
        ]

        classified_files = {file_type: [] for file_type in self.file_patterns.keys()}

        for filename in all_files:
            for file_type, pattern in self.file_patterns.items():
                if pattern in filename.upper():
                    classified_files[file_type].append(filename)
                    break

        # Log classification results
        for file_type, files in classified_files.items():
            if files:
                self._logger.info(f"Found {len(files)} {file_type} files")

        return classified_files


class DataReader:
    """
    Optimized data reader with chunking support for large files.
    Implements memory-efficient reading strategies.
    """

    def __init__(self, batch_size: int = 2000000):
        self.batch_size = batch_size
        self._logger = logging.getLogger(__name__)

    def read_file_in_chunks(
        self, file_path: str, processor: DataProcessor
    ) -> Generator[pd.DataFrame, None, None]:
        """
        Read large files in chunks to manage memory usage.
        Yields processed dataframes.
        """
        try:
            file_size = os.path.getsize(file_path)
            self._logger.info(
                f"Reading {os.path.basename(file_path)} ({file_size:,} bytes)"
            )

            # Determine if chunking is needed
            total_lines = sum(1 for _ in open(file_path, "r", encoding="latin-1"))

            if total_lines <= self.batch_size:
                # Read entire file at once for smaller files
                df = pd.read_csv(
                    file_path,
                    sep=";",
                    header=None,
                    dtype=processor.get_data_types(),
                    encoding="latin-1",
                )
                df = df.reset_index(drop=True)
                yield processor.transform_data(df)

            else:
                # Read in chunks for large files
                self._logger.info(f"File has {total_lines:,} lines, reading in chunks")

                chunk_count = 0
                for chunk in pd.read_csv(
                    file_path,
                    sep=";",
                    header=None,
                    dtype=processor.get_data_types(),
                    encoding="latin-1",
                    chunksize=self.batch_size,
                ):
                    chunk = chunk.reset_index(drop=True)
                    processed_chunk = processor.transform_data(chunk)
                    chunk_count += 1

                    self._logger.info(
                        f"Processing chunk {chunk_count} ({len(processed_chunk):,} rows)"
                    )
                    yield processed_chunk

                    # Force garbage collection to manage memory
                    gc.collect()

        except Exception as e:
            self._logger.error(f"Error reading file {file_path}: {e}")
            raise

    def read_simple_file(
        self, file_path: str, processor: DataProcessor
    ) -> pd.DataFrame:
        """
        Read smaller reference files completely into memory.
        """
        try:
            df = pd.read_csv(
                file_path,
                sep=";",
                header=None,
                dtype=processor.get_data_types(),
                encoding="latin-1",
            )
            df = df.reset_index(drop=True)
            return processor.transform_data(df)

        except Exception as e:
            self._logger.error(f"Error reading file {file_path}: {e}")
            raise


class ProcessorFactory:
    """
    Factory class for creating appropriate data processors.
    Implements factory pattern and dependency inversion principle.
    """

    @staticmethod
    def get_processor(file_type: str) -> DataProcessor:
        """Get appropriate processor for file type."""
        processors = {
            "empresa": EmpresaProcessor(),
            "estabelecimento": EstabelecimentoProcessor(),
            "socios": SociosProcessor(),
            "simples": SimplesProcessor(),
            "cnae": ReferenceDataProcessor(),
            "moti": ReferenceDataProcessor(),
            "munic": ReferenceDataProcessor(),
            "natju": ReferenceDataProcessor(),
            "pais": ReferenceDataProcessor(),
            "quals": ReferenceDataProcessor(),
        }

        if file_type not in processors:
            raise ValueError(f"Unknown file type: {file_type}")

        return processors[file_type]
