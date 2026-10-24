import pytest
from sqlalchemy import select
from analisis.grafo_service import construir_grafo_auditoria, consultar_entidad_grafo
from db.models import RG90, Hallazgo, GrafoNodo, GrafoArista

@pytest.mark.asyncio
async def test_construir_y_consultar_grafo_aislado(db_session, firma, cliente, auditoria):
    # Insertar comprobantes RG90 para el cliente
    compra1 = RG90(
        firma_id=firma.id,
        cliente_id=cliente.id,
        auditoria_id=auditoria.id,
        periodo="2024-03",
        tipo="compra",
        ruc_contraparte="80011223-4",
        nro_comprobante="001-001-0001234",
        fecha_emision="2024-03-10",
        total_comprobante=50000000,
        iva_total=4545455
    )
    compra2 = RG90(
        firma_id=firma.id,
        cliente_id=cliente.id,
        auditoria_id=auditoria.id,
        periodo="2024-03",
        tipo="compra",
        ruc_contraparte="80011223-4",
        nro_comprobante="001-001-0001235",
        fecha_emision="2024-03-15",
        total_comprobante=25000000,
        iva_total=2272727
    )
    db_session.add_all([compra1, compra2])

    # Insertar hallazgo relacionado
    hallazgo = Hallazgo(
        auditoria_id=auditoria.id,
        firma_id=firma.id,
        periodo="2024-03",
        impuesto="IVA",
        tipo_hallazgo="proveedor_inactivo",
        articulo_legal="Art. 85 Ley 6380/2019",
        descripcion="Proveedor con RUC cancelado en DNIT",
        base_ajuste=75000000,
        total_contingencia=112500000,
        nivel_riesgo="alto"
    )
    db_session.add(hallazgo)
    await db_session.flush()

    # Construir grafo
    stats = await construir_grafo_auditoria(db_session, firma.id, cliente.id, auditoria.id)
    assert stats["nodos"] >= 2
    assert stats["aristas"] >= 1

    # Consultar entidad proveedor en scope
    prov_info = await consultar_entidad_grafo(
        db_session,
        firma.id,
        cliente.id,
        auditoria.id,
        identificador="80011223-4"
    )
    assert prov_info is not None
    assert prov_info["identificador"] == "80011223-4"
    assert prov_info["tipo"] == "proveedor"
    assert prov_info["total_facturado"] == 75000000
    assert prov_info["cantidad_comprobantes"] == 2

    # Intentar consultar con otro cliente_id (Aislamiento) -> No debe retornar nada
    prov_otro_cliente = await consultar_entidad_grafo(
        db_session,
        firma.id,
        cliente_id="cliente-ajeno-id",
        auditoria_id=auditoria.id,
        identificador="80011223-4"
    )
    assert prov_otro_cliente is None
