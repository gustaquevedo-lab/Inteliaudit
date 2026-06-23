FROM python:3.12-slim

WORKDIR /app

# System deps for Playwright + WeasyPrint
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev libffi-dev libcairo2 libpango-1.0-0 libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 libdbus-1-3 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY . .

RUN playwright install --with-deps chromium 2>/dev/null || true

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
