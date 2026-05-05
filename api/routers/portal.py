"""
Portal de cliente — acceso read-only compartido.
El auditor genera un token único; el cliente lo usa para ver sus hallazgos sin login.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from db import db as crud
from db.models import Auditoria, Cliente, Firma, Hallazgo, Usuario
from api.routers.auth import get_current_user

router = APIRouter(prefix="/portal", tags=["portal"])

# ============================================================
#  Generar token de acceso para portal cliente
# ============================================================

@router.post("/auditorias/{auditoria_id}/generar-token")
async def generar_token_portal(
    auditoria_id: str,
    dias_validez: int = 30,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Genera (o regenera) un token de acceso único para el portal del cliente."""
    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    token = secrets.token_urlsafe(32)
    expira = datetime.now(timezone.utc) + timedelta(days=dias_validez)

    # Guardar token en notas del campo reservado (reutilizamos notas con prefijo especial)
    # En producción esto iría en una tabla dedicada portal_tokens
    # Por ahora embebemos en notas con JSON-like prefix
    import json
    portal_data = {
        "portal_token": token,
        "portal_expira": expira.isoformat(),
    }
    notas_actuales = auditoria.notas or ""
    # Limpiar portal_data anterior si existe
    if "__portal__" in notas_actuales:
        import re
        notas_actuales = re.sub(r'__portal__\{.*?\}__portal__', '', notas_actuales).strip()

    notas_nuevas = f"__portal__{json.dumps(portal_data)}__portal__\n{notas_actuales}".strip()

    await db.execute(
        update(Auditoria).where(Auditoria.id == auditoria_id).values(notas=notas_nuevas)
    )
    await db.commit()

    await crud.log_trail(
        db,
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion="Token portal cliente generado",
        modulo="portal",
        auditoria_id=auditoria_id,
        datos={"dias_validez": dias_validez},
    )

    return {
        "token": token,
        "expira": expira.isoformat(),
        "url": f"/portal/{token}",
    }


# ============================================================
#  Acceso público al portal (sin auth, sólo con token)
# ============================================================

@router.get("/{token}")
async def ver_portal_cliente(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Endpoint público — el cliente accede con su token único."""
    import json, re
    from datetime import datetime, timezone

    # Buscar la auditoría que tiene este token en sus notas
    result = await db.execute(
        select(Auditoria).where(Auditoria.notas.contains(token))
    )
    auditoria = result.scalar_one_or_none()

    if not auditoria:
        raise HTTPException(404, "Portal no encontrado o token inválido")

    # Extraer y validar portal_data
    notas = auditoria.notas or ""
    match = re.search(r'__portal__(\{.*?\})__portal__', notas, re.DOTALL)
    if not match:
        raise HTTPException(404, "Token no válido")

    portal_data = json.loads(match.group(1))
    if portal_data.get("portal_token") != token:
        raise HTTPException(403, "Token incorrecto")

    expira = datetime.fromisoformat(portal_data["portal_expira"])
    if datetime.now(timezone.utc) > expira:
        raise HTTPException(403, "El enlace de acceso ha expirado. Contacte a su auditor.")

    # Cargar datos de cliente y firma
    cliente = await crud.get_cliente(db, auditoria.firma_id, id=auditoria.cliente_id)
    firma_result = await db.execute(select(Firma).where(Firma.id == auditoria.firma_id))
    firma = firma_result.scalar_one_or_none()

    # Cargar hallazgos (solo los no descartados)
    hallazgos_result = await db.execute(
        select(Hallazgo).where(
            Hallazgo.auditoria_id == auditoria.id,
            Hallazgo.firma_id == auditoria.firma_id,
            Hallazgo.estado != "descartado",
        ).order_by(Hallazgo.nivel_riesgo, Hallazgo.impuesto_omitido.desc())
    )
    hallazgos = hallazgos_result.scalars().all()

    import json as _json
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
            "impuestos": _json.loads(auditoria.impuestos),
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
        "token_expira": portal_data["portal_expira"],
    }
