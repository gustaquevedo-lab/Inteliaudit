"""
Endpoints de gestión de hallazgos — automatizados y manuales del auditor.
"""
import json
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo
from db.base import get_db
from db import db as crud
from db.models import Hallazgo, Usuario
from api.routers.auth import get_current_user

router = APIRouter(prefix="/auditorias/{auditoria_id}/hallazgos", tags=["hallazgos"])


# ============================================================
#  Schemas
# ============================================================

class HallazgoManualCreate(BaseModel):
    impuesto: Literal["IVA", "IRE", "IRP", "IDU", "RET_IVA", "RET_IRE", "OTRO"]
    periodo: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="YYYY-MM")
    tipo_hallazgo: str
    descripcion: str
    articulo_legal: str
    base_ajuste: int = Field(0, ge=0)
    impuesto_omitido: int = Field(0, ge=0)
    fecha_omision: Optional[str] = Field(None, description="YYYY-MM-DD para cálculo de intereses")
    nivel_riesgo: Literal["alto", "medio", "bajo"] = "medio"
    descripcion_tecnica: Optional[str] = None
    notas_auditor: Optional[str] = None
    evidencias: list[dict] = []


class HallazgoUpdate(BaseModel):
    estado: Optional[Literal["pendiente", "confirmado", "descartado", "regularizado"]] = None
    nivel_riesgo: Optional[Literal["alto", "medio", "bajo"]] = None
    notas_auditor: Optional[str] = None
    descripcion: Optional[str] = None
    impuesto_omitido: Optional[int] = Field(None, ge=0)
    base_ajuste: Optional[int] = Field(None, ge=0)


# ============================================================
#  Endpoints
# ============================================================

@router.get("")
async def listar_hallazgos(
    auditoria_id: str,
    impuesto: Optional[str] = None,
    estado: Optional[str] = None,
    riesgo: Optional[str] = None,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista hallazgos filtrados por firma_id."""
    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    hallazgos = await crud.get_hallazgos(
        db, 
        firma_id=user.firma_id, 
        auditoria_id=auditoria_id, 
        impuesto=impuesto, 
        estado=estado
    )
    
    if riesgo:
        hallazgos = [h for h in hallazgos if h.nivel_riesgo == riesgo]

    return [_serializar(h) for h in hallazgos]


@router.post("", status_code=201)
async def crear_hallazgo_manual(
    auditoria_id: str,
    body: HallazgoManualCreate,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Crea un hallazgo manual asegurando el aislamiento."""
    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada o sin acceso")

    multa = 0
    intereses = 0
    if body.impuesto_omitido > 0 and body.fecha_omision:
        cont = calcular_contingencia(body.impuesto_omitido, body.fecha_omision)
        multa = cont["multa_estimada"]
        intereses = cont["intereses_estimados"]
    else:
        multa = int(body.impuesto_omitido * 0.50)

    nivel = body.nivel_riesgo
    if body.impuesto_omitido > 0:
        total = body.impuesto_omitido + multa + intereses
        nivel = clasificar_riesgo(total, auditoria.materialidad)

    hallazgo = await crud.crear_hallazgo(
        db,
        firma_id=user.firma_id,
        auditoria_id=auditoria_id,
        impuesto=body.impuesto,
        periodo=body.periodo,
        tipo_hallazgo=body.tipo_hallazgo,
        descripcion=body.descripcion,
        articulo_legal=body.articulo_legal,
        base_ajuste=body.base_ajuste,
        impuesto_omitido=body.impuesto_omitido,
        multa_estimada=multa,
        intereses_estimados=intereses,
        nivel_riesgo=nivel,
        descripcion_tecnica=body.descripcion_tecnica,
        evidencias=body.evidencias,
        creado_por="auditor",
    )
    
    if body.notas_auditor:
        await db.execute(
            update(Hallazgo)
            .where(Hallazgo.id == hallazgo.id, Hallazgo.firma_id == user.firma_id)
            .values(notas_auditor=body.notas_auditor)
        )

    await crud.log_trail(
        db, 
        firma_id=user.firma_id, 
        usuario_id=user.id,
        accion=f"Hallazgo manual creado: {body.tipo_hallazgo}", 
        modulo="hallazgos", 
        auditoria_id=auditoria_id, 
        datos={"hallazgo_id": hallazgo.id}
    )
    return _serializar(hallazgo)


@router.get("/{hallazgo_id}")
async def get_hallazgo(
    auditoria_id: str,
    hallazgo_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Hallazgo).where(
            Hallazgo.id == hallazgo_id, 
            Hallazgo.auditoria_id == auditoria_id,
            Hallazgo.firma_id == user.firma_id
        )
    )
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(404, "Hallazgo no encontrado o sin acceso")
    return _serializar(h)


