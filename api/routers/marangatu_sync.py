"""
Router para sincronización e ingesta directa desde Marangatú (REA).
Soporta tanto sincronización HTTP por cookie de sesión como recepción
directa de payloads enviados desde el Bookmarklet 1-Clic.
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from api.routers.auth import get_current_user
from db.models import Usuario, Auditoria, RG90, _uuid
from ingesta.marangatu_http import MarangatuHttpClient, parsear_registros_marangatu
from ingesta.sifen_client import verificar_lote_cdcs

router = APIRouter(prefix="/auditorias", tags=["marangatu-sync"])


class MarangatuVerificarRequest(BaseModel):
    cookie: str


class MarangatuSyncRequest(BaseModel):
    cookie: Optional[str] = None
    periodo: Optional[str] = None
    tipo: str = "ambos"  # "compras", "ventas", "ambos"
    payload_directo: Optional[List[Dict[str, Any]]] = None


@router.post("/{auditoria_id}/marangatu/verificar")
async def verificar_sesion_marangatu(
    auditoria_id: str,
    req: MarangatuVerificarRequest,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    """Verifica si la sesión tributaria de Marangatú provista está activa."""
    auditoria = await db.get(Auditoria, auditoria_id)
    if not auditoria or auditoria.firma_id != user.firma_id:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    client = MarangatuHttpClient()
    res = await client.verificar_sesion(req.cookie)
    return res


@router.post("/{auditoria_id}/marangatu/sync")
async def sincronizar_marangatu(
    auditoria_id: str,
    req: MarangatuSyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    """
    Sincroniza comprobantes RG 90 a la auditoría.
    Puede recibir un payload directo del Bookmarklet o descargar vía sesión HTTP.
    """
    auditoria = await db.get(Auditoria, auditoria_id)
    if not auditoria or auditoria.firma_id != user.firma_id:
        raise HTTPException(status_code=404, detail="Auditoría no encontrada")

    registros_raw: List[Dict[str, Any]] = []

    if req.payload_directo:
        registros_raw = parsear_registros_marangatu(req.payload_directo)
    elif req.cookie:
        client = MarangatuHttpClient()
        verif = await client.verificar_sesion(req.cookie)
        if not verif.get("valido"):
            raise HTTPException(status_code=400, detail=verif.get("error", "Sesión de Marangatú inválida"))
        
        ruc = verif.get("ruc", "")
        talones = await client.listar_talones_rg90(req.cookie, ruc, req.periodo or auditoria.periodo_desde)
        for talon in talones:
            id_talon = talon.get("id")
            if id_talon:
                archivo_bytes = await client.descargar_comprobantes(req.cookie, id_talon)
                # Parsear archivo bytes si aplica
    else:
        raise HTTPException(status_code=400, detail="Debe proveer una cookie de sesión o un payload directo")

    cdcs_a_validar: List[str] = []
    insertados = 0

    for item in registros_raw:
        cdc = item.get("cdc")
        if cdc:
            cdcs_a_validar.append(cdc)

        rg_obj = RG90(
            id=_uuid(),
            firma_id=user.firma_id,
            cliente_id=auditoria.cliente_id,
            auditoria_id=auditoria.id,
            periodo=req.periodo or auditoria.periodo_desde,
            tipo=item.get("tipo", "compra"),
            tipo_comprobante=item.get("tipo_comprobante", "109"),
            ruc_contraparte=item.get("ruc_contraparte", ""),
            nombre_contraparte=item.get("razon_social_contraparte", ""),
            timbrado=item.get("timbrado", ""),
            establecimiento=item.get("establecimiento", "001"),
            punto_expedicion=item.get("punto_expedicion", "001"),
            nro_comprobante=item.get("numero_documento", "0000001"),
            fecha_emision=item.get("fecha_comprobante") or "2024-01-01",
            base_gravada_10=int(item.get("gravada_10", 0.0) or 0),
            iva_10=int(item.get("iva_10", 0.0) or 0),
            base_gravada_5=int(item.get("gravada_5", 0.0) or 0),
            iva_5=int(item.get("iva_5", 0.0) or 0),
            monto_exento=int(item.get("exenta", 0.0) or 0),
            iva_total=int((item.get("iva_10", 0.0) or 0) + (item.get("iva_5", 0.0) or 0)),
            total_comprobante=int(item.get("total_comprobante", 0.0) or 0),
            cdc=cdc
        )
        db.add(rg_obj)
        insertados += 1

    await db.commit()

    # Validación asíncrona de CDCs en segundo plano
    if cdcs_a_validar:
        background_tasks.add_task(verificar_lote_cdcs, db, cdcs_a_validar, consultar_online=False)

    return {
        "ok": True,
        "insertados": insertados,
        "cdcs_pendientes": len(cdcs_a_validar),
        "periodo": req.periodo or auditoria.periodo_desde
    }
