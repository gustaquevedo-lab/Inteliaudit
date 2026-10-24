"""
Servicio de Grafo de Conocimiento Contable-Forense por Cliente.
Modelado relacional de nodos y aristas en PostgreSQL con aislamiento estricto
por (firma_id, cliente_id, auditoria_id).
"""
import json
from typing import Optional, Dict, Any, List
from sqlalchemy import select, func, and_, or_, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Cliente, Auditoria, RG90, SifenComprobante, Hallazgo, GrafoNodo, GrafoArista


async def construir_grafo_auditoria(
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    auditoria_id: str
) -> dict:
    """
    Construye o actualiza el subgrafo relacional de la auditoría a partir de los
    comprobantes RG90, SIFEN y hallazgos registrados para el cliente.
    """
    # 1. Obtener cliente asegurando pertenencia a la firma
    res_cli = await db.execute(
        select(Cliente).where(Cliente.id == cliente_id, Cliente.firma_id == firma_id)
    )
    cliente = res_cli.scalar_one_or_none()
    if not cliente:
        return {"nodos": 0, "aristas": 0, "error": "Cliente no encontrado en la firma"}

    # 2. Limpiar grafo anterior de esta auditoría para reconstrucción determinista
    await db.execute(
        delete(GrafoArista).where(
            GrafoArista.firma_id == firma_id,
            GrafoArista.cliente_id == cliente_id,
            GrafoArista.auditoria_id == auditoria_id
        )
    )
    await db.execute(
        delete(GrafoNodo).where(
            GrafoNodo.firma_id == firma_id,
            GrafoNodo.cliente_id == cliente_id,
            GrafoNodo.auditoria_id == auditoria_id
        )
    )

    # 3. Crear nodo raíz del Cliente
    nodo_cliente = GrafoNodo(
        firma_id=firma_id,
        cliente_id=cliente_id,
        auditoria_id=auditoria_id,
        tipo="cliente",
        identificador=cliente.ruc,
        etiqueta=cliente.razon_social,
        atributos_json={
            "regimen": cliente.regimen,
            "estado_dnit": cliente.estado_dnit
        }
    )
    db.add(nodo_cliente)
    await db.flush()

    total_nodos = 1
    total_aristas = 0

    # 4. Procesar Proveedores desde RG90 compras
    stmt_provs = (
        select(
            RG90.ruc_contraparte,
            func.coalesce(func.sum(RG90.total_comprobante), 0).label("total_facturado"),
            func.count(RG90.id).label("cantidad_comprobantes")
        )
        .where(
            RG90.firma_id == firma_id,
            RG90.cliente_id == cliente_id,
            RG90.tipo == "compra"
        )
        .group_by(RG90.ruc_contraparte)
    )
    res_provs = await db.execute(stmt_provs)
    prov_rows = res_provs.all()

    for ruc_prov, total_fact, cant in prov_rows:
        if not ruc_prov:
            continue
        nodo_prov = GrafoNodo(
            firma_id=firma_id,
            cliente_id=cliente_id,
            auditoria_id=auditoria_id,
            tipo="proveedor",
            identificador=ruc_prov,
            etiqueta=f"Proveedor {ruc_prov}",
            atributos_json={
                "total_facturado": int(total_fact),
                "cantidad_comprobantes": int(cant)
            }
        )
        db.add(nodo_prov)
        await db.flush()
        total_nodos += 1

        # Arista Proveedor -> Cliente
        arista = GrafoArista(
            firma_id=firma_id,
            cliente_id=cliente_id,
            auditoria_id=auditoria_id,
            nodo_origen_id=nodo_prov.id,
            nodo_destino_id=nodo_cliente.id,
            relacion="PROVEEDOR_DE",
            peso=float(total_fact) / 1_000_000.0,
            metadatos_json={
                "total_facturado": int(total_fact),
                "cantidad_comprobantes": int(cant)
            }
        )
        db.add(arista)
        total_aristas += 1

    # 5. Procesar Hallazgos de la auditoría
    res_hal = await db.execute(
        select(Hallazgo).where(
            Hallazgo.auditoria_id == auditoria_id,
            Hallazgo.firma_id == firma_id
        )
    )
    hallazgos = res_hal.scalars().all()
    for h in hallazgos:
        nodo_hal = GrafoNodo(
            firma_id=firma_id,
            cliente_id=cliente_id,
            auditoria_id=auditoria_id,
            tipo="hallazgo",
            identificador=f"HAL-{h.id[:8]}",
            etiqueta=h.descripcion[:60] if h.descripcion else "Hallazgo fiscal",
            atributos_json={
                "impuesto": h.impuesto,
                "nivel_riesgo": h.nivel_riesgo,
                "contingencia": h.total_contingencia or 0
            }
        )
        db.add(nodo_hal)
        await db.flush()
        total_nodos += 1

        arista_hal = GrafoArista(
            firma_id=firma_id,
            cliente_id=cliente_id,
            auditoria_id=auditoria_id,
            nodo_origen_id=nodo_hal.id,
            nodo_destino_id=nodo_cliente.id,
            relacion="INCONSISTENCIA_DE",
            peso=1.0,
            metadatos_json={
                "nivel_riesgo": h.nivel_riesgo,
                "base_ajuste": h.base_ajuste or 0
            }
        )
        db.add(arista_hal)
        total_aristas += 1

    await db.commit()
    return {"nodos": total_nodos, "aristas": total_aristas}


