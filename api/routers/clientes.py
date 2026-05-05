"""
Router para la gestión de clientes en un entorno multi-tenant.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from db.base import get_db
from db import db as crud
from db.models import Usuario, Cliente, Firma
from api.routers.auth import get_current_user

router = APIRouter(prefix="/clientes", tags=["clientes"])

class ClienteCreate(BaseModel):
    ruc: str
    razon_social: str
    regimen: str
    nombre_fantasia: Optional[str] = None
    actividad_principal: Optional[str] = None
    tipo_contribuyente: Optional[str] = None
    direccion: Optional[str] = None
    email_dnit: Optional[str] = None

@router.get("")
async def listar_clientes(
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    clientes = await crud.listar_clientes(db, user.firma_id)
    return [
        {
            "id": c.id,
            "ruc": c.ruc,
            "razon_social": c.razon_social,
            "nombre_fantasia": c.nombre_fantasia,
            "actividad_principal": c.actividad_principal,
            "regimen": c.regimen,
            "direccion": c.direccion,
            "email_dnit": c.email_dnit,
            "estado_dnit": c.estado_dnit,
        }
        for c in clientes
    ]

@router.post("", status_code=201)
async def crear_cliente(
    body: ClienteCreate,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from config.plans import get_plan, PLAN_ALIAS_MAP

    # Verificar límite de clientes según plan
    firma_result = await db.execute(select(Firma).where(Firma.id == user.firma_id))
    firma = firma_result.scalar_one_or_none()

    if firma:
        plan_key = PLAN_ALIAS_MAP.get(firma.plan, firma.plan)
        plan_cfg = get_plan(plan_key)

        if plan_cfg.max_clientes is not None:
            count_result = await db.execute(
                select(func.count(Cliente.id)).where(Cliente.firma_id == user.firma_id)
            )
            num_clientes = count_result.scalar() or 0
            if num_clientes >= plan_cfg.max_clientes:
                raise HTTPException(
                    403,
                    f"Tu plan {plan_cfg.nombre} permite hasta {plan_cfg.max_clientes} clientes. "
                    f"Actualmente tenés {num_clientes}. Contactanos para actualizar tu plan."
                )

    cliente = await crud.crear_cliente(db, firma_id=user.firma_id, **body.model_dump())
    return {"id": cliente.id, "ruc": cliente.ruc, "razon_social": cliente.razon_social}

@router.get("/{cliente_id}")
async def get_cliente(
    cliente_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    cliente = await crud.get_cliente(db, firma_id=user.firma_id, id=cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")
    return {
        "id": cliente.id,
        "ruc": cliente.ruc,
        "razon_social": cliente.razon_social,
        "nombre_fantasia": cliente.nombre_fantasia,
        "regimen": cliente.regimen,
        "tipo_contribuyente": cliente.tipo_contribuyente,
        "actividad_principal": cliente.actividad_principal,
        "estado_dnit": cliente.estado_dnit,
        "fecha_inscripcion": cliente.fecha_inscripcion,
    }
