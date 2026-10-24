import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from api.main import app
from api.routers.auth import get_current_user, _hash
from db.base import get_db
from db.models import Firma, Usuario


import uuid


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
async def test_creacion_atomica_firma_y_admin(client_superadmin: AsyncClient, db_session):
    sfx = uuid.uuid4().hex[:6]
    payload = {
        "nombre": f"Estudio Contable {sfx} SRL",
        "ruc": f"800{sfx[:5]}-9",
        "email": f"contacto_{sfx}@guarani.com.py",
        "plan": "starter",
        "admin_email": f"admin_{sfx}@guarani.com.py",
        "admin_nombre": "Lic. Carlos Benítez",
        "features_override_json": '{"tiene_ia": true}',
    }
    resp = await client_superadmin.post("/api/superadmin/firmas", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert "firma" in data
    assert "admin_usuario" in data
    assert "password_temporal" in data
    assert len(data["password_temporal"]) >= 8

    firma_id = data["firma"]["id"]
    admin_id = data["admin_usuario"]["id"]

    # Verificar en BD
    firma_db = (await db_session.execute(select(Firma).where(Firma.id == firma_id))).scalar_one()
    assert firma_db.nombre == f"Estudio Contable {sfx} SRL"
    assert firma_db.features_override_json == '{"tiene_ia": true}'

    user_db = (await db_session.execute(select(Usuario).where(Usuario.id == admin_id))).scalar_one()
    assert user_db.email == f"admin_{sfx}@guarani.com.py"
    assert user_db.rol == "admin"
    assert user_db.debe_cambiar_password is True


@pytest.mark.asyncio
async def test_creacion_usuario_en_tenant(client_superadmin: AsyncClient, db_session, firma: Firma):
    sfx = uuid.uuid4().hex[:6]
    payload = {
        "firma_id": firma.id,
        "email": f"auditor_{sfx}@estudio.com.py",
        "nombre": "Ana Gómez",
        "rol": "auditor_senior",
    }
    resp = await client_superadmin.post("/api/superadmin/usuarios", json=payload)
    assert resp.status_code == 201
    data = resp.json()

    assert "usuario" in data
    assert "password_temporal" in data
    user_data = data["usuario"]
    assert user_data["email"] == f"auditor_{sfx}@estudio.com.py"
    assert user_data["rol"] == "auditor_senior"

    # Verificar en BD
    user_db = (await db_session.execute(select(Usuario).where(Usuario.id == user_data["id"]))).scalar_one()
    assert user_db.debe_cambiar_password is True
