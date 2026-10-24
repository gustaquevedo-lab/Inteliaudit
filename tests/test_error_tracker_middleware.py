import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from api.main import app
from db.models import ErrorPlataforma


from db.base import get_db


@pytest_asyncio.fixture
async def client_app(db_session):
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


@app.get("/api/test-sentry-lite-failure")
async def _endpoint_fallo_test():
    # Fallo intencional para verificar el capturador
    return 1 / 0


@pytest.mark.asyncio
async def test_error_tracker_captura_y_deduplica(client_app: AsyncClient, db_session):
    # 1. Primera invocación: debe responder 500 y registrar el error
    resp1 = await client_app.get("/api/test-sentry-lite-failure")
    assert resp1.status_code == 500
    data1 = resp1.json()
    assert "fingerprint" in data1
    fingerprint = data1["fingerprint"]

    # Verificar en BD
    res1 = await db_session.execute(
        select(ErrorPlataforma).where(ErrorPlataforma.fingerprint == fingerprint)
    )
    err1 = res1.scalar_one_or_none()
    assert err1 is not None
    assert err1.tipo_error == "ZeroDivisionError"
    assert "division by zero" in err1.mensaje.lower() or "integer division" in err1.mensaje.lower()
    assert err1.path == "/api/test-sentry-lite-failure"
    assert err1.ocurrencias == 1

    # 2. Segunda invocación: debe deduplicar e incrementar ocurrencias a 2
    resp2 = await client_app.get("/api/test-sentry-lite-failure")
    assert resp2.status_code == 500
    data2 = resp2.json()
    assert data2["fingerprint"] == fingerprint

    # Refrescar / consultar en BD
    db_session.expire_all()
    res2 = await db_session.execute(
        select(ErrorPlataforma).where(ErrorPlataforma.fingerprint == fingerprint)
    )
    err2 = res2.scalar_one()
    assert err2.ocurrencias == 2
