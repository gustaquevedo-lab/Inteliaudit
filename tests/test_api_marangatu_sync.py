import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch
from api.main import app
from api.routers.auth import get_current_user
from db.base import get_db
from db.models import Auditoria, Usuario

@pytest.fixture
def override_auth_and_db(usuario_admin: Usuario, db_session):
    async def _user():
        return usuario_admin
    async def _db():
        yield db_session

    app.dependency_overrides[get_current_user] = _user
    app.dependency_overrides[get_db] = _db
    yield
    app.dependency_overrides.clear()

@pytest.fixture
async def api_client(override_auth_and_db):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_endpoint_validar_cdc(api_client: AsyncClient):
    cdc = "01080012346100100100000011202401151123456780"
    resp = await api_client.get(f"/api/sifen/validar-cdc/{cdc}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cdc"] == cdc
    assert "es_valido" in data
    assert "estado" in data

@pytest.mark.asyncio
async def test_endpoint_marangatu_verificar(api_client: AsyncClient, auditoria: Auditoria):
    with patch("ingesta.marangatu_http.MarangatuHttpClient.verificar_sesion") as mock_ver:
        mock_ver.return_value = {"valido": True, "ruc": "80012345-6", "nombre": "TEST S.A."}
        resp = await api_client.post(
            f"/api/auditorias/{auditoria.id}/marangatu/verificar",
            json={"cookie": "JSESSIONID=dummy123"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["valido"] is True
        assert data["ruc"] == "80012345-6"

@pytest.mark.asyncio
async def test_endpoint_marangatu_sync_payload_directo(api_client: AsyncClient, auditoria: Auditoria):
    payload = [
        {
            "tipo": "compra",
            "tipoComprobante": "109",
            "rucEmisor": "80099999-1",
            "razonSocial": "PROVEEDOR DIRECTO S.A.",
            "timbrado": "12345678",
            "numeroDocumento": "001-001-0001234",
            "fecha": "2024-03-15",
            "gravada10": 1000000.0,
            "iva10": 100000.0,
            "total": 1100000.0,
            "cdc": "01080012346100100100000011202401151123456780"
        }
    ]
    resp = await api_client.post(
        f"/api/auditorias/{auditoria.id}/marangatu/sync",
        json={"periodo": "2024-03", "payload_directo": payload}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["insertados"] == 1
