#!/bin/bash
set -e

echo "=== INTELIAUDIT STARTUP ==="
echo "Python: $(python --version)"
echo "PORT: ${PORT:-8000}"
echo "DATABASE_URL set: $([ -n "$DATABASE_URL" ] && echo 'YES' || echo 'NO')"

echo ""
echo "=== TESTING IMPORTS ==="
python -u -c "
import sys
print('Python path:', sys.path[:3])

try:
    import fastapi
    print('fastapi OK')
except Exception as e:
    print('fastapi FAILED:', e)

try:
    import sqlalchemy
    print('sqlalchemy OK')
except Exception as e:
    print('sqlalchemy FAILED:', e)

try:
    import asyncpg
    print('asyncpg OK')
except Exception as e:
    print('asyncpg FAILED:', e)

try:
    from config.settings import settings
    print('settings OK, db:', settings.database_url[:20], '...')
except Exception as e:
    print('settings FAILED:', e)

try:
    from db.base import engine
    print('db.base OK')
except Exception as e:
    print('db.base FAILED:', e)

try:
    from api.routers.auth import router
    print('auth router OK')
except Exception as e:
    print('auth router FAILED:', e)

try:
    from api.routers.superadmin import router
    print('superadmin router OK')
except Exception as e:
    print('superadmin router FAILED:', e)

try:
    from api.main import app
    print('api.main OK')
except Exception as e:
    import traceback
    print('api.main FAILED:', e)
    traceback.print_exc()
" 2>&1

echo ""
echo "=== RUNNING ALEMBIC ==="
alembic upgrade head 2>&1

echo ""
echo "=== STARTING UVICORN on port ${PORT:-8000} ==="
exec python -u -m uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --log-level info \
    --no-access-log 2>&1
