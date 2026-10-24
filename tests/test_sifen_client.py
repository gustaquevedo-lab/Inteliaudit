import pytest
from unittest.mock import patch, MagicMock
from db.models import SifenCache
from ingesta.sifen_client import consultar_o_validar_cdc, verificar_lote_cdcs
from ingesta.sifen_validator import calcular_dv_modulo11

@pytest.mark.asyncio
async def test_consultar_cdc_con_cache_existente(db_session):
    cdc = "01080012346100100100000011202401151123456789"
    db_session.add(SifenCache(
        cdc=cdc,
        estado_sifen="APROBADO",
        ruc_emisor="8001234-6",
        es_valido=True,
        total_comprobante=2500000.0
    ))
    await db_session.commit()

    resultado = await consultar_o_validar_cdc(db_session, cdc)
    assert resultado["en_cache"] is True
    assert resultado["estado"] == "APROBADO"
    assert resultado["es_valido"] is True
    assert resultado["total_comprobante"] == 2500000.0

@pytest.mark.asyncio
async def test_consultar_cdc_invalido_guarda_en_cache(db_session):
    cdc_invalido = "123456"
    resultado = await consultar_o_validar_cdc(db_session, cdc_invalido)
    assert resultado["es_valido"] is False
    assert resultado["estado"] == "CDC_INVALIDO"

    # Verificar que se guardó en cache
    cache = await db_session.get(SifenCache, cdc_invalido)
    assert cache is not None
    assert cache.es_valido is False
    assert cache.estado_sifen == "CDC_INVALIDO"

@pytest.mark.asyncio
async def test_consultar_cdc_valido_sin_cache(db_session):
    cdc_43 = "0108001234610010010000001120240115112345678"
    dv = calcular_dv_modulo11(cdc_43)
    cdc_44 = cdc_43 + str(dv)

    resultado = await consultar_o_validar_cdc(db_session, cdc_44)
    assert resultado["es_valido"] is True
    assert resultado["estado"] in ("FORMATO_VALIDO", "APROBADO")
    assert resultado["ruc_emisor"] == "8001234-6"

    # Verificar persistencia en base de datos
    cache = await db_session.get(SifenCache, cdc_44)
    assert cache is not None
    assert cache.es_valido is True

@pytest.mark.asyncio
async def test_verificar_lote_cdcs(db_session):
    cdc_43 = "0108001234610010010000001120240115112345999"
    dv = calcular_dv_modulo11(cdc_43)
    cdc_valido = cdc_43 + str(dv)
    cdcs = [cdc_valido, "9999999"]

    lote = await verificar_lote_cdcs(db_session, cdcs)
    assert len(lote) == 2
    assert lote[cdc_valido]["es_valido"] is True
    assert lote["9999999"]["es_valido"] is False
