"""
Endpoints para gestión de jobs en background (scraper, análisis, etc).
"""
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from db import db as crud
from db.models import Job, Usuario, CredencialMarangatu
from api.routers.auth import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreate(BaseModel):
    tipo: str  # 'scraper_rg90', 'scraper_hechauka', 'scraper_dj', 'validar_sifen'
    cliente_ruc: str
    periodo_desde: Optional[str] = None
    periodo_hasta: Optional[str] = None
    params: Optional[dict] = None


class JobResponse(BaseModel):
    id: str
    tipo: str
    estado: str
    progreso: int
    creado_en: str
    iniciado_en: Optional[str] = None
    completado_en: Optional[str] = None
    error_msg: Optional[str] = None
    reintentos: int
    resultado: Optional[dict] = None


@router.post("/encolar", status_code=201)
async def encolar_job(
    body: JobCreate,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Encola un job para ejecución en background.
    Usa credenciales cifradas de CredencialMarangatu.
    """
    # Verificar que existan credenciales para el cliente
    cred_result = await db.execute(
        select(CredencialMarangatu).where(
            CredencialMarangatu.firma_id == user.firma_id,
            CredencialMarangatu.cliente_ruc == body.cliente_ruc,
            CredencialMarangatu.activa == True,
        )
    )
    cred = cred_result.scalar_one_or_none()
    
    if not cred:
        raise HTTPException(
            400,
            f"No hay credenciales activas para el cliente {body.cliente_ruc}. "
            "Cargá las credenciales de Marangatú primero."
        )

    # Construir params del job
    params = {
        "cliente_ruc": body.cliente_ruc,
        "periodo_desde": body.periodo_desde,
        "periodo_hasta": body.periodo_hasta,
        "credencial_id": cred.id,
        **(body.params or {}),
    }

    job = Job(
        firma_id=user.firma_id,
        tipo=body.tipo,
        estado="pendiente",
        params_json=json.dumps(params, ensure_ascii=False),
    )
    db.add(job)
    await db.commit()

    await crud.log_trail(
        db,
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion=f"Job encolado: {body.tipo} para {body.cliente_ruc}",
        modulo="jobs",
        datos={"job_id": job.id, "tipo": body.tipo},
    )

    return {
        "ok": True,
        "job_id": job.id,
        "mensaje": "Job encolado. Se ejecutará en background.",
    }


@router.get("")
async def listar_jobs(
    estado: Optional[str] = None,
    tipo: Optional[str] = None,
    limit: int = 50,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista jobs de la firma con filtros opcionales."""
    q = select(Job).where(Job.firma_id == user.firma_id)
    
    if estado:
        q = q.where(Job.estado == estado)
    if tipo:
        q = q.where(Job.tipo == tipo)
    
    q = q.order_by(Job.creado_en.desc()).limit(limit)
    
    result = await db.execute(q)
    jobs = result.scalars().all()
    
    return [
        {
            "id": j.id,
            "tipo": j.tipo,
            "estado": j.estado,
            "progreso": j.progreso,
            "creado_en": j.creado_en.isoformat() if j.creado_en else None,
            "iniciado_en": j.iniciado_en.isoformat() if j.iniciado_en else None,
            "completado_en": j.completado_en.isoformat() if j.completado_en else None,
            "error_msg": j.error_msg,
            "reintentos": j.reintentos,
            "params": json.loads(j.params_json) if j.params_json else None,
            "resultado": json.loads(j.resultado_json) if j.resultado_json else None,
        }
        for j in jobs
    ]


@router.get("/{job_id}")
async def obtener_job(
    job_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Obtiene detalle de un job específico."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.firma_id == user.firma_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(404, "Job no encontrado")
    
    return {
        "id": job.id,
        "tipo": job.tipo,
        "estado": job.estado,
        "progreso": job.progreso,
        "creado_en": job.creado_en.isoformat() if job.creado_en else None,
        "iniciado_en": job.iniciado_en.isoformat() if job.iniciado_en else None,
        "completado_en": job.completado_en.isoformat() if job.completado_en else None,
        "error_msg": job.error_msg,
        "reintentos": job.reintentos,
        "params": json.loads(job.params_json) if job.params_json else None,
        "resultado": json.loads(job.resultado_json) if job.resultado_json else None,
    }


@router.post("/{job_id}/cancelar")
async def cancelar_job(
    job_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancela un job pendiente o en ejecución."""
    result = await db.execute(
        select(Job).where(Job.id == job_id, Job.firma_id == user.firma_id)
    )
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(404, "Job no encontrado")
    
    if job.estado not in ("pendiente", "ejecutando"):
        raise HTTPException(400, f"No se puede cancelar un job en estado '{job.estado}'")
    
    await db.execute(
        update(Job).where(Job.id == job_id).values(estado="cancelado")
    )
    await db.commit()
    
    await crud.log_trail(
        db,
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion=f"Job cancelado: {job_id}",
        modulo="jobs",
    )
    
    return {"ok": True, "mensaje": "Job cancelado"}
