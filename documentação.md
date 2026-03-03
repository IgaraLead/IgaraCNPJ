## **1. Visão Geral do Projeto**

A plataforma tem como objetivo disponibilizar dados públicos do Cadastro Nacional da Pessoa Jurídica (CNPJ), fornecidos mensalmente pela Receita Federal do Brasil (RFB), de forma estruturada, acessível e comercializável. Através de um sistema de assinaturas mensais com **créditos acumulativos**, os usuários podem realizar consultas detalhadas e exportações de dados de empresas brasileiras, utilizando uma interface web moderna e intuitiva.

O grande diferencial competitivo é o modelo de **créditos que nunca expiram enquanto a assinatura estiver ativa**, algo único no mercado brasileiro de dados de CNPJ. A plataforma será acessível exclusivamente via **front-end web**, sem exposição direta de API para usuários. O backend será consumido apenas pelo frontend, garantindo maior segurança e controle. Futuramente, este frontend servirá como **central de SaaS** da empresa, reunindo outros projetos em um mesmo ecossistema.

---

## **2. Objetivos e Escopo**

### **2.1. Objetivos Principais**

- Fornecer acesso rápido e confiável aos dados de CNPJ (empresas, estabelecimentos, sócios, Simples Nacional e tabelas de referência).
- Oferecer um modelo de precificação simples, transparente e justo, baseado em créditos acumulativos.
- Permitir que usuários realizem buscas com filtros avançados (UF, município, CNAE, situação cadastral, porte, etc.) e exportem os resultados em formatos CSV/Excel.
- Garantir escalabilidade e performance através de particionamento dos dados por Unidade Federativa (UF) e de um sistema de **filas de processamento** opcional (controlado por super-admin).
- Disponibilizar cinco planos mensais com preços progressivos e limite de acúmulo de 100.000 créditos.
- Construir um frontend moderno com **glassmorphism** que sirva como hub para futuros SaaS da empresa.
- Incluir uma **área de super-admin** para gestão avançada do sistema, incluindo a ativação/desativação do modo de fila.
- Definir o primeiro super-admin através de variáveis de ambiente (`.env`).

### **2.2. Escopo Inicial (MVP)**

- Dados das 27 UFs disponíveis, com consultas limitadas a **1 estado por vez** (todos os planos).
- Cinco planos de assinatura mensal (sem planos anuais no lançamento).
- Sistema de créditos acumulativos com limite de 100.000 créditos.
- Interface web com design glassmorphism.
- PagSeguro integrado via backend (webhooks) exclusivamente para assinaturas mensais (sem compra avulsa de créditos).
- Painel super-admin com controle de fila, gestão de UFs, logs e outras funcionalidades.
- Sem landing page inicial (será desenvolvida posteriormente).
- Autenticação via JWT com refresh tokens armazenados em httpOnly cookies.

---

## **3. Modelo de Negócio e Planos**

### **3.1. Estrutura de Créditos**

- **1 crédito = R$ 0,01 a R$ 0,03** (dependente do plano).
- Cada consulta detalhada a um CNPJ (todos os dados) consome **1 crédito**.
- Buscas com filtros consomem **1 crédito por CNPJ retornado** (ex.: uma busca que retorna 50 CNPJs consome 50 créditos).
- A exportação dos resultados (CSV/Excel) não tem custo adicional (já inclusa no custo da consulta).
- Créditos são **acumulativos** e **não expiram enquanto a assinatura mensal estiver ativa**. Se a assinatura for cancelada, os créditos ficam inacessíveis, mas são reativados caso o cliente retorne.
- **Limite máximo de acúmulo**: 100.000 créditos por cliente. Ao atingir o teto, novos créditos mensais não são adicionados até que o saldo diminua.

### **3.2. Tabela de Planos Mensais**

| **Plano** | **Preço Mensal** | **Créditos/mês** | **Preço por Crédito** | **Limite Máximo Acumulado** |
| --- | --- | --- | --- | --- |
| **Básico** | R$ 30 | **1.000** | R$ 0,0300 | 100.000 créditos |
| **Profissional** | R$ 60 | **2.400** | R$ 0,0250 | 100.000 créditos |
| **Negócios** | R$ 120 | **6.000** | R$ 0,0200 | 100.000 créditos |
| **Corporativo** | R$ 250 | **16.500** | R$ 0,01515 | 100.000 créditos |
| **Enterprise** | R$ 500 | **50.000** | R$ 0,0100 | 100.000 créditos |

