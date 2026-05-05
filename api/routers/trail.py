"""
Endpoints de Audit Trail y Configuración de Firma.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from db import db as crud
from db.models import Firma, Usuario
from api.routers.auth import get_current_user, get_current_admin

router = APIRouter(tags=["firma"])


# ============================================================
#  Audit Trail
# ============================================================

@router.get("/audit-trail")
async def listar_audit_trail(
    auditoria_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista las entradas del audit trail de la firma, más recientes primero."""
    from db.models import AuditTrail, Auditoria, Cliente
    from sqlalchemy import select, outerjoin

    q = (
        select(AuditTrail, Usuario.nombre.label("usuario_nombre"))
        .outerjoin(Usuario, AuditTrail.usuario_id == Usuario.id)
        .where(AuditTrail.firma_id == user.firma_id)
    )
    if auditoria_id:
        q = q.where(AuditTrail.auditoria_id == auditoria_id)
    q = q.order_by(AuditTrail.timestamp.desc()).limit(limit).offset(offset)

    result = await db.execute(q)
    rows = result.all()

    return [
        {
            "id": t.id,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "accion": t.accion,
            "modulo": t.modulo,
            "detalle": t.detalle,
            "resultado": t.resultado,
            "auditoria_id": t.auditoria_id,
            "usuario_nombre": nombre or "Sistema",
        }
        for t, nombre in rows
    ]


# ============================================================
#  Configuración de Firma
# ============================================================

class FirmaUpdate(BaseModel):
    nombre: Optional[str] = None
    ruc: Optional[str] = None
    email: Optional[str] = None
    eslogan: Optional[str] = None


@router.get("/firmas/configuracion")
async def get_configuracion_firma(
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Obtiene la configuración de la firma del usuario autenticado."""
    result = await db.execute(select(Firma).where(Firma.id == user.firma_id))
    firma = result.scalar_one_or_none()
    if not firma:
        raise HTTPException(404, "Firma no encontrada")

    return {
        "id": firma.id,
        "nombre": firma.nombre,
        "ruc": firma.ruc,
        "email": firma.email,
        "eslogan": firma.eslogan,
        "plan": firma.plan,
        "activa": firma.activa,
        "trial_hasta": firma.trial_hasta.isoformat() if firma.trial_hasta else None,
        "logo_path": firma.logo_path,
        "creado_en": firma.creado_en.isoformat() if firma.creado_en else None,
    }


@router.patch("/firmas/configuracion")
async def actualizar_configuracion_firma(
    body: FirmaUpdate,
    user: Usuario = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza los datos de la firma. Solo admins."""
    from sqlalchemy import update as sa_update

    vals = body.model_dump(exclude_none=True)
    if not vals:
        raise HTTPException(400, "Sin campos para actualizar")

    await db.execute(
        sa_update(Firma).where(Firma.id == user.firma_id).values(**vals)
    )
    await db.commit()

    await crud.log_trail(
        db,
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion="Configuración de firma actualizada",
        modulo="configuracion",
        datos={"campos": list(vals.keys())},
    )

    return {"ok": True, **vals}


@router.post("/firmas/configuracion/logo")
async def subir_logo_firma(
    user: Usuario = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Placeholder — subida de logo via multipart se maneja en archivos."""
    raise HTTPException(501, "Use el endpoint /archivos con tipo=logo_cliente")
