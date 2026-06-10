"""
Endpoints de importacion manual de archivos (RG90, HECHAUKA, DJ).
El auditor descarga archivos de Marangatu y los sube a la plataforma.
"""
import json
import re
from pathlib import Path
from typing import Optional

import pdfplumber
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from db.base import get_db
from db import db as crud
from db.models import Usuario
from api.routers.auth import get_current_user
from ingesta.parser_rg90 import parsear_rg90

router = APIRouter(prefix="/auditorias/{auditoria_id}/importar", tags=["importacion"])


@router.post("/rg90")
async def importar_rg90(
    auditoria_id: str,
    tipo: str = Form(..., description="'compras' o 'ventas'"),
    periodo: str = Form(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    archivo: UploadFile = File(...),
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Importa archivo XLSX de RG90 (compras o ventas) y parsea sus registros."""
    if tipo not in ("compras", "ventas"):
        raise HTTPException(400, "tipo debe ser 'compras' o 'ventas'")

    if not archivo.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "El archivo debe ser XLSX")

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    ruta = await _guardar_archivo(user.firma_id, auditoria_id, "rg90", archivo)

    registros = parsear_rg90(ruta, cliente.id, periodo, auditoria_id)
    if not registros:
        raise HTTPException(400, "No se pudo parsear el archivo. Verificá que la estructura de columnas coincida con el formato RG90.")

    preview = _generar_preview(registros)

    return {
        "ok": True,
        "preview": preview,
        "total_registros": len(registros),
        "total_monto": sum(r.get("total_comprobante", 0) for r in registros),
        "total_iva": sum(r.get("iva_total", 0) for r in registros),
        "periodo": periodo,
        "tipo": tipo,
        "archivo": archivo.filename,
        "requiere_confirmacion": True,
    }


@router.post("/rg90/confirmar")
async def confirmar_importacion_rg90(
    auditoria_id: str,
    periodo: str = Form(...),
    tipo: str = Form(...),
    archivo_nombre: str = Form(...),
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirma la importacion de registros RG90 previamente parseados."""
    ruta = Path(settings.storage_path) / user.firma_id / auditoria_id / "rg90" / archivo_nombre
    if not ruta.exists():
        raise HTTPException(404, "Archivo no encontrado. Debe importarlo primero.")

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    registros = parsear_rg90(ruta, cliente.id, periodo, auditoria_id)
    n = await crud.guardar_rg90_batch(db, user.firma_id, registros)

    await crud.log_trail(
        db, firma_id=user.firma_id, usuario_id=user.id,
        accion=f"RG90 importado: {n} registros ({tipo}, {periodo})",
        modulo="importacion", auditoria_id=auditoria_id,
        datos={"archivo": archivo_nombre, "periodo": periodo, "tipo": tipo, "registros": n},
    )
    await db.commit()

    return {
        "ok": True,
        "registros_importados": n,
        "periodo": periodo,
        "tipo": tipo,
    }


@router.post("/hechauka")
async def importar_hechauka(
    auditoria_id: str,
    periodo: str = Form(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    archivo: UploadFile = File(...),
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Importa archivo XLSX de HECHAUKA y parsea sus registros."""
    if not archivo.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(400, "El archivo debe ser XLSX")

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    ruta = await _guardar_archivo(user.firma_id, auditoria_id, "hechauka", archivo)

    from ingesta.parser_hechauka import parsear_hechauka
    registros = parsear_hechauka(ruta, cliente.id, periodo, auditoria_id)
    if not registros:
        raise HTTPException(400, "No se pudo parsear el archivo HECHAUKA.")

    preview = _generar_preview(registros)

    return {
        "ok": True,
        "preview": preview,
        "total_registros": len(registros),
        "total_monto": sum(r.get("monto_operacion", 0) for r in registros),
        "total_iva": sum(r.get("iva_operacion", 0) for r in registros),
        "periodo": periodo,
        "archivo": archivo.filename,
        "requiere_confirmacion": True,
    }


@router.post("/hechauka/confirmar")
async def confirmar_importacion_hechauka(
    auditoria_id: str,
    periodo: str = Form(...),
    archivo_nombre: str = Form(...),
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirma la importacion de registros HECHAUKA previamente parseados."""
    ruta = Path(settings.storage_path) / user.firma_id / auditoria_id / "hechauka" / archivo_nombre
    if not ruta.exists():
        raise HTTPException(404, "Archivo no encontrado. Debe importarlo primero.")

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    from ingesta.parser_hechauka import parsear_hechauka
    registros = parsear_hechauka(ruta, cliente.id, periodo, auditoria_id)
    n = await crud.guardar_hechauka_batch(db, user.firma_id, registros)

    await crud.log_trail(
        db, firma_id=user.firma_id, usuario_id=user.id,
        accion=f"HECHAUKA importado: {n} registros ({periodo})",
        modulo="importacion", auditoria_id=auditoria_id,
        datos={"archivo": archivo_nombre, "periodo": periodo, "registros": n},
    )
    await db.commit()

    return {
        "ok": True,
        "registros_importados": n,
        "periodo": periodo,
    }


@router.post("/dj")
async def importar_declaracion_jurada(
    auditoria_id: str,
    formulario: str = Form(..., description="120, 500, 800, 810, 820, 830"),
    periodo: str = Form(..., pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    archivo: UploadFile = File(...),
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Importa PDF de declaracion jurada y extrae campos clave."""
    formularios_validos = {"120", "500", "800", "810", "820", "830"}
    if formulario not in formularios_validos:
        raise HTTPException(400, f"Formulario invalido. Opciones: {formularios_validos}")

    if not archivo.filename.endswith(".pdf"):
        raise HTTPException(400, "El archivo debe ser PDF")

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    ruta = await _guardar_archivo(user.firma_id, auditoria_id, "dj", archivo)

    texto, campos = _parsear_pdf_dj(ruta, formulario)

    # Guardar declaracion automaticamente
    decl = await crud.guardar_declaracion(
        db,
        firma_id=user.firma_id,
        cliente_id=cliente.id,
        formulario=formulario,
        periodo=periodo,
        fecha_presentacion=campos.get("fecha_presentacion", periodo + "-20"),
        estado_declaracion=campos.get("estado", "original"),
        datos_json=campos,
        auditoria_id=auditoria_id,
        nro_rectificativa=int(campos.get("nro_rectificativa", 0)),
        archivo_pdf=str(ruta),
    )

    await crud.log_trail(
        db, firma_id=user.firma_id, usuario_id=user.id,
        accion=f"DJ Form.{formulario} importada ({periodo})",
        modulo="importacion", auditoria_id=auditoria_id,
        datos={"formulario": formulario, "periodo": periodo, "campos": campos},
    )
    await db.commit()

    return {
        "ok": True,
        "formulario": formulario,
        "periodo": periodo,
        "campos_extraidos": campos,
        "declaracion_id": decl.id,
        "confirmada": True,
    }


def _generar_preview(registros: list[dict]) -> dict:
    """Genera preview de hasta 10 registros con columnas relevantes."""
    preview = registros[:10]
    columnas_omitir = {"auditoria_id", "cliente_id", "fuente_archivo"}
    return [
        {k: v for k, v in r.items() if k not in columnas_omitir}
        for r in preview
    ]


def _parsear_pdf_dj(ruta: Path, formulario: str) -> tuple[str, dict]:
    """Parsea PDF de declaracion jurada y extrae campos segun formulario."""
    texto = ""
    campos: dict = {"fecha_presentacion": None, "estado": "original", "nro_rectificativa": 0}

    try:
        with pdfplumber.open(ruta) as pdf:
            for page in pdf.pages:
                texto += page.extract_text() + "\n"
    except Exception:
        raise HTTPException(400, "No se pudo leer el archivo PDF. Verificá que sea un PDF valido.")

    m = re.search(r"(\d{2}/\d{2}/\d{4})", texto)
    if m:
        campos["fecha_presentacion"] = m.group(1)

    m = re.search(r"Rectificativa[:\s]*(\d+)", texto, re.IGNORECASE)
    if m:
        campos["nro_rectificativa"] = int(m.group(1))
        campos["estado"] = "rectificativa"

    if formulario == "120":
        campos["credito_fiscal"] = _extraer_monto(texto, r"(?:credito\s*fiscal|total\s*credito)[:\s]*([\d.,]+)")
        campos["debito_fiscal"] = _extraer_monto(texto, r"(?:debito\s*fiscal|total\s*debito)[:\s]*([\d.,]+)")
        campos["saldo_a_favor"] = _extraer_monto(texto, r"(?:saldo\s*a\s*favor)[:\s]*([\d.,]+)")

    elif formulario == "500":
        campos["ingresos_brutos"] = _extraer_monto(texto, r"(?:ingresos?\s*brutos?|total\s*ingresos)[:\s]*([\d.,]+)")
        campos["renta_neta"] = _extraer_monto(texto, r"(?:renta\s*neta|resultado\s*fiscal)[:\s]*([\d.,]+)")
        campos["impuesto_determinado"] = _extraer_monto(texto, r"(?:impuesto\s*determinado|impuesto\s*resultante)[:\s]*([\d.,]+)")

    return texto, campos


def _extraer_monto(texto: str, patron: str) -> int:
    m = re.search(patron, texto, re.IGNORECASE | re.MULTILINE)
    if m:
        try:
            return int(re.sub(r"[^\d]", "", m.group(1)))
        except (ValueError, IndexError):
            pass
    return 0


async def _guardar_archivo(firma_id: str, auditoria_id: str, tipo: str, archivo: UploadFile) -> Path:
    """Guarda archivo en storage con estructura tenant/auditoria/tipo."""
    directorio = Path(settings.storage_path) / firma_id / auditoria_id / tipo
    directorio.mkdir(parents=True, exist_ok=True)
    destino = directorio / archivo.filename
    contenido = await archivo.read()
    destino.write_bytes(contenido)
    await archivo.seek(0)
    return destino