**Características comuns a todos os planos:**

- Acesso a todas as 27 UFs, porém **cada consulta/extração é limitada a um único estado** (escolhido pelo usuário no momento da consulta).
- Suporte a exportação (CSV/Excel) dos resultados.
- Acesso apenas via interface web (sem API pública).

### **3.3. Plano Gratuito (para testes e atração)**

- **Busca unitária**: até 5 consultas por minuto (apenas dados básicos: razão social, situação, UF).
- Não requer cadastro de cartão.
- Sem acesso a exportações.

### **3.4. Funcionamento do Limite de Acumulação**

- O saldo de créditos do cliente **não pode ultrapassar 100.000**.
- Créditos mensais são adicionados no aniversário da assinatura.
- Se o saldo atual + novos créditos > 100.000, o excedente **é perdido**.
- Clientes próximos do limite (acima de 80.000) recebem notificações para usar os créditos.

---

## **4. Arquitetura da Plataforma**

A arquitetura segue o modelo de camadas, com componentes bem definidos e otimizados para performance e baixo custo. A comunicação com o PagSeguro é feita exclusivamente via backend (webhooks) para evitar fraudes.

text

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Front-end     │────▶│      API        │────▶│  PostgreSQL     │
│    (React)      │     │   (FastAPI)     │     │ (particionado)  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        │                       │                       │
        ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  PagSeguro      │◀────│     Redis       │     │    Backup       │
│  (webhooks)     │     │ (cache/fila)    │     │   (storage)     │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### **4.1. Componentes Principais**

| **Componente** | **Tecnologia** | **Função** |
| --- | --- | --- |
| **Front-end Web** | React + TypeScript | Interface do usuário (glassmorphism). Central de SaaS da empresa. |
| **API Backend** | FastAPI (Python) | Camada de negócio: autenticação, consultas, consumo de créditos, integração com PagSeguro (via webhooks). |
| **Banco de Dados** | PostgreSQL 15+ | Armazenamento principal dos dados de CNPJ, particionado por UF. |
| **Cache/Fila** | Redis | Armazenamento de sessões, rate limiting, e **fila de processamento** (quando ativada pelo super-admin). |
| **Processamento de Pagamentos** | PagSeguro (API) | Assinaturas mensais e webhooks (comunicação apenas com backend). |
| **ETL** | Python (scripts internos) | Download, extração, transformação e carga dos dados da RFB. |

### **4.2. Fluxo de Dados (Visão Geral)**

1. **RFB** disponibiliza arquivos mensalmente.
2. **Sistema de ETL** baixa, extrai e transforma os dados.
3. Dados são carregados no **PostgreSQL** em partições por UF.
4. **Usuário** acessa o front-end, escolhe filtros e UF.
5. **API** valida autenticação, verifica saldo de créditos.
6. Se o **modo fila** estiver ativado (configuração super-admin), a solicitação é enfileirada no Redis e processada assincronamente; caso contrário, é executada imediatamente.
7. Resultados são retornados e exibidos.
8. Usuário pode exportar os resultados (CSV/Excel) sem custo adicional.
9. **PagSeguro** envia webhooks para o backend confirmando pagamentos; o backend atualiza assinaturas e créditos.

---

## **5. Fluxo de Dados (ETL)**

### **5.1. Origem dos Dados**

- **Fonte**: Arquivos públicos da Receita Federal disponíveis em `https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/<data>/`
- **Arquivos**: ZIP contendo CSVs com delimitador ponto e vírgula, codificação Latin-1.
- **Tabelas**: empresa, estabelecimento, socios, simples, cnae, moti, munic, natju, pais, quals.

### **5.2. Processo de ETL**

O ETL é executado mensalmente (após a disponibilização dos novos arquivos) e compreende as seguintes etapas:

