FROM python:3.11-slim

WORKDIR /app

# Dependências de sistema para psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Instalar dependências Python (layer cacheável)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY api/ ./api/

# Criar diretórios de trabalho
RUN mkdir -p /app/exports /app/downloads /app/extracted

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