@router.patch("/{hallazgo_id}")
async def actualizar_hallazgo(
    auditoria_id: str,
    hallazgo_id: str,
    body: HallazgoUpdate,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Hallazgo).where(
            Hallazgo.id == hallazgo_id, 
            Hallazgo.firma_id == user.firma_id
        )
    )
    h = result.scalar_one_or_none()
    if not h:
        raise HTTPException(404, "Hallazgo no encontrado")

    vals = body.model_dump(exclude_none=True)
    if "impuesto_omitido" in vals:
        nuevo_impuesto = vals["impuesto_omitido"]
        vals["multa_estimada"] = int(nuevo_impuesto * 0.50)

    await db.execute(
        update(Hallazgo)
        .where(Hallazgo.id == hallazgo_id, Hallazgo.firma_id == user.firma_id)
        .values(**vals)
    )
    
    await crud.log_trail(
        db, 
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion=f"Hallazgo actualizado: {hallazgo_id[:8]}", 
        modulo="hallazgos", 
        auditoria_id=auditoria_id, 
        datos=vals
    )

    return _serializar(h)


@router.delete("/{hallazgo_id}")
async def descartar_hallazgo(
    auditoria_id: str,
    hallazgo_id: str,
    motivo: str = "Descartado por el auditor",
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Descarta un hallazgo con motivo."""
    await db.execute(
        update(Hallazgo)
        .where(
            Hallazgo.id == hallazgo_id, 
            Hallazgo.auditoria_id == auditoria_id,
            Hallazgo.firma_id == user.firma_id
        )
        .values(estado="descartado", notas_auditor=motivo)
    )
    return {"ok": True, "estado": "descartado"}


@router.post("/{hallazgo_id}/confirmar")
async def confirmar_hallazgo(
    auditoria_id: str,
    hallazgo_id: str,
    notas: Optional[str] = None,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """El auditor confirma un hallazgo del sistema."""
    vals: dict = {"estado": "confirmado"}
    if notas:
        vals["notas_auditor"] = notas
    
    await db.execute(
        update(Hallazgo)
        .where(
            Hallazgo.id == hallazgo_id, 
            Hallazgo.firma_id == user.firma_id
        )
        .values(**vals)
    )
    
    await crud.log_trail(
        db, 
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion=f"Hallazgo confirmado: {hallazgo_id[:8]}", 
        modulo="hallazgos", 
        auditoria_id=auditoria_id
    )
    return {"ok": True, "estado": "confirmado"}


@router.get("/resumen/contingencias")
async def resumen_contingencias(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resumen de contingencias por impuesto y nivel de riesgo."""
    from analisis.riesgo import resumir_contingencias
    hallazgos = await crud.get_hallazgos(db, user.firma_id, auditoria_id)
    datos = [_serializar(h) for h in hallazgos]
    return resumir_contingencias(datos)


# ============================================================
#  Helpers
# ============================================================

def _serializar(h: Hallazgo) -> dict:
    return {
        "id": h.id,
        "impuesto": h.impuesto,
        "periodo": h.periodo,
        "tipo_hallazgo": h.tipo_hallazgo,
        "descripcion": h.descripcion,
        "descripcion_tecnica": h.descripcion_tecnica,
        "articulo_legal": h.articulo_legal,
        "base_ajuste": h.base_ajuste,
        "impuesto_omitido": h.impuesto_omitido,
        "multa_estimada": h.multa_estimada,
        "intereses_estimados": h.intereses_estimados,
        "total_contingencia": h.total_contingencia,
        "nivel_riesgo": h.nivel_riesgo,
        "estado": h.estado,
        "evidencias": json.loads(h.evidencias or "[]"),
        "notas_auditor": h.notas_auditor,
        "creado_por": h.creado_por,
        "creado_en": h.creado_en.isoformat() if h.creado_en else None,
    }