1. **Descoberta**: Lista todos os arquivos ZIP disponíveis.
2. **Download paralelo**: Baixa apenas os arquivos necessários (com verificação de integridade).
3. **Extração paralela**: Descompacta os ZIPs em diretórios separados.
4. **Classificação**: Identifica cada arquivo por tipo (empresa, estabelecimento, etc.).
5. **Transformação**: Aplica regras de negócio (conversão de formato decimal, limpeza, etc.) e filtra apenas as colunas essenciais (redução de ~33% do volume).
6. **Carga**: Insere os dados no PostgreSQL utilizando **COPY** em chunks, já particionando por UF na tabela de estabelecimentos.
7. **Pós-processamento**: Cria índices específicos por partição e executa `VACUUM ANALYZE`.

### **5.3. Otimizações**

- Leitura em chunks (2 milhões de linhas por vez) para controle de memória.
- Uso de `COPY` para inserção em massa.
- Partições por UF na tabela `estabelecimentos` (e nas tabelas relacionadas, se necessário).
- Índices locais em cada partição (ex.: índice em `cnae_fiscal_principal` na partição `estabelecimentos_sp`).

---

## **6. Banco de Dados e Estrutura**

### **6.1. Modelo de Dados**

O banco é normalizado, com tabelas de referência e tabelas factuais. A tabela principal (`estabelecimentos`) é particionada por UF.

### **Tabelas:**

| **Tabela** | **Descrição** | **Particionada?** |
| --- | --- | --- |
| `empresa` | Dados cadastrais da empresa (cnpj_basico, razao_social, porte, capital) | Não (mas referenciada) |
| `estabelecimentos` | Dados dos estabelecimentos (endereço, telefone, CNAE, situação) | **Sim, por UF** |
| `socios` | Quadro societário | Não (referencia cnpj_basico) |
| `simples` | Opção pelo Simples Nacional e MEI | Não |
| `cnae` | Códigos e descrições da CNAE | Não |
| `munic` | Códigos e nomes de municípios | Não |
| `natju` | Naturezas jurídicas | Não |
| `pais` | Países | Não |
| `quals` | Qualificações de sócios | Não |
| `moti` | Motivos de situação cadastral | Não |

### **6.2. Estrutura de Partição**

sql

```
CREATE TABLE estabelecimentos (
    cnpj_basico VARCHAR(8),
    cnpj_ordem VARCHAR(4),
    cnpj_dv VARCHAR(2),
    uf VARCHAR(2) NOT NULL,
    -- demais colunas...
) PARTITION BY LIST (uf);

-- Partições para cada UF
CREATE TABLE estabelecimentos_sp PARTITION OF estabelecimentos FOR VALUES IN ('SP');
CREATE TABLE estabelecimentos_rj PARTITION OF estabelecimentos FOR VALUES IN ('RJ');
-- ... 27 partições
```

**Vantagens:**

- Consultas que especificam `uf` acessam apenas a partição correspondente, reduzindo I/O.
- Índices menores e mais eficientes.
- Facilidade para backups incrementais por UF.
- Isolamento de performance entre UFs.

### **6.3. Índices Estratégicos (por partição)**

- `(cnae_fiscal_principal)`
- `(situacao_cadastral)`
- `(municipio)`
- `(cep)`
- `(cnpj_basico)` (para join com empresa)

---

## **7. Backend (API)**

### **7.1. Tecnologias**

- **Framework**: FastAPI (Python)
- **Autenticação**: JWT com refresh tokens armazenados em httpOnly cookies.
- **Banco de dados**: asyncpg (conexão assíncrona) + SQLAlchemy Core
- **Cache/Fila**: Redis (para rate limiting, filas de processamento)
- **Pagamentos**: Integração com PagSeguro via SDK oficial; **webhooks** para receber notificações.

### **7.2. Autenticação – JWT com httpOnly Cookies**

### **Por que JWT com cookies?**

- **Stateless**: facilita escalabilidade horizontal.
- **Segurança**: cookies httpOnly protegem contra XSS.
- **CSRF**: mitigado com `SameSite=Strict/Lax` e tokens anti-CSRF em ações sensíveis.
- **Refresh token rotativo**: aumenta a segurança.

