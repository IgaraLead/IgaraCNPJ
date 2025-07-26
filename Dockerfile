# Optimized Dockerfile for RFB ETL process
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Create directories for data
RUN mkdir -p /app/data/downloads /app/data/extracted /app/logs

# Copy requirements first for better layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY code/ ./code/
COPY LICENSE README.md ./

# Create non-root user
RUN useradd --create-home --shell /bin/bash etl_user && \
    chown -R etl_user:etl_user /app

# Switch to non-root user
USER etl_user

# Set Python path
ENV PYTHONPATH=/app/code

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command
CMD ["python", "code/etl_orchestrator.py"]
