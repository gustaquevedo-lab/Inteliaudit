#!/usr/bin/env bash
# ============================================================
# Inteliaudit — Respaldo diario de base de datos a Cloudflare R2
# ============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${APP_DIR}"

# Cargar entorno virtual si existe
if [ -d ".venv" ]; then
    PYTHON_BIN=".venv/bin/python"
elif [ -d "venv" ]; then
    PYTHON_BIN="venv/bin/python"
else
    PYTHON_BIN="python3"
fi

echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Iniciando backup automático Inteliaudit..."
${PYTHON_BIN} -m storage.backup_postgres
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Proceso de backup finalizado exitosamente."