### **Fluxo:**

1. **Login**: usuário envia credenciais → backend gera `access_token` (15 min) e `refresh_token` (7 dias), ambos em cookies httpOnly.
2. **Requisições autenticadas**: cookies são enviados automaticamente; backend valida `access_token`.
3. **Refresh**: quando `access_token` expira, frontend chama `/auth/refresh` (sem intervenção do usuário) que usa `refresh_token` para gerar novos tokens.
4. **Logout**: backend limpa os cookies.

### **7.3. Endpoints Principais (todos consumidos apenas pelo frontend)**

### **Autenticação**

- `POST /auth/register` – cria conta (com opção de plano gratuito)
- `POST /auth/login` – retorna cookies com tokens
- `POST /auth/refresh` – renova tokens
- `POST /auth/logout` – limpa cookies
- `GET /auth/me` – informações do usuário (incluindo saldo de créditos)

### **Planos e Pagamentos**

- `GET /plans` – lista planos disponíveis
- `POST /subscription/create` – inicia assinatura (retorna link do PagSeguro)
- `POST /subscription/cancel` – cancela assinatura
- `POST /webhooks/pagseguro` – **rota pública** (mas segura) para receber notificações do PagSeguro (atualiza assinaturas e créditos)

### **Consultas**

- `POST /search` – realiza busca com filtros (obrigatório informar `uf`)
    - Parâmetros: `uf`, `municipio`, `cnae`, `situacao`, `porte`, `q` (texto livre), etc.
    - Retorna lista paginada de CNPJs com dados completos.
    - **Consome créditos** = número de CNPJs retornados.
    - Se o modo fila estiver ativo, retorna imediatamente um `task_id` e processa em background.
- `GET /search/{cnpj}` – consulta unitária por CNPJ (consome 1 crédito)

### **Exportação**

- `POST /export` – solicita exportação dos resultados de uma busca (assíncrono)
    - Parâmetros: mesmos da busca, mais formato (`csv` ou `xlsx`)
    - Retorna `task_id` para acompanhamento
- `GET /export/{task_id}` – status da exportação e link para download (quando pronto)

### **Super-admin**

- `GET /admin/stats` – métricas do sistema
- `POST /admin/config/queue` – ativa/desativa modo fila
- `GET /admin/config/queue` – retorna status atual da fila
- `POST /admin/ufs/toggle` – ativa/desativa UFs
- `GET /admin/logs` – logs de ações destrutivas
- `POST /admin/users/{id}/adjust-credits` – ajuste manual de créditos
- `POST /admin/users/{id}/block` – bloquear/desbloquear usuário

### **7.4. Controle de Créditos**

Cada requisição a endpoints pagos verifica:

1. Se usuário tem assinatura ativa.
2. Se possui créditos suficientes para a operação (estimativa).
3. Ao final, debita os créditos exatos.

**Modelo de dados para créditos:**

sql

```
CREATE TABLE creditos (
    usuario_id INT PRIMARY KEY,
    saldo INT NOT NULL,
    creditos_recebidos INT DEFAULT 0,
    creditos_consumidos INT DEFAULT 0,
    updated_at TIMESTAMP
);

CREATE TABLE creditos_transacoes (
    id SERIAL PRIMARY KEY,
    usuario_id INT,
    tipo VARCHAR(20), -- 'recebimento_mensal', 'consumo', 'estorno'
    quantidade INT,
    motivo TEXT,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

Um job agendado (cron) executa no primeiro dia de cada mês para adicionar os créditos dos planos ativos, respeitando o limite de 100.000.

---

## **8. Front-end Web**

### **8.1. Tecnologias**

- **Framework**: React 18+ com TypeScript
- **UI Library**: Componentes customizados com **glassmorphism** (efeitos de vidro, transparência, blur, cores suaves)
- **Gerenciamento de estado**: React Query (para cache de API) + Zustand (estado global)
- **Formulários**: React Hook Form
- **Tabelas**: TanStack Table (com virtual scrolling para grandes volumes)
- **Estilização**: Styled-components ou Tailwind com plugins para glassmorphism

### **8.2. Arquitetura do Frontend (Central de SaaS)**

O frontend será estruturado para permitir a inclusão futura de outros produtos da empresa. Cada produto será um módulo separado, acessível via rotas específicas, mas compartilhando o mesmo design system e autenticação.

text

```
/src
  /modules
    /cnpj-platform    # Módulo atual (dados CNPJ)
      /components
      /pages
      /hooks
      /services
    /future-product   # Exemplo de futuro módulo
  /shared             # Componentes, hooks e utilitários compartilhados
    /ui               # Botões, cards, modais com glassmorphism
    /auth             # Contexto de autenticação
    /layout           # Layout principal (header, sidebar, etc.)
