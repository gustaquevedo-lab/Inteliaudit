import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from jose import jwt
from sqlalchemy import select

from api.main import app
from api.routers.auth import get_current_user, _hash
from config.settings import settings
from db.base import get_db
from db.models import Firma, Usuario, ErrorPlataforma, SifenCache


@pytest_asyncio.fixture
async def superadmin_user(db_session, firma: Firma) -> Usuario:
    u = Usuario(
        firma_id=firma.id,
        email=f"superadmin_{uuid.uuid4().hex[:8]}@inteliaudit.com",
        nombre="Super Admin Test",
        password_hash=_hash("supersecret123"),
        rol="super_admin",
        activo=True,
    )
    db_session.add(u)
    await db_session.flush()
    return u


@pytest_asyncio.fixture
async def client_superadmin(db_session, superadmin_user: Usuario):
    async def _override_get_db():
        yield db_session

    async def _override_user():
        return superadmin_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_superadmin_impersonate(client_superadmin: AsyncClient, db_session, firma: Firma):
    # Crear un usuario en la firma para impersonar
    tenant_admin = Usuario(
        firma_id=firma.id,
        email=f"admin_{uuid.uuid4().hex[:6]}@cliente.com",
        nombre="Cliente Admin",
        password_hash=_hash("secret"),
        rol="admin",
        activo=True,
    )
    db_session.add(tenant_admin)
    await db_session.commit()

    resp = await client_superadmin.post(f"/api/superadmin/firmas/{firma.id}/impersonate")
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data
    assert data["user"]["email"] == tenant_admin.email

    payload = jwt.decode(data["token"], settings.secret_key, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] in (tenant_admin.id, tenant_admin.email)
    assert payload["firma_id"] == firma.id
    assert "impersonated_by" in payload


@pytest.mark.asyncio
async def test_superadmin_stats(client_superadmin: AsyncClient):
    resp = await client_superadmin.get("/api/superadmin/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_firmas" in data
    assert "total_usuarios" in data
    assert "total_errores_pendientes" in data
    assert "distribucion_planes" in data


@pytest.mark.asyncio
async def test_superadmin_errores_y_resolver(client_superadmin: AsyncClient, db_session, firma: Firma):
    fp = f"fp_{uuid.uuid4().hex}"
    err = ErrorPlataforma(
        fingerprint=fp,
        tipo_error="KeyError",
        mensaje="'clave_inexistente'",
        path="/api/test",
        metodo="GET",
        status_code=500,
        stacktrace="Traceback ...",
        firma_id=firma.id,
        usuario_email="alguien@test.com",
        ocurrencias=3,
        resuelto=False,
    )
    db_session.add(err)
    await db_session.commit()

    # 1. Listar errores
    resp = await client_superadmin.get("/api/superadmin/errores")
    assert resp.status_code == 200
    items = resp.json()
    assert any(i["fingerprint"] == fp for i in items)

    # 2. Resolver error
    resp_res = await client_superadmin.post(
        f"/api/superadmin/errores/{err.id}/resolver",
        json={"notas_resolucion": "Corregido con fallback get()"},
    )
    assert resp_res.status_code == 200
    res_data = resp_res.json()
    assert res_data["resuelto"] is True
    assert res_data["notas_resolucion"] == "Corregido con fallback get()"


@pytest.mark.asyncio
async def test_superadmin_vitals(client_superadmin: AsyncClient):
    resp = await client_superadmin.get("/api/superadmin/vitals")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert data["database"]["status"] == "ok"
    assert "sifen_cache" in data
    assert "ollama_ai" in data
