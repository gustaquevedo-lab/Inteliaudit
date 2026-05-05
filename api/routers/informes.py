"""
Endpoints de generación y descarga de informes Word/PDF.
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from db.base import get_db
from db import db as crud
from db.models import Firma, Hallazgo, Informe, Usuario
from api.routers.auth import get_current_user

router = APIRouter(prefix="/auditorias/{auditoria_id}/informes", tags=["informes"])


class InformeConfig(BaseModel):
    notas_auditor: Optional[str] = None
    incluir_descartados: bool = False


# ============================================================
#  Helpers
# ============================================================

def _serializar_hallazgo(h: Hallazgo) -> dict:
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
        "notas_auditor": h.notas_auditor,
    }


async def _get_hallazgos_filtrados(
    db: AsyncSession, auditoria_id: str, firma_id: str, incluir_descartados: bool
) -> list[Hallazgo]:
    q = select(Hallazgo).where(
        Hallazgo.auditoria_id == auditoria_id,
        Hallazgo.firma_id == firma_id,
    )
    if not incluir_descartados:
        q = q.where(Hallazgo.estado != "descartado")
    q = q.order_by(Hallazgo.impuesto_omitido.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


# ============================================================
#  Endpoints
# ============================================================

@router.get("")
async def listar_informes(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista informes generados para la auditoría."""
    result = await db.execute(
        select(Informe).where(
            Informe.auditoria_id == auditoria_id,
            Informe.firma_id == user.firma_id,
        ).order_by(Informe.generado_en.desc())
    )
    informes = result.scalars().all()
    return [
        {
            "id": i.id,
            "tipo": i.tipo,
            "version": i.version,
            "estado": i.estado,
            "archivo_docx": i.archivo_docx,
            "archivo_pdf": i.archivo_pdf,
            "generado_en": i.generado_en.isoformat() if i.generado_en else None,
        }
        for i in informes
    ]


@router.post("/word")
async def generar_word(
    auditoria_id: str,
    config: InformeConfig = InformeConfig(),
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Genera el informe de auditoría profesional en Word (.docx)."""
    from informes.word_profesional import generar_informe_word

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    firma_result = await db.execute(select(Firma).where(Firma.id == user.firma_id))
    firma = firma_result.scalar_one_or_none()

    hallazgos_db = await _get_hallazgos_filtrados(db, auditoria_id, user.firma_id, config.incluir_descartados)
    hallazgos = [_serializar_hallazgo(h) for h in hallazgos_db]

    auditoria_dict = {
        "id": auditoria.id,
        "periodo_desde": auditoria.periodo_desde,
        "periodo_hasta": auditoria.periodo_hasta,
        "impuestos": json.loads(auditoria.impuestos),
        "auditor": auditoria.auditor,
        "materialidad": auditoria.materialidad,
    }
    cliente_dict = {
        "ruc": cliente.ruc,
        "razon_social": cliente.razon_social,
        "nombre_fantasia": cliente.nombre_fantasia,
        "actividad_principal": cliente.actividad_principal,
        "regimen": cliente.regimen,
        "direccion": cliente.direccion,
    }

    logo_cliente = None
    logo_dir = Path(settings.storage_path) / user.firma_id / auditoria.cliente_id / auditoria_id / "logo_cliente"
    if logo_dir.exists():
        logos = list(logo_dir.iterdir())
        if logos:
            logo_cliente = logos[0]

    logo_firma = Path(firma.logo_path) if firma and firma.logo_path else None

    contenido = generar_informe_word(
        auditoria=auditoria_dict,
        cliente=cliente_dict,
        hallazgos=hallazgos,
        logo_cliente_path=logo_cliente,
        logo_inteliaudit_path=logo_firma,
        notas_auditor=config.notas_auditor,
    )

    output_dir = Path(settings.storage_path) / user.firma_id / auditoria.cliente_id / auditoria_id / "informes"
    output_dir.mkdir(parents=True, exist_ok=True)
    nombre = f"informe_{cliente.ruc}_{auditoria.periodo_desde}_{auditoria.periodo_hasta}.docx"
    ruta = output_dir / nombre
    ruta.write_bytes(contenido)

    informe = Informe(
        firma_id=user.firma_id,
        auditoria_id=auditoria_id,
        tipo="auditoria_impositiva",
        archivo_docx=str(ruta),
    )
    db.add(informe)
    await crud.log_trail(
        db,
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion="Informe Word generado",
        modulo="informes",
        auditoria_id=auditoria_id,
        datos={"archivo": nombre},
    )

    return FileResponse(
        path=str(ruta),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=nombre,
    )


@router.post("/pdf")
async def generar_pdf(
    auditoria_id: str,
    config: InformeConfig = InformeConfig(),
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Genera el informe en PDF vía WeasyPrint."""
    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    hallazgos_db = await _get_hallazgos_filtrados(db, auditoria_id, user.firma_id, config.incluir_descartados)
    hallazgos = [_serializar_hallazgo(h) for h in hallazgos_db]

    auditoria_dict = {
        "id": auditoria.id,
        "periodo_desde": auditoria.periodo_desde,
        "periodo_hasta": auditoria.periodo_hasta,
        "impuestos": json.loads(auditoria.impuestos),
        "auditor": auditoria.auditor,
        "materialidad": auditoria.materialidad,
    }
    cliente_dict = {
        "ruc": cliente.ruc,
        "razon_social": cliente.razon_social,
        "nombre_fantasia": cliente.nombre_fantasia,
        "actividad_principal": cliente.actividad_principal,
        "regimen": cliente.regimen,
        "direccion": cliente.direccion,
    }

    output_dir = Path(settings.storage_path) / user.firma_id / auditoria.cliente_id / auditoria_id / "informes"
    output_dir.mkdir(parents=True, exist_ok=True)
    nombre = f"informe_{cliente.ruc}_{auditoria.periodo_desde}_{auditoria.periodo_hasta}.pdf"
    ruta_pdf = output_dir / nombre

    try:
        from informes.pdf_profesional import generar_informe_pdf
        contenido = generar_informe_pdf(
            auditoria=auditoria_dict,
            cliente=cliente_dict,
            hallazgos=hallazgos,
            notas_auditor=config.notas_auditor,
        )
        ruta_pdf.write_bytes(contenido)
    except ImportError:
        raise HTTPException(501, "Módulo PDF no disponible. Instalá WeasyPrint o usá el informe Word.")

    informe = Informe(
        firma_id=user.firma_id,
        auditoria_id=auditoria_id,
        tipo="auditoria_impositiva",
        archivo_pdf=str(ruta_pdf),
    )
    db.add(informe)
    await crud.log_trail(
        db,
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion="Informe PDF generado",
        modulo="informes",
        auditoria_id=auditoria_id,
        datos={"archivo": nombre},
    )

    return FileResponse(
        path=str(ruta_pdf),
        media_type="application/pdf",
        filename=nombre,
    )
