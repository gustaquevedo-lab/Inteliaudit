import pytest
from analisis.agente_tools import ejecutar_herramienta, ESQUEMA_HERRAMIENTAS
from db.models import RG90

@pytest.mark.asyncio
async def test_ejecutar_herramienta_contingencia(db_session, firma, cliente, auditoria):
    # Probar herramienta de recálculo de contingencia
    res = await ejecutar_herramienta(
        nombre="recalcular_contingencia_fiscal",
        args={"monto": 10000000, "periodo": "2024-01", "reincidente": False},
        db=db_session,
        firma_id=firma.id,
        cliente_id=cliente.id,
        auditoria_id=auditoria.id
    )
    assert res is not None
    assert res["impuesto_omitido"] == 10000000
    assert res["multa_estimada"] == 5000000 # 50%
    assert res["total_contingencia"] > 10000000

@pytest.mark.asyncio
async def test_ejecutar_herramienta_buscar_comprobantes_aislado(db_session, firma, cliente, auditoria):
    # Insertar comprobante de prueba
    compra = RG90(
        firma_id=firma.id,
        cliente_id=cliente.id,
        auditoria_id=auditoria.id,
        periodo="2024-02",
        tipo="compra",
        ruc_contraparte="80022334-5",
        nro_comprobante="001-001-0009999",
        fecha_emision="2024-02-14",
        total_comprobante=12000000
    )
    db_session.add(compra)
    await db_session.flush()

    res = await ejecutar_herramienta(
        nombre="buscar_comprobantes_cliente",
        args={"tipo": "compra", "ruc_contraparte": "80022334-5"},
        db=db_session,
        firma_id=firma.id,
        cliente_id=cliente.id,
        auditoria_id=auditoria.id
    )
    assert isinstance(res, list)
    assert len(res) == 1
    assert res[0]["nro_comprobante"] == "001-001-0009999"

    # Con cliente ajeno no debe traer nada
    res_vacio = await ejecutar_herramienta(
        nombre="buscar_comprobantes_cliente",
        args={"tipo": "compra", "ruc_contraparte": "80022334-5"},
        db=db_session,
        firma_id=firma.id,
        cliente_id="cliente-ajeno-uuid",
        auditoria_id=auditoria.id
    )
    assert len(res_vacio) == 0

def test_esquema_herramientas_valido():
    assert isinstance(ESQUEMA_HERRAMIENTAS, list)
    assert len(ESQUEMA_HERRAMIENTAS) >= 4
    nombres = [t["function"]["name"] for t in ESQUEMA_HERRAMIENTAS]
    assert "consultar_normativa_legal" in nombres
    assert "buscar_comprobantes_cliente" in nombres
    assert "recalcular_contingencia_fiscal" in nombres
