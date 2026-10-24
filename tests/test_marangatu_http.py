import pytest
from unittest.mock import patch, MagicMock
from ingesta.marangatu_http import MarangatuHttpClient, parsear_registros_marangatu

@pytest.mark.asyncio
async def test_marangatu_verificar_sesion_activa():
    client = MarangatuHttpClient()
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "autenticado": True,
            "ruc": "80012345",
            "dv": "6",
            "razonSocial": "CONTRIBUYENTE MODELO S.A."
        }
        mock_get.return_value = mock_resp

        res = await client.verificar_sesion("JSESSIONID=valid_session_token_123")
        assert res["valido"] is True
        assert res["ruc"] == "80012345-6"
        assert "CONTRIBUYENTE MODELO" in res["nombre"]

@pytest.mark.asyncio
async def test_marangatu_verificar_sesion_expirada():
    client = MarangatuHttpClient()
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_get.return_value = mock_resp

        res = await client.verificar_sesion("JSESSIONID=expired_token")
        assert res["valido"] is False
        assert "expirada" in res["error"].lower() or "inválida" in res["error"].lower()

@pytest.mark.asyncio
async def test_marangatu_listar_talones_rg90():
    client = MarangatuHttpClient()
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "talones": [
                {
                    "id": "TALON-987654",
                    "tipo": "compras",
                    "periodo": "2024-03",
                    "cantidadComprobantes": 45,
                    "fecha": "2024-04-05"
                }
            ]
        }
        mock_get.return_value = mock_resp

        talones = await client.listar_talones_rg90("JSESSIONID=abc", "80012345-6", "2024-03")
        assert len(talones) == 1
        assert talones[0]["id"] == "TALON-987654"
        assert talones[0]["tipo"] == "compras"

def test_parsear_registros_marangatu_json():
    payload_dnit = [
        {
            "tipo": "compra",
            "tipoComprobante": "109",
            "rucEmisor": "80098765-4",
            "razonSocial": "PROVEEDOR S.A.",
            "timbrado": "12345678",
            "establecimiento": "001",
            "puntoExpedicion": "001",
            "numeroDocumento": "0012345",
            "fecha": "2024-03-10",
            "gravada10": 1000000.0,
            "iva10": 100000.0,
            "gravada5": 0.0,
            "iva5": 0.0,
            "exenta": 0.0,
            "total": 1100000.0,
            "cdc": "010800987654100100100012345120240310112345678"
        }
    ]
    registros = parsear_registros_marangatu(payload_dnit)
    assert len(registros) == 1
    reg = registros[0]
    assert reg["tipo"] == "compra"
    assert reg["ruc_contraparte"] == "80098765-4"
    assert reg["total_comprobante"] == 1100000.0
    assert reg["iva_10"] == 100000.0
    assert reg["timbrado"] == "12345678"
