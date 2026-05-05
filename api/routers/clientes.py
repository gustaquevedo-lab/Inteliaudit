"""
Router para la gestión de clientes en un entorno multi-tenant.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from db import db as crud
from db.models import Usuario
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
