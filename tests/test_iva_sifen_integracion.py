import pytest
from db.models import RG90, SifenCache, Auditoria
from analisis.iva import auditar_credito_fiscal_sifen


@pytest.mark.asyncio
async def test_impugnacion_factura_sifen_rechazada(db_session, auditoria: Auditoria):
    # Comprobante electrónico con CDC inválido o rechazado en SIFEN
    comp = RG90(
        firma_id=auditoria.firma_id,
        cliente_id=auditoria.cliente_id,
        auditoria_id=auditoria.id,
        periodo="2024-01",
        tipo="compra",
        tipo_comprobante="109",  # Factura electrónica
        ruc_contraparte="80098765-4",
        nro_comprobante="001-001-0000045",
        fecha_emision="2024-01-15",
        cdc="01800123456001001000000122024010112345678901",
        total_comprobante=5500000,
        base_gravada_10=5000000,
        iva_10=500000,
        iva_total=500000,
    )
    db_session.add(comp)

    # Marcar en SifenCache como NO_EXISTE / no válido
    db_session.add(SifenCache(
        cdc=comp.cdc,
        estado_sifen="NO_EXISTE",
        es_valido=False,
    ))
    await db_session.commit()

    hallazgos = await auditar_credito_fiscal_sifen(db_session, auditoria.id)
    assert len(hallazgos) >= 1
    assert any("Art. 85" in h.articulo_legal for h in hallazgos)
    assert any(h.impuesto_omitido == 500000 for h in hallazgos)
    assert any(h.tipo_hallazgo == "IVA_CF_SIFEN_NO_REGISTRADO" for h in hallazgos)


@pytest.mark.asyncio
async def test_factura_sifen_aprobada_no_genera_hallazgo(db_session, auditoria: Auditoria):
    comp = RG90(
        firma_id=auditoria.firma_id,
        cliente_id=auditoria.cliente_id,
        auditoria_id=auditoria.id,
        periodo="2024-02",
        tipo="compra",
        tipo_comprobante="109",
        ruc_contraparte="80098765-4",
        nro_comprobante="001-001-0000099",
        fecha_emision="2024-02-10",
        cdc="01080012346100100100000011202401151123456784",
        total_comprobante=11000000,
        base_gravada_10=10000000,
        iva_10=1000000,
        iva_total=1000000,
    )
    db_session.add(comp)

    db_session.add(SifenCache(
        cdc=comp.cdc,
        estado_sifen="APROBADO",
        es_valido=True,
    ))
    await db_session.commit()

    hallazgos = await auditar_credito_fiscal_sifen(db_session, auditoria.id)
    # The valid CDC should not generate IVA_CF_SIFEN_NO_REGISTRADO
    sifen_hallazgos = [h for h in hallazgos if h.tipo_hallazgo == "IVA_CF_SIFEN_NO_REGISTRADO"]
    assert len(sifen_hallazgos) == 0