```

### **8.3. Páginas e Funcionalidades**

### **Páginas Públicas (sem landing page por enquanto)**

- **Login/Registro**: formulários de autenticação com design glassmorphism.

### **Páginas Privadas (após login)**

- **Dashboard**: visão geral do saldo de créditos, status da assinatura, últimas consultas, gráfico de consumo.
- **Consultas**: tela principal com:
    - Seletor de UF (dropdown com todos os estados).
    - Painel de filtros (CNAE, situação, porte, município, etc.).
    - Campo de busca textual (razão social, nome fantasia).
    - Botão "Buscar".
    - Tabela de resultados paginada.
    - Botão "Exportar" (gera CSV/Excel).
- **Histórico**: lista de consultas realizadas e exports com links para download.
- **Planos**: página para upgrade de plano.
- **Configurações**: alterar senha, e-mail, UF padrão.

### **Área Super-admin (acessível apenas para usuários com role `super_admin`)**

- **Dashboard Admin**: métricas do sistema (usuários ativos, consultas por período, uso de recursos).
- **Controle de Fila**: toggle para ativar/desativar o modo fila, com indicador de status e tamanho atual da fila.
- **Gestão de UFs**: painel para ativar/desativar UFs (expansão progressiva) com confirmação.
- **Logs de Ações**: visualização de ações destrutivas.
- **Configurações do Sistema**: parâmetros como limite máximo de créditos, timeout, etc.
- **Gestão de Usuários**: lista de usuários, ajuste manual de créditos, bloqueio.

### **8.4. Design System – Glassmorphism**

- Fundos com blur e transparência.
- Cards com bordas suaves, sombras e efeito "vidro fosco".
- Paleta de cores: tons pastel com contrastes adequados para acessibilidade.
- Animações suaves e microinterações.

---

## **9. Sistema de Filas (Controle pelo Super-Admin)**

### **9.1. Objetivo**

Permitir que o super-admin ative um modo de **processamento assíncrono** para consultas e exportações, evitando sobrecarga do sistema em momentos de pico. Quando ativado, as solicitações dos usuários são enfileiradas e processadas em background.

### **9.2. Implementação**

- Utilizar **Redis** como broker de fila.
- Biblioteca: **Celery** (Python) ou **RQ** (simples) para processamento assíncrono.
- Quando o modo fila está **desativado**: as consultas são executadas síncronamente (resposta imediata).
- Quando o modo fila está **ativado**:
    - A requisição `POST /search` retorna imediatamente um `task_id` e status "processing".
    - O frontend faz polling em um endpoint `GET /search/task/{task_id}` para obter o resultado quando pronto.
    - O worker processa a consulta em background e armazena o resultado em cache (Redis) com expiração.

### **9.3. Controle no Super-admin**

- Interface com toggle:
    - **Modo fila**: [ATIVADO / DESATIVADO]
    - Exibição do número de tarefas na fila.
    - Possibilidade de limpar a fila (cuidado!).

---

## **10. Definição do Primeiro Super-Admin via .env**

### **10.1. Variáveis no .env**

env

```
# Super Admin Inicial
ADMIN_NAME="Administrador"
ADMIN_EMAIL="admin@seudominio.com"
ADMIN_PASSWORD="s3nh@F0rt3!"
ADMIN_PHONE="11999999999"
```

### **10.2. Funcionamento**

Durante a inicialização da aplicação (ou em um script de seed), o backend verifica se já existe algum usuário com role `super_admin`. Caso não exista, cria um novo usuário com as credenciais fornecidas.

python

```
# Exemplo em FastAPI startup event
@app.on_event("startup")
def create_first_superadmin():
    if not db.query(Usuario).filter(Usuario.role == "super_admin").first():
        hashed = hash_password(os.getenv("ADMIN_PASSWORD"))
        admin = Usuario(
            nome=os.getenv("ADMIN_NAME"),
            email=os.getenv("ADMIN_EMAIL"),
            senha_hash=hashed,
            role="super_admin",
            ativo=True
        )
        db.add(admin)
        db.commit()
