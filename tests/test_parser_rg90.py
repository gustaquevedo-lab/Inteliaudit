"""
Tests del parser RG90 (XLSX).
ingesta/parser_rg90.py — parseo de archivos descargados de Marangatu.
"""
import pytest
from pathlib import Path

from ingesta.parser_rg90 import (
    parsear_rg90, _detectar_tipo, _limpiar_cdc, _limpiar_ruc,
    _normalizar_fecha, _int_pyg, _fila_vacia,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestHelpersParser:

    def test_detectar_tipo_compras(self):
        assert _detectar_tipo("Compras") == "compra"
        assert _detectar_tipo("COMPRAS") == "compra"
        assert _detectar_tipo("Mis Compras 2024") == "compra"

    def test_detectar_tipo_ventas(self):
        assert _detectar_tipo("Ventas") == "venta"
        assert _detectar_tipo("VENTAS") == "venta"

    def test_detectar_tipo_desconocido(self):
        assert _detectar_tipo("Resumen") is None
        assert _detectar_tipo("Totales") is None

    def test_limpiar_ruc_valido(self):
        assert _limpiar_ruc("80012345-6") == "80012345-6"
        assert _limpiar_ruc(" 80012345-6 ") == "80012345-6"

    def test_limpiar_ruc_vacio(self):
        assert _limpiar_ruc(None) is None
        assert _limpiar_ruc("") is None
        assert _limpiar_ruc("   ") is None

    def test_limpiar_cdc_valido(self):
        cdc = "12345678901234567890123456789012345678901234"
        assert _limpiar_cdc(cdc) == cdc

    def test_limpiar_cdc_invalido(self):
        assert _limpiar_cdc("12345") is None
        assert _limpiar_cdc("a" * 44) is None
        assert _limpiar_cdc(None) is None
        assert _limpiar_cdc("") is None

    def test_normalizar_fecha_iso(self):
        assert _normalizar_fecha("2024-03-15") == "2024-03-15"

    def test_normalizar_fecha_ddmmyyyy(self):
        assert _normalizar_fecha("15/03/2024") == "2024-03-15"

    def test_normalizar_fecha_datetime(self):
        from datetime import datetime
        dt = datetime(2024, 3, 15)
        assert _normalizar_fecha(dt) == "2024-03-15"

    def test_normalizar_fecha_vacio(self):
        assert _normalizar_fecha(None) is None
        assert _normalizar_fecha("") is None

    def test_int_pyg_valido(self):
        assert _int_pyg(1000000) == 1000000
        assert _int_pyg("1000000") == 1000000
        assert _int_pyg(0) == 0

    def test_int_pyg_cero(self):
        assert _int_pyg(None) == 0
        assert _int_pyg(0) == 0
        assert _int_pyg("") == 0

    def test_fila_vacia(self):
        assert _fila_vacia((None, None, None)) is True
        assert _fila_vacia(("", "", "")) is True
        assert _fila_vacia((None, "dato", None)) is False


class TestParsearRG90Compras:

    def test_parsear_compras_fixture(self):
        path = FIXTURES / "rg90_compras.xlsx"
        registros = parsear_rg90(path, "test-cliente-id", "2024-03")
        assert len(registros) == 3

    def test_compras_tipo(self):
        path = FIXTURES / "rg90_compras.xlsx"
        registros = parsear_rg90(path, "test-cliente-id", "2024-03")
        for r in registros:
            assert r["tipo"] == "compra"

    def test_compras_periodo(self):
        path = FIXTURES / "rg90_compras.xlsx"
        registros = parsear_rg90(path, "test-cliente-id", "2024-03")
        for r in registros:
            assert r["periodo"] == "2024-03"

    def test_compras_ruc(self):
        path = FIXTURES / "rg90_compras.xlsx"
        registros = parsear_rg90(path, "test-cliente-id", "2024-03")
        rucs = [r["ruc_contraparte"] for r in registros]
        assert "80055555-1" in rucs
        assert "80066666-2" in rucs
        assert "80077777-3" in rucs

    def test_compras_montos(self):
        path = FIXTURES / "rg90_compras.xlsx"
        registros = parsear_rg90(path, "test-cliente-id", "2024-03")
        primero = registros[0]
        assert primero["base_gravada_10"] == 10000000
        assert primero["iva_10"] == 1000000
        assert primero["iva_total"] == 1000000
        assert primero["total_comprobante"] == 11000000

    def test_compras_cdc_valido(self):
        path = FIXTURES / "rg90_compras.xlsx"
        registros = parsear_rg90(path, "test-cliente-id", "2024-03")
        assert registros[0]["cdc"] == "12345678901234567890123456789012345678901234"

    def test_compras_sin_cdc(self):
        path = FIXTURES / "rg90_compras.xlsx"
        registros = parsear_rg90(path, "test-cliente-id", "2024-03")
        assert registros[2]["cdc"] is None


class TestParsearRG90Ventas:

    def test_parsear_ventas_fixture(self):
        path = FIXTURES / "rg90_ventas.xlsx"
        registros = parsear_rg90(path, "test-cliente-id", "2024-03")
        assert len(registros) == 2

    def test_ventas_tipo(self):
        path = FIXTURES / "rg90_ventas.xlsx"
        registros = parsear_rg90(path, "test-cliente-id", "2024-03")
        for r in registros:
            assert r["tipo"] == "venta"

    def test_ventas_montos(self):
        path = FIXTURES / "rg90_ventas.xlsx"
        registros = parsear_rg90(path, "test-cliente-id", "2024-03")
        assert registros[0]["base_gravada_10"] == 20000000
        assert registros[0]["iva_total"] == 2000000
        assert registros[1]["base_gravada_10"] == 15000000
        assert registros[1]["iva_total"] == 1500000
