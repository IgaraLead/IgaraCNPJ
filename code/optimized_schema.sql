-- Optimized database schema for RFB ETL process
-- Includes performance optimizations and proper indexing strategies

-- Create the database "Dados_RFB" (if not exists)
CREATE DATABASE "Dados_RFB"
    WITH
    OWNER = postgres
    ENCODING = 'UTF8'
    CONNECTION LIMIT = -1;

COMMENT ON DATABASE "Dados_RFB"
    IS 'Optimized database for RFB public CNPJ data with performance enhancements';

-- Connect to the database
\c "Dados_RFB";

-- Enable extensions for better performance
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Create optimized empresa table
CREATE TABLE IF NOT EXISTS empresa (
    cnpj_basico VARCHAR(8) NOT NULL,
    razao_social TEXT,
    natureza_juridica INTEGER,
    qualificacao_responsavel INTEGER,
    capital_social DECIMAL(15,2),
    porte_empresa INTEGER,
    ente_federativo_responsavel TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_empresa PRIMARY KEY (cnpj_basico)
);

-- Create optimized estabelecimento table
CREATE TABLE IF NOT EXISTS estabelecimento (
    cnpj_basico VARCHAR(8) NOT NULL,
    cnpj_ordem VARCHAR(4) NOT NULL,
    cnpj_dv VARCHAR(2) NOT NULL,
    identificador_matriz_filial INTEGER,
    nome_fantasia TEXT,
    situacao_cadastral INTEGER,
    data_situacao_cadastral INTEGER,
    motivo_situacao_cadastral INTEGER,
    nome_cidade_exterior TEXT,
    pais INTEGER,
    data_inicio_atividade INTEGER,
    cnae_fiscal_principal INTEGER,
    cnae_fiscal_secundaria TEXT,
    tipo_logradouro TEXT,
    logradouro TEXT,
    numero TEXT,
    complemento TEXT,
    bairro TEXT,
    cep VARCHAR(8),
    uf VARCHAR(10),  -- Changed from VARCHAR(2) to VARCHAR(10)
    municipio INTEGER,
    ddd_1 VARCHAR(15),  -- Changed from VARCHAR(4) to VARCHAR(15)
    telefone_1 VARCHAR(30),  -- Changed from VARCHAR(20) to VARCHAR(30)
    ddd_2 VARCHAR(15),  -- Changed from VARCHAR(4) to VARCHAR(15)
    telefone_2 VARCHAR(30),  -- Changed from VARCHAR(20) to VARCHAR(30)
    ddd_fax VARCHAR(15),  -- Changed from VARCHAR(4) to VARCHAR(15)
    fax VARCHAR(30),  -- Changed from VARCHAR(20) to VARCHAR(30)
    correio_eletronico TEXT,
    situacao_especial TEXT,
    data_situacao_especial INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_estabelecimento PRIMARY KEY (cnpj_basico, cnpj_ordem, cnpj_dv)
);

