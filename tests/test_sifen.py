"""
Tests del parser SIFEN (XML e-Kuatia) y validacion de CDC.
ingesta/sifen.py — RG 69/2020 factura electronica Paraguay.
"""
import pytest
from pathlib import Path

from ingesta.sifen import SifenClient, _validar_cdc, _parsear_xml_de

FIXTURES = Path(__file__).parent / "fixtures"


class TestValidarCDC:

    def test_cdc_valido_44_digitos(self):
        cdc = "12345678901234567890123456789012345678901234"
        assert _validar_cdc(cdc) is True

    def test_cdc_invalido_corto(self):
        assert _validar_cdc("12345") is False

    def test_cdc_invalido_largo(self):
        assert _validar_cdc("1" * 50) is False

    def test_cdc_invalido_letras(self):
        assert _validar_cdc("a" * 44) is False

    def test_cdc_vacio(self):
        assert _validar_cdc("") is False


class TestParsearXML:

    def test_parsear_xml_fixture(self):
        xml_path = FIXTURES / "sifen_de.xml"
        xml_str = xml_path.read_text(encoding="utf-8")
        result = SifenClient.parsear_xml(xml_str)
        assert result["encontrado"] is True

    def test_parsear_xml_cdc(self):
        xml_path = FIXTURES / "sifen_de.xml"
        xml_str = xml_path.read_text(encoding="utf-8")
        result = SifenClient.parsear_xml(xml_str)
        assert result["cdc"] == "12345678901234567890123456789012345678901234"

    def test_parsear_xml_tipo_de(self):
        xml_path = FIXTURES / "sifen_de.xml"
        xml_str = xml_path.read_text(encoding="utf-8")
        result = SifenClient.parsear_xml(xml_str)
        assert result["tipo_de"] == "1"

    def test_parsear_xml_emisor(self):
        xml_path = FIXTURES / "sifen_de.xml"
        xml_str = xml_path.read_text(encoding="utf-8")
        result = SifenClient.parsear_xml(xml_str)
        assert result["ruc_emisor"] == "80055555-1"
        assert result["nombre_emisor"] == "Proveedor Activo SA"

    def test_parsear_xml_receptor(self):
        xml_path = FIXTURES / "sifen_de.xml"
        xml_str = xml_path.read_text(encoding="utf-8")
        result = SifenClient.parsear_xml(xml_str)
        assert result["ruc_receptor"] == "80012345-6"
        assert result["nombre_receptor"] == "Comercial Guarani SA"

    def test_parsear_xml_montos(self):
        xml_path = FIXTURES / "sifen_de.xml"
        xml_str = xml_path.read_text(encoding="utf-8")
        result = SifenClient.parsear_xml(xml_str)
        assert result["base_gravada_10"] == 10000000
        assert result["base_gravada_5"] == 0
        assert result["monto_exento"] == 0
        assert result["iva_total"] == 1000000
        assert result["total_comprobante"] == 11000000

    def test_parsear_xml_timbrado(self):
        xml_path = FIXTURES / "sifen_de.xml"
        xml_str = xml_path.read_text(encoding="utf-8")
        result = SifenClient.parsear_xml(xml_str)
        assert result["timbrado"] == "12345678"
        assert result["establecimiento"] == "001"
        assert result["punto_expedicion"] == "001"
        assert result["nro_comprobante"] == "0000001"

    def test_parsear_xml_fecha(self):
        xml_path = FIXTURES / "sifen_de.xml"
        xml_str = xml_path.read_text(encoding="utf-8")
        result = SifenClient.parsear_xml(xml_str)
        assert result["fecha_emision"] == "2024-03-15T10:30:00"

    def test_parsear_xml_invalido(self):
        result = SifenClient.parsear_xml("esto no es xml <<<>>>")
        assert result["encontrado"] is False
        assert "error" in result

    def test_parsear_xml_vacio(self):
        result = SifenClient.parsear_xml("")
        assert result["encontrado"] is False
