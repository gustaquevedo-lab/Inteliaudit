"""
Portal de cliente — acceso read-only compartido via JWT.
El auditor genera un token; el cliente lo usa para ver hallazgos sin login.
Solo disponible en plan Enterprise.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.plans import PLAN_ALIAS_MAP, get_plan
from config.settings import settings
from db.base import get_db
from db import db as crud
from db.models import Auditoria, Cliente, Firma, Hallazgo, Informe, Usuario
from api.routers.auth import get_current_user

router = APIRouter(prefix="/portal", tags=["portal"])


class GenerarLinkBody(BaseModel):
    auditoria_id: str
    hallazgos_visibles: list[str] = []
    expira_en_dias: int = 30


@router.post("/generar-link", status_code=201)
async def generar_link_portal(
    body: GenerarLinkBody,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Genera link JWT para portal del cliente. Solo Enterprise y admin/auditor_senior."""
    if user.rol not in ("super_admin", "admin", "auditor_senior"):
        raise HTTPException(403, "Solo admin o auditor senior puede generar links")

    firma_result = await db.execute(select(Firma).where(Firma.id == user.firma_id))
    firma = firma_result.scalar_one_or_none()
    if not firma:
        raise HTTPException(404, "Firma no encontrada")

    plan_key = PLAN_ALIAS_MAP.get(firma.plan, firma.plan)
    plan_cfg = get_plan(plan_key)
    if not plan_cfg.tiene_portal_cliente:
        raise HTTPException(403, "Portal del cliente disponible solo en plan Enterprise")

    auditoria = await crud.get_auditoria(db, user.firma_id, body.auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoria no encontrada")

    expira = datetime.now(timezone.utc) + timedelta(days=body.expira_en_dias)
    token = jwt.encode(
        {
            "tipo": "portal",
            "auditoria_id": body.auditoria_id,
            "firma_id": user.firma_id,
            "hallazgos_ids": body.hallazgos_visibles,
            "exp": expira,
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )

    await crud.log_trail(db, firma_id=user.firma_id, usuario_id=user.id,
        accion=f"Link portal generado para {body.auditoria_id[:8]}",
        modulo="portal", auditoria_id=body.auditoria_id,
        datos={"expira_dias": body.expira_en_dias, "hallazgos": len(body.hallazgos_visibles)})
    await db.commit()

    return {
        "token": token,
        "url": f"/portal/{token}",
        "expira": expira.isoformat(),
        "hallazgos_incluidos": len(body.hallazgos_visibles),
    }


@router.get("/{token}")
async def ver_portal_cliente(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Endpoint publico — el cliente accede con su token JWT."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("tipo") != "portal":
            raise HTTPException(403, "Token invalido")
        auditoria_id = payload.get("auditoria_id")
        firma_id = payload.get("firma_id")
        hallazgos_ids = payload.get("hallazgos_ids", [])
    except JWTError:
        raise HTTPException(403, "Token invalido o expirado")

    if not auditoria_id or not firma_id:
        raise HTTPException(404, "Portal no encontrado")

    result = await db.execute(select(Auditoria).where(Auditoria.id == auditoria_id, Auditoria.firma_id == firma_id))
    auditoria = result.scalar_one_or_none()
    if not auditoria:
        raise HTTPException(404, "Auditoria no encontrada")

    cliente = await crud.get_cliente(db, firma_id, id=auditoria.cliente_id)
    firma_result = await db.execute(select(Firma).where(Firma.id == firma_id))
    firma = firma_result.scalar_one_or_none()

    # Hallazgos filtrados por los IDs que el auditor selecciono
    if hallazgos_ids:
        hallazgos_result = await db.execute(
            select(Hallazgo).where(
                Hallazgo.id.in_(hallazgos_ids),
                Hallazgo.auditoria_id == auditoria_id,
                Hallazgo.firma_id == firma_id,
            ).order_by(Hallazgo.total_contingencia.desc())
        )
    else:
        hallazgos_result = await db.execute(
            select(Hallazgo).where(
                Hallazgo.auditoria_id == auditoria_id,
                Hallazgo.firma_id == firma_id,
                Hallazgo.estado != "descartado",
            ).order_by(Hallazgo.total_contingencia.desc())
        )
    hallazgos = hallazgos_result.scalars().all()

    total_contingencia = sum(h.total_contingencia for h in hallazgos)
    por_riesgo = {"alto": 0, "medio": 0, "bajo": 0}
    for h in hallazgos:
        por_riesgo[h.nivel_riesgo] = por_riesgo.get(h.nivel_riesgo, 0) + 1

    return {
        "firma": {
            "nombre": firma.nombre if firma else "Firma Auditora",
            "eslogan": firma.eslogan if firma else None,
        },
        "cliente": {
            "razon_social": cliente.razon_social if cliente else "—",
            "ruc": cliente.ruc if cliente else "—",
        },
        "auditoria": {
            "id": auditoria.id,
            "periodo_desde": auditoria.periodo_desde,
            "periodo_hasta": auditoria.periodo_hasta,
            "impuestos": json.loads(auditoria.impuestos),
            "estado": auditoria.estado,
            "auditor": auditoria.auditor,
        },
        "resumen": {
            "total_hallazgos": len(hallazgos),
            "total_contingencia": total_contingencia,
            "por_riesgo": por_riesgo,
        },
        "hallazgos": [
            {
                "id": h.id,
                "impuesto": h.impuesto,
                "periodo": h.periodo,
                "tipo_hallazgo": h.tipo_hallazgo,
                "descripcion": h.descripcion,
                "articulo_legal": h.articulo_legal,
                "impuesto_omitido": h.impuesto_omitido,
                "multa_estimada": h.multa_estimada,
                "intereses_estimados": h.intereses_estimados,
                "total_contingencia": h.total_contingencia,
                "nivel_riesgo": h.nivel_riesgo,
                "estado": h.estado,
            }
            for h in hallazgos
        ],
        "token_expira": datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat() if "exp" in payload else "",
    }


@router.get("/{token}/informe")
async def descargar_informe_portal(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Descarga el informe PDF final de la auditoria. Sin auth, solo con token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        if payload.get("tipo") != "portal":
            raise HTTPException(403, "Token invalido")
        auditoria_id = payload.get("auditoria_id")
    except JWTError:
        raise HTTPException(403, "Token invalido o expirado")

    if not auditoria_id:
        raise HTTPException(404, "Auditoria no encontrada")

    # Buscar el informe mas reciente con PDF
    result = await db.execute(
        select(Informe).where(
            Informe.auditoria_id == auditoria_id,
            Informe.archivo_pdf != None,
            Informe.estado == "generado",
        ).order_by(Informe.generado_en.desc()).limit(1)
    )
    informe = result.scalar_one_or_none()
    if not informe or not informe.archivo_pdf:
        raise HTTPException(404, "No hay informe PDF disponible para esta auditoria")

    # Verificar que el archivo existe
    ruta_informe = Path(settings.storage_path) / informe.archivo_pdf
    if not ruta_informe.exists():
        ruta_informe = Path(informe.archivo_pdf)
    if not ruta_informe.exists():
        raise HTTPException(404, "Archivo de informe no encontrado en storage")

    return FileResponse(
        path=str(ruta_informe),
        media_type="application/pdf",
        filename=f"informe_auditoria.pdf",
        headers={"Content-Disposition": "inline; filename=informe_auditoria.pdf"},
    )