-- Create optimized socios table
CREATE TABLE IF NOT EXISTS socios (
    cnpj_basico VARCHAR(8) NOT NULL,
    identificador_socio INTEGER,
    nome_socio_razao_social TEXT,
    cpf_cnpj_socio VARCHAR(14),
    qualificacao_socio INTEGER,
    data_entrada_sociedade INTEGER,
    pais INTEGER,
    representante_legal TEXT,
    nome_do_representante TEXT,
    qualificacao_representante_legal INTEGER,
    faixa_etaria INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create optimized simples table
CREATE TABLE IF NOT EXISTS simples (
    cnpj_basico VARCHAR(8) NOT NULL,
    opcao_pelo_simples VARCHAR(1),
    data_opcao_simples INTEGER,
    data_exclusao_simples INTEGER,
    opcao_mei VARCHAR(1),
    data_opcao_mei INTEGER,
    data_exclusao_mei INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_simples PRIMARY KEY (cnpj_basico)
);

-- Create reference tables with optimized structure
CREATE TABLE IF NOT EXISTS cnae (
    codigo INTEGER PRIMARY KEY,
    descricao TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS moti (
    codigo INTEGER PRIMARY KEY,
    descricao TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS munic (
    codigo INTEGER PRIMARY KEY,
    descricao TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS natju (
    codigo INTEGER PRIMARY KEY,
    descricao TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pais (
    codigo INTEGER PRIMARY KEY,
    descricao TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS quals (
    codigo INTEGER PRIMARY KEY,
    descricao TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for optimal query performance
-- Primary indexes for main entity lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_empresa_cnpj_basico ON empresa(cnpj_basico);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estabelecimento_cnpj_basico ON estabelecimento(cnpj_basico);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_socios_cnpj_basico ON socios(cnpj_basico);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_simples_cnpj_basico ON simples(cnpj_basico);

-- Secondary indexes for common query patterns
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estabelecimento_situacao ON estabelecimento(situacao_cadastral);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estabelecimento_uf ON estabelecimento(uf);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estabelecimento_municipio ON estabelecimento(municipio);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estabelecimento_cnae ON estabelecimento(cnae_fiscal_principal);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_empresa_porte ON empresa(porte_empresa);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_empresa_natureza ON empresa(natureza_juridica);

-- Composite indexes for complex queries
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estabelecimento_uf_municipio ON estabelecimento(uf, municipio);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estabelecimento_situacao_uf ON estabelecimento(situacao_cadastral, uf);

-- Text search indexes for name searches
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_empresa_razao_social_gin ON empresa USING gin(razao_social gin_trgm_ops);
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_estabelecimento_nome_fantasia_gin ON estabelecimento USING gin(nome_fantasia gin_trgm_ops);

-- Foreign key constraints (optional, can be enabled for data integrity)
-- ALTER TABLE estabelecimento ADD CONSTRAINT fk_estabelecimento_empresa 
--     FOREIGN KEY (cnpj_basico) REFERENCES empresa(cnpj_basico);
-- ALTER TABLE socios ADD CONSTRAINT fk_socios_empresa 
--     FOREIGN KEY (cnpj_basico) REFERENCES empresa(cnpj_basico);
-- ALTER TABLE simples ADD CONSTRAINT fk_simples_empresa 
--     FOREIGN KEY (cnpj_basico) REFERENCES empresa(cnpj_basico);

-- Create materialized views for common aggregations
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_empresa_resumo AS
SELECT 
    e.porte_empresa,
    e.natureza_juridica,
    COUNT(*) as total_empresas,
    SUM(e.capital_social) as capital_total,
    AVG(e.capital_social) as capital_medio
FROM empresa e
GROUP BY e.porte_empresa, e.natureza_juridica;

CREATE UNIQUE INDEX ON mv_empresa_resumo (porte_empresa, natureza_juridica);

CREATE MATERIALIZED VIEW IF NOT EXISTS mv_estabelecimento_por_uf AS
SELECT 
    est.uf,
    est.situacao_cadastral,
    COUNT(*) as total_estabelecimentos
FROM estabelecimento est
GROUP BY est.uf, est.situacao_cadastral;

CREATE UNIQUE INDEX ON mv_estabelecimento_por_uf (uf, situacao_cadastral);

-- Performance monitoring views
CREATE OR REPLACE VIEW v_table_sizes AS
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
FROM pg_tables 
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

CREATE OR REPLACE VIEW v_index_usage AS
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    idx_scan
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;

-- Vacuum and analyze settings for optimal performance
-- Run these commands periodically for maintenance
-- VACUUM ANALYZE empresa;
-- VACUUM ANALYZE estabelecimento;
-- VACUUM ANALYZE socios;
-- VACUUM ANALYZE simples;

-- Refresh materialized views (run after data loads)
-- REFRESH MATERIALIZED VIEW mv_empresa_resumo;
-- REFRESH MATERIALIZED VIEW mv_estabelecimento_por_uf;

-- Comments for documentation
COMMENT ON TABLE empresa IS 'Optimized table for company basic information';
COMMENT ON TABLE estabelecimento IS 'Optimized table for establishment detailed information with extended phone fields';
COMMENT ON TABLE socios IS 'Optimized table for company partners/shareholders information';
COMMENT ON TABLE simples IS 'Optimized table for simplified tax regime information';

COMMENT ON MATERIALIZED VIEW mv_empresa_resumo IS 'Aggregated summary of companies by size and legal nature';
COMMENT ON MATERIALIZED VIEW mv_estabelecimento_por_uf IS 'Establishment count by state and status';

-- Grant permissions (adjust as needed)
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
-- GRANT SELECT ON ALL MATERIALIZED VIEWS IN SCHEMA public TO readonly_user;