```

### **10.3. Outras Variáveis Essenciais no .env**

env

```
# ===== Banco de Dados =====
DB_HOST=localhost
DB_PORT=5432
DB_NAME=cnpj_platform
DB_USER=postgres
DB_PASSWORD=postgres

# ===== Redis =====
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# ===== PagSeguro =====
PAGSEGURO_EMAIL=seu@email.com
PAGSEGURO_TOKEN=seu_token
PAGSEGURO_SANDBOX=true
PAGSEGURO_APP_ID=app_id
PAGSEGURO_APP_KEY=app_key

# ===== JWT =====
JWT_SECRET_KEY=chave_super_secreta
JWT_REFRESH_SECRET_KEY=outra_chave
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# ===== Configurações da Plataforma =====
LIMITE_CREDITOS_MAXIMO=100000
MODO_FILA_PADRAO=false
TIMEOUT_CONSULTA_SEGUNDOS=30
CHUNK_SIZE_EXPORTACAO=10000

# ===== ETL =====
OUTPUT_FILES_PATH=./downloads
EXTRACTED_FILES_PATH=./extracted
FILES_DATE=2024-01
MAX_WORKERS=4
```

---

## **11. Infraestrutura e Hospedagem**

### **11.1. Máquina Inicial**

| **Recurso** | **Especificação** |
| --- | --- |
| vCPU | 2 cores |
| RAM | 8 GB |
| Armazenamento | 100 GB NVMe |
| Transferência | 8 TB |
| **Custo** | **R$ 100/mês** |

Esta máquina é suficiente para atender até **70-80 clientes** ativos, considerando que as consultas são limitadas a 1 estado por vez e os dados cabem parcialmente em cache. O modo fila, quando ativado, ajuda a suavizar picos.

### **11.2. Serviços Adicionais**

- **Redis**: pode rodar na mesma máquina (consumo adicional de RAM ~1 GB).
- **Backups**: armazenamento em nuvem (ex.: S3) para backups diários do banco.
- **CDN**: Cloudflare para acelerar entrega de assets estáticos.

### **11.3. Dimensionamento Futuro**

- Ao atingir **100+ clientes**, avaliar upgrade para máquina de 16 GB RAM (R$ 180/mês) ou 32 GB RAM (R$ 330/mês).
- Se o modo fila se tornar padrão, considerar workers separados para processamento assíncrono.

---

## **12. Segurança e Conformidade**

### **12.1. Segurança da Aplicação**

- **Autenticação**: JWT com refresh tokens em cookies httpOnly.
- **HTTPS**: obrigatório em produção (certificado Let's Encrypt).
- **Rate limiting**: por IP e por usuário (Redis) para evitar abusos.
- **Proteção contra ataques**: validação de entrada, prepared statements, CORS configurado.
- **CSRF**: uso de `SameSite=Strict` em cookies e tokens anti-CSRF para ações sensíveis.

### **12.2. Conformidade Legal**

- **Origem dos dados**: Dados públicos da RFB (Lei 12.527/2011). Obrigatório atribuir fonte nos resultados.
- **LGPD**: Dados de pessoas jurídicas não são protegidos; dados de sócios (pessoas físicas) são tratados com base no legítimo interesse. A plataforma terá:
    - Política de Privacidade clara.
    - Canal para exercício de direitos (acesso, correção, exclusão).
- **Termos de Uso**: Estabelecem responsabilidades do usuário e limites de uso.

---

## **13. Painel Super-Admin (Funcionalidades Detalhadas)**

| **Funcionalidade** | **Descrição** |
| --- | --- |
| **Dashboard** | Gráficos de usuários ativos, consultas, créditos consumidos, uso de CPU/RAM. |
| **Controle de Fila** | Toggle para ativar/desativar modo fila. Exibe tamanho da fila, tarefas processadas, tempo médio. |
| **Gestão de UFs** | Lista de UFs com indicador de ativa. Botão para ativar/desativar (ação destrutiva requer confirmação). |
| **Logs de Ações** | Tabela com ações de super-admin (ativação/desativação de UF, mudanças de configuração). |
| **Configurações do Sistema** | Parâmetros como `limite_max_creditos`, `timeout_consulta`, `max_ufs_por_consulta` (futuro). |
| **Gestão de Usuários** | Lista de usuários, possibilidade de bloquear, ajustar créditos manualmente. |
| **Relatórios** | Gerar relatórios em CSV/Excel com dados do sistema. |
| **Ferramentas de Manutenção** | Executar ETL manual, limpar cache, reindexar tabelas. |

---

## **14. Projeção Financeira**

| **Plano** | **Preço** | **% estimada de clientes** | **Clientes (100 total)** | **Receita** |
| --- | --- | --- | --- | --- |
| Básico | R$ 30 | 40% | 40 | R$ 1.200 |
| Profissional | R$ 60 | 30% | 30 | R$ 1.800 |
| Negócios | R$ 120 | 15% | 15 | R$ 1.800 |
| Corporativo | R$ 250 | 10% | 10 | R$ 2.500 |
| Enterprise | R$ 500 | 5% | 5 | R$ 2.500 |
| **Total** |  | **100%** | **100** | **R$ 9.800** |

**Custo do servidor**: R$ 100/mês

**Lucro estimado**: **R$ 9.700/mês**

Break-even: **1 cliente** já cobre o custo do servidor.

---

## **15. Roadmap de Implementação**

### **Fase 1: Preparação (Meses 1-2)**

- Implementar ETL com particionamento por UF.
- Criar banco de dados e tabelas.
- Desenvolver backend com autenticação JWT (cookies), planos, créditos e webhooks PagSeguro.
- Implementar sistema de filas (Redis + Celery/RQ) com controle super-admin.
- Criar frontend base com design glassmorphism e estrutura modular (central SaaS).
- Desenvolver área de super-admin (controle de fila, UFs, logs).
- Configurar variáveis de ambiente para primeiro super-admin.

### **Fase 2: Lançamento (Mês 3)**

- Lançar planos mensais.
- Ativar sistema de créditos acumulativos com limite de 100.000.
- Disponibilizar busca com filtros (1 UF).
- Implementar exportação CSV/Excel.
- Onboarding de primeiros clientes (10-20).

### **Fase 3: Crescimento (Meses 4-6)**

- Monitorar performance e métricas de uso.
- Atingir 50+ clientes.
- Coletar dados para ajustes e futuros planos anuais.
- Melhorias de UI/UX baseadas em feedback.

### **Fase 4: Expansão (Mês 7+)**

- Avaliar lançamento de planos anuais (com desconto).
- Avaliar upgrade de infraestrutura.
- Implementar réplicas de leitura se necessário.
- Desenvolver parcerias e programa de indicações.

---

## **16. Conclusão**

A plataforma foi cuidadosamente planejada para oferecer um serviço de alto valor com custos operacionais extremamente baixos, graças à arquitetura otimizada (particionamento por UF, créditos acumulativos, máquina de R$ 100/mês). O modelo de negócio é simples, transparente e com preços muito competitivos em relação ao mercado.

O grande diferencial – **créditos que não expiram enquanto a assinatura estiver ativa** – posiciona a plataforma como a escolha ideal para profissionais e empresas que realmente precisam de dados de CNPJ com regularidade e sem desperdício.

A arquitetura de frontend modular e o design glassmorphism preparam o terreno para a visão de longo prazo: uma **central de SaaS** que reunirá diversos produtos da empresa. A área de super-admin e o controle de filas garantem governança e escalabilidade.

Com uma execução disciplinada e foco na experiência do usuário, a plataforma tem grande potencial para se tornar referência no fornecimento de dados de CNPJ no Brasil.