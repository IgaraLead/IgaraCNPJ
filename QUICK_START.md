# RFB ETL - Quick Start Guide

This is a quick start guide for the optimized RFB ETL process.

## 🚀 Quick Setup (Docker - Recommended)

1. **Clone and navigate to the project**:
   ```bash
   git clone https://github.com/judsonjuniorr/Receita_Federal_do_Brasil_-_Dados_Publicos_CNPJ.git
   cd Receita_Federal_do_Brasil_-_Dados_Publicos_CNPJ
   ```

2. **Start the database**:
   ```bash
   docker-compose up -d postgres
   ```

3. **Run the ETL process**:
   ```bash
   docker-compose --profile etl up etl
   ```

That's it! The ETL process will:
- Download all RFB files automatically
- Extract and process the data
- Load it into the PostgreSQL database
- Create optimized indexes

## 🏃‍♂️ Quick Local Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup database**:
   ```bash
   # Create PostgreSQL database
   createdb Dados_RFB
   
   # Run schema creation
   psql -d Dados_RFB -f code/database_schema.sql
   ```

3. **Configure environment**:
   ```bash
   cp code/.env.example code/.env
   # Edit .env with your database credentials
   ```

4. **Run ETL**:
   ```bash
   cd code
   python etl_orchestrator.py
   ```

## ⚡ Quick Performance Tips

For faster processing on powerful machines:
```bash
# Set these in your .env file
MAX_WORKERS=8
BATCH_SIZE=1000000
CHUNK_SIZE=8192
```

For limited memory systems:
```bash
MAX_WORKERS=2
BATCH_SIZE=500000
CHUNK_SIZE=2048
```

## 📊 Quick Database Access

After completion, access your data:

```sql
-- Companies by state
SELECT uf, COUNT(*) as total
FROM estabelecimento 
GROUP BY uf 
ORDER BY total DESC;

-- Active companies
SELECT COUNT(*) as active_companies
FROM estabelecimento 
WHERE situacao_cadastral = 2;

-- Use materialized views for aggregated data
SELECT * FROM mv_empresa_resumo;
SELECT * FROM mv_estabelecimento_por_uf;
```

## 🔗 Quick Links

- [Full Documentation](README_OPTIMIZED.md)
- [Database Schema](code/database_schema.sql)
- [Configuration Examples](code/.env.example)
- [Original Project](https://github.com/judsonjuniorr/Receita_Federal_do_Brasil_-_Dados_Publicos_CNPJ)

---

**Total estimated time**: 3-6 hours depending on your internet connection and hardware.

**Disk space needed**: ~100GB for downloads + extracted files + database

**Memory recommended**: 8GB+ RAM for optimal performance
