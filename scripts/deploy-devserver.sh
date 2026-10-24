#!/usr/bin/env bash
set -e

SERVER_IP="100.72.38.119"
TARGET_DIR="/home/dev-server/apps/inteliaudit"

echo "=== DEPLOYING INTELIAUDIT TO DEV-SERVER (${SERVER_IP}) ==="

# 1. Verificar conectividad
echo "[1/4] Verificando conectividad Tailscale SSH..."
ssh -o BatchMode=yes -o ConnectTimeout=5 "root@${SERVER_IP}" "echo 'Dev-Server conectado correctamente.'"

# 2. Sincronizar archivos del backend y configuración
echo "[2/4] Sincronizando código fuente con rsync..."
rsync -avz --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'venv' \
  --exclude '.local-node-modules' \
  --exclude 'node_modules' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.pytest_cache' \
  --exclude 'storage' \
  --exclude '.env' \
  --exclude 'inteliaudit.db' \
  --exclude 'ui-web/node_modules' \
  --exclude 'ui-web/dist' \
  ./ "root@${SERVER_IP}:${TARGET_DIR}/"

# Asegurar permisos correctos para el usuario dev-server
ssh "root@${SERVER_IP}" "chown -R dev-server:dev-server ${TARGET_DIR} && chmod -R u+rwX ${TARGET_DIR}"

# 3. Aplicar migraciones Alembic
echo "[3/4] Ejecutando migraciones Alembic en PostgreSQL..."
ssh "root@${SERVER_IP}" "su - dev-server -c 'cd ${TARGET_DIR} && .venv/bin/alembic upgrade head'"

# 4. Reiniciar servicio en PM2
echo "[4/4] Reiniciando inteliaudit-api en PM2..."
ssh "root@${SERVER_IP}" "su - dev-server -c 'cd ${TARGET_DIR} && pm2 startOrRestart ecosystem.config.js --update-env'"

echo ""
echo "=== VERIFICACIÓN EN VIVO ==="
sleep 4
curl -s "https://inteliaudit.intellihouse.lat/api/health" || echo "Error consultando health check"
echo ""
echo "Deploy finalizado con éxito."
