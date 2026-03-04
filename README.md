# IgaraLead Entity

Plataforma web para consulta de dados públicos do Cadastro Nacional da Pessoa Jurídica (CNPJ), disponibilizados pela Receita Federal do Brasil (RFB). Oferece acesso estruturado, buscas com filtros avançados e exportação de dados através de um sistema de assinaturas com créditos acumulativos.

## Visão Geral

A plataforma permite que usuários consultem informações de empresas brasileiras — como razão social, endereço, CNAE, situação cadastral, quadro societário e opção pelo Simples Nacional — a partir dos dados abertos da Receita Federal, que são atualizados mensalmente.

### Principais funcionalidades

- **Busca com filtros avançados**: UF, município, CNAE, situação cadastral, porte da empresa, entre outros.
- **Exportação de resultados**: Download em CSV/Excel dos dados consultados.
- **Sistema de créditos acumulativos**: Créditos que não expiram enquanto a assinatura estiver ativa.
- **Painel administrativo**: Área de super-admin para gestão de UFs, controle de fila de processamento e logs.
- **Integração com PagSeguro**: Assinaturas mensais gerenciadas via webhooks no backend.

## Arquitetura

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │────▶│   Backend       │────▶│  PostgreSQL     │
│   (React/TS)    │     │   (FastAPI)     │     │ (particionado)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              ┌──────────┐ ┌──────────┐ ┌──────────┐
              │  Redis   │ │  MinIO   │ │ PagSeguro│
              │(cache/   │ │  (S3)    │ │(webhooks)│
              │ fila)    │ │          │ │          │
              └──────────┘ └──────────┘ └──────────┘
```

| Componente | Tecnologia | Função |
|---|---|---|
| **Frontend** | React + TypeScript + Vite | Interface do usuário com design glassmorphism |
| **Backend** | FastAPI (Python) | API REST: autenticação, consultas, créditos, pagamentos |
| **Banco de Dados** | PostgreSQL 16 | Armazenamento dos dados de CNPJ, particionado por UF |
| **Cache / Fila** | Redis | Sessões, rate limiting e fila de processamento assíncrona |
| **Object Storage** | MinIO (S3-compatível) | Armazenamento de arquivos exportados |
| **Pagamentos** | PagSeguro | Assinaturas mensais via webhooks |
| **ETL** | Python (scripts internos) | Download, transformação e carga dos dados da RFB |

## ETL (Extract, Transform, Load)

O pipeline de ETL é responsável por baixar, transformar e carregar os dados públicos da Receita Federal no banco de dados. Ele é executado mensalmente após a publicação de novos arquivos pela RFB.

### Etapas do processo

1. **Descoberta** — Lista os arquivos ZIP disponíveis no servidor da RFB.
2. **Download paralelo** — Baixa os arquivos necessários com verificação de integridade.
3. **Extração paralela** — Descompacta os ZIPs em diretórios separados.
4. **Classificação** — Identifica cada arquivo por tipo (empresa, estabelecimento, sócios, etc.).
5. **Transformação** — Aplica regras de negócio, conversão de formatos e filtragem de colunas.
6. **Carga** — Insere os dados no PostgreSQL via `COPY` em chunks, particionando por UF.
7. **Pós-processamento** — Cria índices por partição e executa `VACUUM ANALYZE`.

### Otimizações

- Leitura em chunks de 2 milhões de linhas para controle de memória.
- Inserção em massa via `COPY`.
- Particionamento da tabela `estabelecimentos` por UF (27 partições).
- Índices locais em cada partição.

### Créditos

O ETL desta plataforma foi baseado no repositório [Receita Federal do Brasil - Dados Públicos CNPJ](https://github.com/judsonjuniorr/Receita_Federal_do_Brasil_-_Dados_Publicos_CNPJ), de autoria de [judsonjuniorr](https://github.com/judsonjuniorr), licenciado sob a [Licença MIT](https://github.com/judsonjuniorr/Receita_Federal_do_Brasil_-_Dados_Publicos_CNPJ/blob/main/LICENSE).

## Como executar

### Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/install/)

### Configuração

```bash
# Clone o repositório
git clone https://github.com/igaralead/entity.git
cd entity

# Configure as variáveis de ambiente
cp .env.example .env
# Edite o arquivo .env com suas configurações
```

### Execução

```bash
# Subir todos os serviços
docker compose up -d --build

# Verificar os logs
docker compose logs -f backend
```

A aplicação estará disponível em:

- **Frontend**: http://localhost:3000
- **Backend (API)**: http://localhost:8000

### Variáveis de ambiente importantes

| Variável | Descrição | Padrão |
|---|---|---|
| `ADMIN_EMAIL` | E-mail do super-admin inicial | — |
| `ADMIN_PASSWORD` | Senha do super-admin inicial | — |
| `DB_NAME` | Nome do banco de dados | `cnpj_platform` |
| `DB_USER` | Usuário do PostgreSQL | `postgres` |
| `DB_PASSWORD` | Senha do PostgreSQL | `postgres` |
| `JWT_SECRET_KEY` | Chave secreta para tokens JWT | — |
| `PAGSEGURO_TOKEN` | Token de integração com PagSeguro | — |
| `FRONTEND_URL` | URL do frontend (para CORS) | `http://localhost:3000` |

Consulte o arquivo [.env.example](.env.example) para a lista completa de variáveis.

## Estrutura do projeto

```
entity/
├── api/                    # Backend (FastAPI)
│   ├── main.py             # Entry point da aplicação
│   ├── auth.py             # Autenticação (JWT)
│   ├── search.py           # Endpoints de busca
│   ├── export.py           # Exportação CSV/Excel
│   ├── credits.py          # Gestão de créditos
│   ├── plans.py            # Planos de assinatura
│   ├── admin.py            # Painel super-admin
│   ├── pagseguro.py        # Integração PagSeguro
│   ├── models.py           # Modelos SQLAlchemy
│   ├── schemas.py          # Schemas Pydantic
│   ├── storage.py          # Integração MinIO/S3
│   └── etl/                # Pipeline ETL
│       ├── etl_orchestrator.py
│       ├── config/         # Configurações do ETL
│       ├── database/       # Gestão do banco (ETL)
│       ├── download/       # Download e extração
│       └── processing/     # Transformação dos dados
├── frontend/               # Frontend (React + TypeScript)
│   └── src/
│       ├── App.tsx
│       ├── modules/        # Páginas da aplicação
│       └── shared/         # Componentes e utilitários
├── docker-compose.yml      # Orquestração dos serviços
├── requirements.txt        # Dependências Python
└── .env.example            # Modelo de variáveis de ambiente
```

## Licença

Este projeto é software proprietário da **IgaraLead**. Todos os direitos reservados. Consulte o arquivo [LICENSE](LICENSE) para mais detalhes.

O módulo ETL (`api/etl/`) é baseado em trabalho de terceiros e está licenciado sob a [Licença MIT](api/etl/LICENSE).
