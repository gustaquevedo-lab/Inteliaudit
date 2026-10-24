import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from api.main import app
from api.routers.auth import get_current_user, get_current_admin, _hash
from db.base import get_db
from db.models import Firma, Usuario, Cliente


@pytest_asyncio.fixture
async def firma_starter(db_session) -> Firma:
    f = Firma(
        nombre="Firma Plan Starter",
        ruc=f"800{uuid.uuid4().hex[:5]}-1",
        email=f"contacto_{uuid.uuid4().hex[:6]}@starter.com.py",
        plan="starter",
        activa=True,
    )
    db_session.add(f)
    await db_session.flush()
    return f


@pytest_asyncio.fixture
async def admin_starter(db_session, firma_starter: Firma) -> Usuario:
    u = Usuario(
        firma_id=firma_starter.id,
        email=f"admin_{uuid.uuid4().hex[:6]}@starter.com.py",
        nombre="Admin Starter",
        password_hash=_hash("secret123"),
        rol="admin",
        activo=True,
        debe_cambiar_password=True,
    )
    db_session.add(u)
    await db_session.flush()
    return u


@pytest_asyncio.fixture
async def client_starter_admin(db_session, admin_starter: Usuario):
    admin_id = admin_starter.id

    async def _override_get_db():
        yield db_session

    async def _override_user():
        res = await db_session.execute(select(Usuario).where(Usuario.id == admin_id))
        return res.scalar_one()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_current_admin] = _override_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_admin, None)


@pytest.mark.asyncio
async def test_limite_usuarios_en_auth_crear_usuario(client_starter_admin: AsyncClient, db_session, firma_starter: Firma, admin_starter: Usuario):
    # Plan starter permite 3 usuarios máximo. admin_starter es el 1º.
    # Creamos el 2º y 3º:
    u2 = Usuario(
        firma_id=firma_starter.id,
        email=f"u2_{uuid.uuid4().hex[:6]}@starter.com.py",
        nombre="Auditor 2",
        password_hash=_hash("secret"),
        rol="auditor",
        activo=True,
    )
    u3 = Usuario(
        firma_id=firma_starter.id,
        email=f"u3_{uuid.uuid4().hex[:6]}@starter.com.py",
        nombre="Auditor 3",
        password_hash=_hash("secret"),
        rol="auditor",
        activo=True,
    )
    db_session.add_all([u2, u3])
    await db_session.commit()

    # Intentar crear el 4º usuario debe ser rechazado con 403
    payload = {
        "email": f"u4_{uuid.uuid4().hex[:6]}@starter.com.py",
        "nombre": "Auditor Excedente",
        "password": "password123",
        "rol": "auditor",
    }
    resp = await client_starter_admin.post("/api/auth/usuarios", json=payload)
    assert resp.status_code == 403
    assert "límite de usuarios" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_override_features_permite_mas_usuarios(client_starter_admin: AsyncClient, db_session, firma_starter: Firma):
    # Asignar override a 10 usuarios para esta firma
    firma_starter.features_override_json = '{"max_usuarios": 10}'
    await db_session.commit()

    payload = {
        "email": f"u_permitido_{uuid.uuid4().hex[:6]}@starter.com.py",
        "nombre": "Auditor Permitido Por Override",
        "password": "password123",
        "rol": "auditor",
    }
    resp = await client_starter_admin.post("/api/auth/usuarios", json=payload)
    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_cambio_password_primer_login(client_starter_admin: AsyncClient, db_session, admin_starter: Usuario):
    assert admin_starter.debe_cambiar_password is True
    admin_id = admin_starter.id

    payload = {
        "password_actual": "secret123",
        "password_nueva": "NuevaPassSuperSegura99!",
    }
    resp = await client_starter_admin.post("/api/auth/cambiar-password", json=payload)
    assert resp.status_code == 200

    db_session.expire_all()
    u_db = (await db_session.execute(select(Usuario).where(Usuario.id == admin_id))).scalar_one()
    assert u_db.debe_cambiar_password is False
