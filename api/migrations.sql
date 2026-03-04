-- ============================================================
-- Plataforma CNPJ (igarateca) - Database Schema
-- PostgreSQL 15+
-- ============================================================

-- ─── Application Tables ─────────────────────────────────────

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome VARCHAR(100) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    senha_hash VARCHAR(255) NOT NULL,
    telefone VARCHAR(20),
    role VARCHAR(20) DEFAULT 'user',
    ativo BOOLEAN DEFAULT TRUE,
    criado_em TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios (email);
CREATE INDEX IF NOT EXISTS idx_usuarios_role ON usuarios (role);

CREATE TABLE IF NOT EXISTS creditos (
    usuario_id INT PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    saldo INT NOT NULL DEFAULT 0,
    creditos_recebidos INT DEFAULT 0,
    creditos_consumidos INT DEFAULT 0,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS creditos_transacoes (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo VARCHAR(30),  -- recebimento_mensal, consumo, estorno, ajuste_manual
    quantidade INT,
    motivo TEXT,
    metadata_extra JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_creditos_transacoes_usuario ON creditos_transacoes (usuario_id);
CREATE INDEX IF NOT EXISTS idx_creditos_transacoes_created ON creditos_transacoes (created_at DESC);

CREATE TABLE IF NOT EXISTS assinaturas (
    id SERIAL PRIMARY KEY,
    usuario_id INT UNIQUE NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    plano VARCHAR(30) NOT NULL,  -- basico, profissional, negocios, corporativo, enterprise
    status VARCHAR(20) DEFAULT 'ativa',  -- ativa, cancelada, suspensa, substituida
    pagseguro_subscription_id VARCHAR(100),
    manual BOOLEAN DEFAULT FALSE,
    data_inicio TIMESTAMP DEFAULT NOW(),
    data_validade TIMESTAMP,  -- null = permanente
    data_proximo_ciclo TIMESTAMP,
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_assinaturas_status ON assinaturas (status);

CREATE TABLE IF NOT EXISTS logs_acoes (
    id SERIAL PRIMARY KEY,
    usuario_id INT REFERENCES usuarios(id) ON DELETE SET NULL,
    acao VARCHAR(100) NOT NULL,
    detalhes JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_logs_acoes_created ON logs_acoes (created_at DESC);

CREATE TABLE IF NOT EXISTS config_sistema (
    chave VARCHAR(100) PRIMARY KEY,
    valor TEXT NOT NULL,
    atualizado_em TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS historico_buscas (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    search_id VARCHAR(36) UNIQUE NOT NULL,
    params JSONB NOT NULL DEFAULT '{}',
    total_results INT DEFAULT 0,
    status VARCHAR(30) DEFAULT 'realizada',
    credits_consumed INT DEFAULT 0,
    file_id VARCHAR(36),
    quantidade_processada INT,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_historico_buscas_usuario ON historico_buscas (usuario_id);
CREATE INDEX IF NOT EXISTS idx_historico_buscas_search_id ON historico_buscas (search_id);
CREATE INDEX IF NOT EXISTS idx_historico_buscas_created ON historico_buscas (created_at DESC);

-- Add columns if table already exists (idempotent)
ALTER TABLE historico_buscas ADD COLUMN IF NOT EXISTS file_id VARCHAR(36);
ALTER TABLE historico_buscas ADD COLUMN IF NOT EXISTS quantidade_processada INT;


-- ─── RFB Reference Tables ──────────────────────────────────

CREATE TABLE IF NOT EXISTS cnae (
    codigo VARCHAR(10) PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS moti (
    codigo VARCHAR(10) PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS munic (
    codigo VARCHAR(10) PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS natju (
    codigo VARCHAR(10) PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS pais (
    codigo VARCHAR(10) PRIMARY KEY,
    descricao TEXT
);

CREATE TABLE IF NOT EXISTS quals (
    codigo VARCHAR(10) PRIMARY KEY,
    descricao TEXT
);


-- ─── RFB Factual Tables ────────────────────────────────────

CREATE TABLE IF NOT EXISTS empresa (
    cnpj_basico VARCHAR(8) PRIMARY KEY,
    razao_social TEXT,
    natureza_juridica INT,
    qualificacao_responsavel INT,
    capital_social NUMERIC(18,2),
    porte_empresa INT,
    ente_federativo_responsavel TEXT
);
CREATE INDEX IF NOT EXISTS idx_empresa_razao ON empresa USING gin(to_tsvector('portuguese', razao_social));

CREATE TABLE IF NOT EXISTS estabelecimentos (
    cnpj_basico VARCHAR(8) NOT NULL,
    cnpj_ordem VARCHAR(4) NOT NULL,
    cnpj_dv VARCHAR(2) NOT NULL,
    identificador_matriz_filial INT,
    nome_fantasia TEXT,
    situacao_cadastral INT,
    data_situacao_cadastral VARCHAR(8),
    motivo_situacao_cadastral INT,
    nome_cidade_exterior TEXT,
    pais INT,
    data_inicio_atividade VARCHAR(8),
    cnae_fiscal_principal VARCHAR(10),
    cnae_fiscal_secundaria TEXT,
    tipo_logradouro VARCHAR(20),
    logradouro TEXT,
    numero VARCHAR(20),
    complemento TEXT,
    bairro VARCHAR(100),
    cep VARCHAR(10),
    uf VARCHAR(2) NOT NULL,
    municipio INT,
    ddd_1 VARCHAR(5),
    telefone_1 VARCHAR(15),
    ddd_2 VARCHAR(5),
    telefone_2 VARCHAR(15),
    ddd_fax VARCHAR(5),
    fax VARCHAR(15),
    correio_eletronico TEXT,
    situacao_especial TEXT,
    data_situacao_especial VARCHAR(8),
    PRIMARY KEY (cnpj_basico, cnpj_ordem, cnpj_dv, uf)
) PARTITION BY LIST (uf);


-- ─── Create all 27 UF partitions ───────────────────────────

CREATE TABLE IF NOT EXISTS estabelecimentos_ac PARTITION OF estabelecimentos FOR VALUES IN ('AC');
CREATE TABLE IF NOT EXISTS estabelecimentos_al PARTITION OF estabelecimentos FOR VALUES IN ('AL');
CREATE TABLE IF NOT EXISTS estabelecimentos_am PARTITION OF estabelecimentos FOR VALUES IN ('AM');
CREATE TABLE IF NOT EXISTS estabelecimentos_ap PARTITION OF estabelecimentos FOR VALUES IN ('AP');
CREATE TABLE IF NOT EXISTS estabelecimentos_ba PARTITION OF estabelecimentos FOR VALUES IN ('BA');
CREATE TABLE IF NOT EXISTS estabelecimentos_ce PARTITION OF estabelecimentos FOR VALUES IN ('CE');
CREATE TABLE IF NOT EXISTS estabelecimentos_df PARTITION OF estabelecimentos FOR VALUES IN ('DF');
CREATE TABLE IF NOT EXISTS estabelecimentos_es PARTITION OF estabelecimentos FOR VALUES IN ('ES');
CREATE TABLE IF NOT EXISTS estabelecimentos_go PARTITION OF estabelecimentos FOR VALUES IN ('GO');
CREATE TABLE IF NOT EXISTS estabelecimentos_ma PARTITION OF estabelecimentos FOR VALUES IN ('MA');
CREATE TABLE IF NOT EXISTS estabelecimentos_mg PARTITION OF estabelecimentos FOR VALUES IN ('MG');
CREATE TABLE IF NOT EXISTS estabelecimentos_ms PARTITION OF estabelecimentos FOR VALUES IN ('MS');
CREATE TABLE IF NOT EXISTS estabelecimentos_mt PARTITION OF estabelecimentos FOR VALUES IN ('MT');
CREATE TABLE IF NOT EXISTS estabelecimentos_pa PARTITION OF estabelecimentos FOR VALUES IN ('PA');
CREATE TABLE IF NOT EXISTS estabelecimentos_pb PARTITION OF estabelecimentos FOR VALUES IN ('PB');
CREATE TABLE IF NOT EXISTS estabelecimentos_pe PARTITION OF estabelecimentos FOR VALUES IN ('PE');
CREATE TABLE IF NOT EXISTS estabelecimentos_pi PARTITION OF estabelecimentos FOR VALUES IN ('PI');
CREATE TABLE IF NOT EXISTS estabelecimentos_pr PARTITION OF estabelecimentos FOR VALUES IN ('PR');
CREATE TABLE IF NOT EXISTS estabelecimentos_rj PARTITION OF estabelecimentos FOR VALUES IN ('RJ');
CREATE TABLE IF NOT EXISTS estabelecimentos_rn PARTITION OF estabelecimentos FOR VALUES IN ('RN');
CREATE TABLE IF NOT EXISTS estabelecimentos_ro PARTITION OF estabelecimentos FOR VALUES IN ('RO');
CREATE TABLE IF NOT EXISTS estabelecimentos_rr PARTITION OF estabelecimentos FOR VALUES IN ('RR');
CREATE TABLE IF NOT EXISTS estabelecimentos_rs PARTITION OF estabelecimentos FOR VALUES IN ('RS');
CREATE TABLE IF NOT EXISTS estabelecimentos_sc PARTITION OF estabelecimentos FOR VALUES IN ('SC');
CREATE TABLE IF NOT EXISTS estabelecimentos_se PARTITION OF estabelecimentos FOR VALUES IN ('SE');
CREATE TABLE IF NOT EXISTS estabelecimentos_sp PARTITION OF estabelecimentos FOR VALUES IN ('SP');
CREATE TABLE IF NOT EXISTS estabelecimentos_to PARTITION OF estabelecimentos FOR VALUES IN ('TO');


-- ─── Indexes per partition (strategic) ─────────────────────
-- These are critical for search performance.

DO $$
DECLARE
    uf_code TEXT;
    uf_list TEXT[] := ARRAY['ac','al','am','ap','ba','ce','df','es','go','ma',
                            'mg','ms','mt','pa','pb','pe','pi','pr','rj','rn',
                            'ro','rr','rs','sc','se','sp','to'];
BEGIN
    FOREACH uf_code IN ARRAY uf_list LOOP
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_estab_%s_cnpj ON estabelecimentos_%s (cnpj_basico)', uf_code, uf_code);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_estab_%s_cnae ON estabelecimentos_%s (cnae_fiscal_principal)', uf_code, uf_code);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_estab_%s_sit ON estabelecimentos_%s (situacao_cadastral)', uf_code, uf_code);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_estab_%s_mun ON estabelecimentos_%s (municipio)', uf_code, uf_code);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_estab_%s_cep ON estabelecimentos_%s (cep)', uf_code, uf_code);
    END LOOP;
END $$;


-- ─── Socios ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS socios (
    cnpj_basico VARCHAR(8) NOT NULL,
    identificador_socio INT,
    nome_socio TEXT,
    cpf_cnpj_socio VARCHAR(14),
    qualificacao_socio INT,
    data_entrada_sociedade VARCHAR(8),
    pais INT,
    representante_legal VARCHAR(14),
    nome_representante TEXT,
    qualificacao_representante INT,
    faixa_etaria INT
);
CREATE INDEX IF NOT EXISTS idx_socios_cnpj ON socios (cnpj_basico);

-- ─── Simples ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS simples (
    cnpj_basico VARCHAR(8) PRIMARY KEY,
    opcao_simples VARCHAR(2),
    data_opcao_simples VARCHAR(8),
    data_exclusao_simples VARCHAR(8),
    opcao_mei VARCHAR(2),
    data_opcao_mei VARCHAR(8),
    data_exclusao_mei VARCHAR(8)
);


-- ─── Default system config ─────────────────────────────────

INSERT INTO config_sistema (chave, valor) VALUES ('modo_fila', 'false') ON CONFLICT DO NOTHING;
INSERT INTO config_sistema (chave, valor) VALUES ('limite_creditos', '100000') ON CONFLICT DO NOTHING;
