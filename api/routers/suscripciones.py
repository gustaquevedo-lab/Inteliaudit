"""
Endpoints de suscripciones y planes.
Cobro manual (transferencia) con arquitectura preparada para Bancard vPOS.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config.plans import PLANES, PLAN_ALIAS_MAP, get_plan
from db.base import get_db
from db import db as crud
from db.models import Firma, Suscripcion, Usuario
from api.routers.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/suscripciones", tags=["suscripciones"])


@router.get("/planes")
async def listar_planes():
    """Retorna todos los planes con precios y features."""
    return [
        {
            "id": p.id,
            "nombre": p.nombre,
            "precio_mensual": p.precio_mensual,
            "precio_anual": p.precio_anual,
            "max_clientes": p.max_clientes,
            "max_usuarios": p.max_usuarios,
            "tiene_ia": p.tiene_ia,
            "tiene_portal_cliente": p.tiene_portal_cliente,
            "features": p.features,
            "soporte": p.soporte,
        }
        for p in PLANES.values()
    ]


class SolicitarSuscripcionBody(BaseModel):
    plan_id: str = Field(..., description="starter | pro | enterprise")
    periodo: str = Field("mensual", pattern=r"^(mensual|anual)$")
    ruc_facturacion: Optional[str] = None
    razon_social_facturacion: Optional[str] = None


@router.post("/solicitar", status_code=201)
async def solicitar_suscripcion(
    body: SolicitarSuscripcionBody,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """El usuario solicita un plan. Genera pedido pendiente de confirmacion."""
    if body.plan_id not in PLANES:
        raise HTTPException(400, f"Plan invalido: {body.plan_id}")

    plan_cfg = get_plan(body.plan_id)

    # Verificar si ya tiene suscripcion activa
    existing = await db.execute(
        select(Suscripcion).where(
            Suscripcion.firma_id == user.firma_id,
            Suscripcion.estado == "activa",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Ya tenes una suscripcion activa")

    monto = plan_cfg.precio_anual if body.periodo == "anual" else plan_cfg.precio_mensual

    suscripcion = Suscripcion(
        firma_id=user.firma_id,
        plan_id=body.plan_id,
        estado="pendiente",
        metodo_pago="transferencia",
        fecha_inicio=datetime.now(timezone.utc),
        monto_pyg=monto,
        notas_admin=(
            f"Solicitud de plan {plan_cfg.nombre} ({body.periodo}). "
            f"RUC: {body.ruc_facturacion or '—'}, "
            f"Razon social: {body.razon_social_facturacion or '—'}"
        ),
    )
    db.add(suscripcion)
    await db.flush()

    await crud.log_trail(db, firma_id=user.firma_id, usuario_id=user.id,
        accion=f"Suscripcion solicitada: {plan_cfg.nombre} ({body.periodo})",
        modulo="suscripciones")
    await db.commit()

    return {
        "ok": True,
        "suscripcion_id": suscripcion.id,
        "plan": plan_cfg.nombre,
        "monto_pyg": monto,
        "mensaje": f"Solicitud recibida. Te enviaremos los datos de transferencia por email.",
        "datos_transferencia": {
            "banco": "Banco Continental",
            "titular": "Inteliaudit S.A.",
            "ruc": "80012345-1",
            "cuenta": "123456789/0",
            "monto": monto,
            "concepto": f"Inteliaudit - {plan_cfg.nombre} - Firma {user.firma_id[:8]}",
        },
    }


@router.patch("/{suscripcion_id}/confirmar")
async def confirmar_suscripcion(
    suscripcion_id: str,
    body: dict,
    user: Usuario = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Admin confirma pago recibido y activa la suscripcion."""
    result = await db.execute(
        select(Suscripcion).where(Suscripcion.id == suscripcion_id, Suscripcion.firma_id == user.firma_id)
    )
    susc = result.scalar_one_or_none()
    if not susc:
        raise HTTPException(404, "Suscripcion no encontrada")

    from datetime import timedelta

    susc.estado = "activa"
    susc.comprobante_nro = body.get("comprobante_nro")
    susc.notas_admin = body.get("notas", susc.notas_admin)
    susc.fecha_fin = datetime.now(timezone.utc) + timedelta(days=365 if susc.monto_pyg > 1000000 else 30)

    # Actualizar plan de la firma
    firma_result = await db.execute(select(Firma).where(Firma.id == user.firma_id))
    firma = firma_result.scalar_one_or_none()
    if firma:
        firma.plan = susc.plan_id

    await crud.log_trail(db, firma_id=user.firma_id, usuario_id=user.id,
        accion=f"Suscripcion confirmada: {susc.plan_id}",
        modulo="suscripciones", datos={"suscripcion_id": susc.id})
    await db.commit()

    return {"ok": True, "plan": susc.plan_id, "estado": "activa"}


@router.get("/mi-plan")
async def mi_suscripcion(
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Estado de suscripcion de la firma actual."""
    firma_res = await db.execute(select(Firma).where(Firma.id == user.firma_id))
    firma = firma_res.scalar_one_or_none()
    if not firma:
        raise HTTPException(404, "Firma no encontrada")

    plan_key = PLAN_ALIAS_MAP.get(firma.plan, firma.plan)
    plan_cfg = get_plan(plan_key)

    susc_result = await db.execute(
        select(Suscripcion).where(
            Suscripcion.firma_id == user.firma_id,
            Suscripcion.estado == "activa",
        ).order_by(Suscripcion.creado_en.desc()).limit(1)
    )
    susc = susc_result.scalar_one_or_none()

    en_trial = firma.plan == "trial"
    trial_expirado = en_trial and firma.trial_hasta and datetime.now(timezone.utc) > firma.trial_hasta
    dias_restantes = (firma.trial_hasta - datetime.now(timezone.utc)).days if firma.trial_hasta and en_trial and not trial_expirado else 0

    return {
        "plan_actual": plan_cfg.nombre,
        "plan_id": plan_key,
        "en_trial": en_trial,
        "trial_expirado": trial_expirado,
        "dias_restantes": max(0, dias_restantes),
        "trial_hasta": firma.trial_hasta.isoformat() if firma.trial_hasta else None,
        "suscripcion_activa": susc is not None,
        "suscripcion": {
            "id": susc.id,
            "plan_id": susc.plan_id,
            "estado": susc.estado,
            "fecha_inicio": susc.fecha_inicio.isoformat() if susc else None,
            "fecha_fin": susc.fecha_fin.isoformat() if susc else None,
            "metodo_pago": susc.metodo_pago if susc else None,
            "monto_pyg": susc.monto_pyg if susc else 0,
        } if susc else None,
        "limites": {
            "max_clientes": plan_cfg.max_clientes,
            "max_usuarios": plan_cfg.max_usuarios,
            "tiene_ia": plan_cfg.tiene_ia,
            "tiene_portal_cliente": plan_cfg.tiene_portal_cliente,
        },
    }
