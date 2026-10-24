import pytest
from sqlalchemy import select
from db.models import (
    Firma, Cliente, Auditoria,
    NormativaLegal, NormativaChunk,
    GrafoNodo, GrafoArista,
    AgenteConversacion, AgenteMensaje
)

@pytest.mark.asyncio
async def test_crear_modelos_agente(db_session, firma, cliente, auditoria):
    # 1. Normativa y chunk
    norm = NormativaLegal(
        tipo="ley",
        numero="6380/2019",
        titulo="De Modernización y Simplificación del Sistema Tributario Nacional",
        organismo="DNIT"
    )
    db_session.add(norm)
    await db_session.flush()

    chunk = NormativaChunk(
        normativa_id=norm.id,
        jerarquia="Título I > Capítulo III > Art. 16",
        articulo="Art. 16",
        texto="No serán deducibles las sanciones por infracciones fiscales.",
        embedding=[0.1] * 768
    )
    db_session.add(chunk)

    # 2. Grafo del cliente
    nodo_cli = GrafoNodo(
        firma_id=firma.id,
        cliente_id=cliente.id,
        auditoria_id=auditoria.id,
        tipo="cliente",
        identificador=cliente.ruc,
        etiqueta=cliente.razon_social
    )
    nodo_prov = GrafoNodo(
        firma_id=firma.id,
        cliente_id=cliente.id,
        auditoria_id=auditoria.id,
        tipo="proveedor",
        identificador="80099887-1",
        etiqueta="PROVEEDOR FANTASMA SA"
    )
    db_session.add_all([nodo_cli, nodo_prov])
    await db_session.flush()

    arista = GrafoArista(
        firma_id=firma.id,
        cliente_id=cliente.id,
        auditoria_id=auditoria.id,
        nodo_origen_id=nodo_prov.id,
        nodo_destino_id=nodo_cli.id,
        relacion="PROVEEDOR_DE",
        metadatos_json={"total_facturado": 150000000}
    )
    db_session.add(arista)

    # 3. Conversación persistente
    conv = AgenteConversacion(
        firma_id=firma.id,
        auditoria_id=auditoria.id,
        titulo="Auditoría IRE Gastos No Deducibles"
    )
    db_session.add(conv)
    await db_session.flush()

    msg = AgenteMensaje(
        conversacion_id=conv.id,
        rol="user",
        contenido="¿Cuáles son los proveedores con RUC inactivo?"
    )
    db_session.add(msg)
    await db_session.commit()

    # Verificación
    res = await db_session.execute(select(NormativaLegal).where(NormativaLegal.id == norm.id))
    assert res.scalar_one().numero == "6380/2019"

    res_arista = await db_session.execute(select(GrafoArista).where(GrafoArista.id == arista.id))
    assert res_arista.scalar_one().relacion == "PROVEEDOR_DE"

    res_msg = await db_session.execute(select(AgenteMensaje).where(AgenteMensaje.id == msg.id))
    assert res_msg.scalar_one().rol == "user"