async def consultar_entidad_grafo(
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    auditoria_id: str,
    identificador: str
) -> Optional[dict]:
    """
    Recupera un nodo y sus relaciones asegurando el perímetro de firma y cliente.
    """
    stmt = (
        select(GrafoNodo)
        .where(
            GrafoNodo.firma_id == firma_id,
            GrafoNodo.cliente_id == cliente_id,
            GrafoNodo.auditoria_id == auditoria_id,
            GrafoNodo.identificador == identificador
        )
    )
    res = await db.execute(stmt)
    nodo = res.scalar_one_or_none()
    if not nodo:
        return None

    # Obtener aristas conectadas
    stmt_aristas = (
        select(GrafoArista)
        .where(
            GrafoArista.firma_id == firma_id,
            GrafoArista.cliente_id == cliente_id,
            GrafoArista.auditoria_id == auditoria_id,
            or_(
                GrafoArista.nodo_origen_id == nodo.id,
                GrafoArista.nodo_destino_id == nodo.id
            )
        )
    )
    res_aristas = await db.execute(stmt_aristas)
    aristas = res_aristas.scalars().all()

    info = {
        "id": nodo.id,
        "tipo": nodo.tipo,
        "identificador": nodo.identificador,
        "etiqueta": nodo.etiqueta,
        "atributos": nodo.atributos_json or {},
        "relaciones": [
            {
                "relacion": a.relacion,
                "origen": a.nodo_origen_id,
                "destino": a.nodo_destino_id,
                "metadatos": a.metadatos_json
            }
            for a in aristas
        ]
    }
    # Exponer conveniencias directas
    if nodo.atributos_json:
        if "total_facturado" in nodo.atributos_json:
            info["total_facturado"] = nodo.atributos_json["total_facturado"]
        if "cantidad_comprobantes" in nodo.atributos_json:
            info["cantidad_comprobantes"] = nodo.atributos_json["cantidad_comprobantes"]

    return info


async def consultar_subgrafo_completo(
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    auditoria_id: str
) -> dict:
    """Retorna todos los nodos y aristas para el cliente en alcance."""
    res_n = await db.execute(
        select(GrafoNodo).where(
            GrafoNodo.firma_id == firma_id,
            GrafoNodo.cliente_id == cliente_id,
            GrafoNodo.auditoria_id == auditoria_id
        )
    )
    nodos = res_n.scalars().all()

    res_a = await db.execute(
        select(GrafoArista).where(
            GrafoArista.firma_id == firma_id,
            GrafoArista.cliente_id == cliente_id,
            GrafoArista.auditoria_id == auditoria_id
        )
    )
    aristas = res_a.scalars().all()

    return {
        "nodos": [
            {"id": n.id, "tipo": n.tipo, "identificador": n.identificador, "etiqueta": n.etiqueta, "atributos": n.atributos_json}
            for n in nodos
        ],
        "aristas": [
            {"id": a.id, "origen": a.nodo_origen_id, "destino": a.nodo_destino_id, "relacion": a.relacion, "metadatos": a.metadatos_json}
            for a in aristas
        ]
    }
