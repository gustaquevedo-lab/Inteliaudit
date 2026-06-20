"""
Tests de la API REST — routers principales.
Usa httpx AsyncClient con la app FastAPI de test.
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from api.main import app


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestAuth:
    @pytest.mark.asyncio
    async def test_login_requiere_usuario(self, client: AsyncClient):
        resp = await client.post("/api/auth/token", json={
            "username": "nonexistent@test.com",
            "password": "wrongpassword",
        })
        # Should return 401 or similar
        assert resp.status_code in (401, 422)


class TestClientes:
    @pytest.mark.asyncio
    async def test_listar_clientes_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/clientes")
        assert resp.status_code in (401, 403)


class TestAuditorias:
    @pytest.mark.asyncio
    async def test_listar_auditorias_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/auditorias")
        assert resp.status_code in (401, 403)
