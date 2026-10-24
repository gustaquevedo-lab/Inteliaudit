import pytest
from sqlalchemy import select
from db.models import SifenCache

@pytest.mark.asyncio
async def test_modelo_sifen_cache_creacion(db_session):
    cache = SifenCache(
        cdc="01800123456001001000000122024010112345678901",
        estado_sifen="APROBADO",
        ruc_emisor="80012345-6",
        razon_social="PROVEEDOR MODELO S.A.",
        timbrado="12345678",
        total_comprobante=1100000.0,
        iva_10=100000.0,
        iva_5=0.0,
        es_valido=True,
        respuesta_raw={"estado": "Aprobado", "codigo": "01"}
    )
    db_session.add(cache)
    await db_session.commit()

    stmt = select(SifenCache).where(SifenCache.cdc == cache.cdc)
    recuperado = (await db_session.execute(stmt)).scalar_one()
    assert recuperado.cdc == cache.cdc
    assert recuperado.estado_sifen == "APROBADO"
    assert recuperado.es_valido is True
    assert recuperado.total_comprobante == 1100000.0
