"""
Endpoints de upload de archivos — usando StorageAdapter (local o R2).
"""
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from db.base import get_db
from db import db as crud
from db.models import Usuario
from api.routers.auth import get_current_user
from ingesta.parser_rg90 import parsear_rg90
from storage.adapter import get_storage

router = APIRouter(prefix="/auditorias/{auditoria_id}/archivos", tags=["archivos"])

TIPOS_PERMITIDOS = {
    "rg90":              [".xlsx", ".xls"],
    "hechauka":          [".xlsx", ".xls"],
    "estado_cuenta":     [".pdf"],
    "estados_contables": [".xlsx", ".xls", ".csv"],
    "banco":             [".xlsx", ".xls", ".csv", ".pdf"],
    "logo_cliente":      [".png", ".jpg", ".jpeg", ".svg"],
    "comprobante":       [".pdf", ".xml", ".jpg", ".jpeg", ".png"],
    "otro":              [".pdf", ".xlsx", ".xls", ".docx", ".png", ".jpg"],
}

MAX_SIZE_MB = 20


@router.post("")
async def subir_archivo(
    auditoria_id: str,
    tipo: Literal["rg90", "hechauka", "estado_cuenta", "estados_contables", "banco", "logo_cliente", "comprobante", "otro"] = Form(...),
    periodo: Optional[str] = Form(None, description="YYYY-MM requerido para rg90 y hechauka"),
    archivo: UploadFile = File(...),
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoria no encontrada")
    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    _validar_extension(archivo.filename, tipo)
    contenido = await archivo.read()
    if len(contenido) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"Archivo demasiado grande. Maximo {MAX_SIZE_MB}MB.")

    key = f"{user.firma_id}/{auditoria.cliente_id}/{auditoria_id}/{tipo}/{archivo.filename}"
    storage = get_storage()
    url = await storage.upload(key, contenido, archivo.content_type or "application/octet-stream")

    resultado = {"archivo": archivo.filename, "tipo": tipo, "ruta": url}

    if tipo == "rg90":
        if not periodo:
            raise HTTPException(400, "Periodo requerido para RG90 (YYYY-MM)")
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(contenido)
            tmp_path = tmp.name
        registros = parsear_rg90(tmp_path, cliente.id, periodo, auditoria_id)
        import os
        os.unlink(tmp_path)
        n = await crud.guardar_rg90_batch(db, user.firma_id, registros)
        await crud.log_trail(db, firma_id=user.firma_id, usuario_id=user.id, accion=f"RG90 importado: {n} comprobantes", modulo="ingesta", auditoria_id=auditoria_id, datos={"archivo": archivo.filename, "periodo": periodo, "registros": n})
        resultado["procesado"] = True
        resultado["registros_importados"] = n

    elif tipo == "hechauka":
        if not periodo:
            raise HTTPException(400, "Periodo requerido para HECHAUKA (YYYY-MM)")
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp.write(contenido)
            tmp_path = tmp.name
        from ingesta.parser_hechauka import parsear_hechauka
        try:
            registros = parsear_hechauka(tmp_path, cliente.id, periodo, auditoria_id)
            n = await crud.guardar_hechauka_batch(db, user.firma_id, registros)
            resultado["procesado"] = True
            resultado["registros_importados"] = n
        except Exception as e:
            resultado["procesado"] = False
            resultado["error"] = str(e)
        os.unlink(tmp_path)

    return resultado


@router.get("")
async def listar_archivos(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista archivos subidos (soporta solo LocalStorage por ahora)."""
    from pathlib import Path
    base = Path(settings.storage_path) / user.firma_id / auditoria_id
    if not base.exists():
        return []
    archivos = []
    for tipo_dir in base.iterdir():
        if tipo_dir.is_dir():
            for f in tipo_dir.iterdir():
                if f.is_file():
                    archivos.append({"tipo": tipo_dir.name, "nombre": f.name, "tamano_kb": round(f.stat().st_size / 1024, 1)})
    return sorted(archivos, key=lambda x: x["tipo"])


def _validar_extension(filename: str, tipo: str) -> None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    permitidos = [e.replace(".", "") for e in TIPOS_PERMITIDOS.get(tipo, [])]
    if ext not in permitidos:
        raise HTTPException(400, f"Extension '{ext}' no permitida para tipo '{tipo}'")
