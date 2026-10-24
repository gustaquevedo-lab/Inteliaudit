import pytest
from ingesta.sifen_validator import validar_formato_cdc, calcular_dv_modulo11, TIPOS_DOCUMENTO_SIFEN

def test_calculo_dv_modulo11_oficial():
    # Cadena exacta de 43 dígitos de prueba
    cdc_43 = "0108001234610010010000001120240115112345678"
    assert len(cdc_43) == 43
    dv = calcular_dv_modulo11(cdc_43)
    assert isinstance(dv, int)
    assert 0 <= dv <= 9

def test_cdc_invalido_longitud_o_caracteres():
    res1 = validar_formato_cdc("12345")
    assert res1["valido"] is False
    assert "44 dígitos" in res1["error"]

    # Cadena de 44 caracteres con letras
    res2 = validar_formato_cdc("0108001234610010010000001120240115112345ABCD")
    assert res2["valido"] is False
    assert "numéricos" in res2["error"]

def test_cdc_valido_con_desglose_completo():
    cdc_43 = "0108001234610010010000001120240115112345678"
    assert len(cdc_43) == 43
    dv = calcular_dv_modulo11(cdc_43)
    cdc_44 = cdc_43 + str(dv)
    assert len(cdc_44) == 44

    res = validar_formato_cdc(cdc_44)
    assert res["valido"] is True
    assert res["tipo_documento_codigo"] == "01"
    assert res["tipo_documento_desc"] == "Factura electrónica"
    assert res["ruc_emisor"] == "8001234-6"
    assert res["establecimiento"] == "001"
    assert res["punto_expedicion"] == "001"
    assert res["numero_documento"] == "0000001"
    assert res["comprobante_formato"] == "001-001-0000001"
    assert res["fecha_emision_str"] == "2024-01-15"
    assert res["dv_esperado"] == dv
    assert res["dv_informado"] == dv

def test_cdc_dv_invalido():
    cdc_43 = "0108001234610010010000001120240115112345678"
    dv_real = calcular_dv_modulo11(cdc_43)
    dv_adulterado = (dv_real + 1) % 10
    cdc_adulterado = cdc_43 + str(dv_adulterado)
    assert len(cdc_adulterado) == 44

    res = validar_formato_cdc(cdc_adulterado)
    assert res["valido"] is False
    assert "Dígito verificador inválido" in res["error"]
    assert res["dv_esperado"] == dv_real
    assert res["dv_informado"] == dv_adulterado
