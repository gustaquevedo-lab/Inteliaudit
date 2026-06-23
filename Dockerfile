FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# System deps - full set for runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ \
    libpq-dev \
    libffi-dev \
    libssl-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libdbus-1-3 \
    libxml2 \
    libxslt1.1 \
    libfreetype6 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "python-multipart>=0.0.9" \
    "sqlalchemy[asyncio]>=2.0" \
    "asyncpg>=0.29" \
    "aiosqlite>=0.20" \
    "alembic>=1.13" \
    "pydantic[email]>=2.7" \
    "pydantic-settings>=2.3" \
    "python-dotenv>=1.0" \
    "playwright>=1.44" \
    "httpx>=0.27" \
    "openpyxl>=3.1" \
    "lxml>=5.2" \
    "xmltodict>=0.13" \
    "pdfplumber>=0.11" \
    "jinja2>=3.1" \
    "python-docx>=1.1" \
    "weasyprint>=62" \
    "slowapi>=0.1.9" \
    "python-jose[cryptography]>=3.3" \
    "passlib[bcrypt]>=1.7" \
    "bcrypt>=4.0" \
    "cryptography>=42.0" \
    "anthropic>=0.28" \
    "google-generativeai>=0.5" \
    "boto3>=1.34" \
    "resend>=2.0" \
    "posthog>=3.5" \
    "click>=8.1" \
    "rich>=13.7" \
    "opentelemetry-api>=1.24" \
    "opentelemetry-sdk>=1.24" \
    "opentelemetry-instrumentation-fastapi>=0.45b0" \
    "opentelemetry-instrumentation-sqlalchemy>=0.45b0" \
    "opentelemetry-instrumentation-httpx>=0.45b0" \
    "opentelemetry-exporter-otlp-proto-grpc>=1.24"

RUN playwright install --with-deps chromium 2>/dev/null || true

# Make entrypoint executable
RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/bin/bash", "entrypoint.sh"]
