"""
Endpoints de upload de archivos — insumos del auditor y datos DNIT.
"""
import shutil
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from db.base import get_db
from db import db as crud
from db.models import Usuario
from api.routers.auth import get_current_user
from ingesta.parser_rg90 import parsear_rg90

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
    periodo: Optional[str] = Form(None, description="YYYY-MM — requerido para rg90 y hechauka"),
    archivo: UploadFile = File(...),
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sube un archivo de insumo a la auditoría con aislamiento multi-tenant."""
    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
         raise HTTPException(404, "Cliente no encontrado")

    _validar_extension(archivo.filename, tipo)
    await _validar_tamaño(archivo)

    ruta = await _guardar_archivo(user.firma_id, auditoria.cliente_id, auditoria_id, tipo, archivo)
    resultado = {"archivo": archivo.filename, "tipo": tipo, "ruta": str(ruta)}

    # Procesar automáticamente según el tipo
    if tipo == "rg90":
        if not periodo:
            raise HTTPException(400, "El campo 'periodo' es requerido para archivos RG90 (formato YYYY-MM)")
        
        registros = parsear_rg90(ruta, cliente.id, periodo, auditoria_id)
        n = await crud.guardar_rg90_batch(db, user.firma_id, registros)
        
        await crud.log_trail(
            db, 
            firma_id=user.firma_id,
            usuario_id=user.id,
            accion=f"RG90 importado: {n} comprobantes", 
            modulo="ingesta", 
            auditoria_id=auditoria_id, 
            datos={"archivo": archivo.filename, "periodo": periodo, "registros": n}
        )
        resultado["procesado"] = True
        resultado["registros_importados"] = n

    elif tipo == "hechauka":
        if not periodo:
            raise HTTPException(400, "El campo 'periodo' es requerido para archivos HECHAUKA (formato YYYY-MM)")
        
        from ingesta.parser_hechauka import parsear_hechauka
        try:
            registros = parsear_hechauka(ruta, cliente.id, periodo, auditoria_id)
            n = await crud.guardar_hechauka_batch(db, user.firma_id, registros)
            resultado["procesado"] = True
            resultado["registros_importados"] = n
        except Exception as e:
            resultado["procesado"] = False
            resultado["error"] = str(e)

    else:
        await crud.log_trail(
            db, 
            firma_id=user.firma_id,
            usuario_id=user.id,
            accion=f"Archivo subido: {archivo.filename}", 
            modulo="ingesta", 
            auditoria_id=auditoria_id, 
            datos={"tipo": tipo, "ruta": str(ruta)}
        )
        resultado["procesado"] = False

    return resultado


@router.get("")
async def listar_archivos(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista los archivos subidos a una auditoría."""
    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    base = Path(settings.storage_path) / user.firma_id / auditoria.cliente_id / auditoria_id
    if not base.exists():
        return []

    archivos = []
    for tipo_dir in base.iterdir():
        if tipo_dir.is_dir():
            for f in tipo_dir.iterdir():
                if f.is_file():
                    archivos.append({
                        "tipo": tipo_dir.name,
                        "nombre": f.name,
                        "tamaño_kb": round(f.stat().st_size / 1024, 1),
                        "ruta": str(f.relative_to(Path(settings.storage_path))),
                    })
    return sorted(archivos, key=lambda x: x["tipo"])


# ============================================================
#  Helpers
# ============================================================

def _validar_extension(filename: str, tipo: str) -> None:
    ext = Path(filename).suffix.lower()
    permitidos = TIPOS_PERMITIDOS.get(tipo, [])
    if ext not in permitidos:
        raise HTTPException(400, f"Extensión '{ext}' no permitida para tipo '{tipo}'. Permitidos: {permitidos}")


async def _validar_tamaño(archivo: UploadFile) -> None:
    contenido = await archivo.read()
    if len(contenido) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(413, f"Archivo demasiado grande. Máximo {MAX_SIZE_MB}MB.")
    await archivo.seek(0)


async def _guardar_archivo(firma_id: str, cliente_id: str, auditoria_id: str, tipo: str, archivo: UploadFile) -> Path:
    directorio = Path(settings.storage_path) / firma_id / cliente_id / auditoria_id / tipo
    directorio.mkdir(parents=True, exist_ok=True)
    destino = directorio / archivo.filename
    with open(destino, "wb") as f:
        shutil.copyfileobj(archivo.file, f)
    return destino
