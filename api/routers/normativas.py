"""
Router para gestión de la Base Legal y Normativas (RAG).
Permite listar normativas vigentes, consultar chunks e importar nuevas resoluciones.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from api.routers.auth import get_current_user
from db.models import Usuario, NormativaLegal, NormativaChunk
from ingesta.normativas_parser import parsear_texto_normativa
from analisis.rag_service import indexar_normativa

router = APIRouter(prefix="/normativas", tags=["normativas-rag"])


class NormativaTextoUpload(BaseModel):
    tipo: str  # 'ley', 'decreto', 'resolucion_general', 'nia'
    numero: str  # '6380/2019', '90/2021', etc.
    titulo: str
    organismo: str = "DNIT"
    texto_completo: str
    es_global: bool = True


@router.get("")
async def listar_normativas(
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    """Lista las normativas disponibles para la firma (globales + privadas)."""
    stmt = (
        select(
            NormativaLegal,
            func.count(NormativaChunk.id).label("total_chunks")
        )
        .outerjoin(NormativaChunk, NormativaChunk.normativa_id == NormativaLegal.id)
        .where(
            or_(
                NormativaLegal.firma_id.is_(None),
                NormativaLegal.firma_id == user.firma_id
            )
        )
        .group_by(NormativaLegal.id)
        .order_by(NormativaLegal.creado_en.desc())
    )
    res = await db.execute(stmt)
    rows = res.all()
    return [
        {
            "id": norm.id,
            "tipo": norm.tipo,
            "numero": norm.numero,
            "titulo": norm.titulo,
            "organismo": norm.organismo,
            "estado": norm.estado,
            "fecha_vigencia": norm.fecha_vigencia,
            "es_global": norm.firma_id is None,
            "total_chunks": int(total_chunks),
            "creado_en": norm.creado_en.isoformat() if norm.creado_en else None
        }
        for norm, total_chunks in rows
    ]


@router.post("/texto")
async def importar_normativa_texto(
    body: NormativaTextoUpload,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    """Importa una normativa a partir de texto estructurado y la vectoriza en el RAG."""
    # Verificar si ya existe el número para evitar duplicados
    check_stmt = select(NormativaLegal).where(
        NormativaLegal.numero == body.numero.strip()
    )
    if not body.es_global:
        check_stmt = check_stmt.where(NormativaLegal.firma_id == user.firma_id)
    else:
        check_stmt = check_stmt.where(NormativaLegal.firma_id.is_(None))

    existente = (await db.execute(check_stmt)).scalar_one_or_none()
    if existente:
        norm = existente
    else:
        norm = NormativaLegal(
            firma_id=None if body.es_global else user.firma_id,
            tipo=body.tipo,
            numero=body.numero.strip(),
            titulo=body.titulo.strip(),
            organismo=body.organismo
        )
        db.add(norm)
        await db.commit()
        await db.refresh(norm)

    # Parsear y segmentar por artículos
    chunks = parsear_texto_normativa(body.texto_completo, f"{body.tipo.upper()} {body.numero}")
    total_idx = await indexar_normativa(db, norm.id, chunks)

    return {
        "status": "ok",
        "normativa_id": norm.id,
        "numero": norm.numero,
        "chunks_indexados": total_idx
    }


@router.get("/{normativa_id}/chunks")
async def obtener_chunks_normativa(
    normativa_id: str,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    """Retorna los fragmentos indexados de una normativa específica."""
    res_norm = await db.execute(
        select(NormativaLegal).where(
            NormativaLegal.id == normativa_id,
            or_(NormativaLegal.firma_id.is_(None), NormativaLegal.firma_id == user.firma_id)
        )
    )
    norm = res_norm.scalar_one_or_none()
    if not norm:
        raise HTTPException(404, "Normativa no encontrada")

    res_chunks = await db.execute(
        select(NormativaChunk)
        .where(NormativaChunk.normativa_id == normativa_id)
        .order_by(NormativaChunk.creado_en.asc())
    )
    chunks = res_chunks.scalars().all()
    return [
        {
            "id": c.id,
            "jerarquia": c.jerarquia,
            "articulo": c.articulo,
            "texto": c.texto
        }
        for c in chunks
    ]
