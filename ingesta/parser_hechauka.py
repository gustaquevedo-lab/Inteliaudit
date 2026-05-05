"""
Parser del archivo XLSX de HECHAUKA (información de terceros desde Marangatú).

HECHAUKA es el sistema en que los agentes de retención y grandes contribuyentes
informan sus operaciones con terceros. El contribuyente auditado puede descargar
"HECHAUKA Recibido" — lo que terceros declararon sobre él.

Columnas típicas del XLSX (pueden variar según período):
- RUC Informante
- Razón Social Informante
- Tipo Operación (compra/venta/retención)
- Período (YYYY-MM)
- Número Comprobante
- Fecha
- Monto Total
- Monto IVA
- Retención IVA
- Retención IRE
"""
from pathlib import Path
from typing import Union
import re

import openpyxl


# Mapeo flexible de nombres de columnas HECHAUKA → clave interna
_COL_MAP = {
    # RUC del informante (quien declaró)
    "ruc informante": "ruc_informante",
    "ruc del informante": "ruc_informante",
    "ruc": "ruc_informante",

    # Tipo de operación
    "tipo operacion": "tipo_operacion",
    "tipo de operacion": "tipo_operacion",
    "tipo": "tipo_operacion",

    # Período
    "periodo": "periodo",
    "período": "periodo",
    "mes": "periodo",

    # Nro comprobante
    "numero comprobante": "nro_comprobante",
    "número comprobante": "nro_comprobante",
    "nro comprobante": "nro_comprobante",
    "comprobante": "nro_comprobante",

    # Fecha
    "fecha": "fecha",
    "fecha comprobante": "fecha",
    "fecha emision": "fecha",
    "fecha emisión": "fecha",

    # Montos
    "monto total": "monto",
    "total": "monto",
    "monto": "monto",
    "importe": "monto",

    # IVA
    "iva": "iva",
    "monto iva": "iva",
    "importe iva": "iva",

    # Retenciones
    "retencion iva": "retencion_iva",
    "retención iva": "retencion_iva",
    "ret iva": "retencion_iva",
    "retencion ire": "retencion_ire",
    "retención ire": "retencion_ire",
    "ret ire": "retencion_ire",
    "retencion": "retencion",  # genérica si no especifica impuesto
}


def _normalizar_col(nombre: str) -> str:
    return re.sub(r"\s+", " ", str(nombre).strip().lower())


def _parse_monto(val) -> int:
    if val is None:
        return 0
    try:
        return int(round(float(str(val).replace(",", "").replace(".", "").strip())))
    except (ValueError, TypeError):
        return 0


def _parse_fecha(val) -> str:
    if val is None:
        return ""
    from datetime import datetime, date
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s


def parsear_hechauka(
    archivo: Union[str, Path],
    cliente_id: str,
    periodo: str,
    auditoria_id: str,
) -> list[dict]:
    """
    Parsea un XLSX de HECHAUKA Recibido y devuelve lista de dicts
    listos para insertar en la tabla `hechauka`.

    Args:
        archivo: Ruta al XLSX descargado de Marangatú.
        cliente_id: UUID del contribuyente auditado.
        periodo: Período declarado en el formulario de descarga (YYYY-MM).
        auditoria_id: UUID de la auditoría activa.

    Returns:
        Lista de dicts con claves:
            cliente_id, auditoria_id, periodo, ruc_informante,
            tipo_operacion, nro_comprobante, fecha_comprobante, monto_operacion,
            iva_operacion, retencion_iva, retencion_ire
    """
    wb = openpyxl.load_workbook(str(archivo), data_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    # Detectar fila de encabezado (primera fila no vacía)
    header_row_idx = 0
    for i, row in enumerate(rows):
        if any(c is not None for c in row):
            header_row_idx = i
            break

    headers = [_normalizar_col(c) for c in rows[header_row_idx]]
    col_map: dict[int, str] = {}
    for idx, h in enumerate(headers):
        if h in _COL_MAP:
            col_map[idx] = _COL_MAP[h]

    registros = []
    for row in rows[header_row_idx + 1:]:
        if all(c is None for c in row):
            continue

        r: dict = {
            "cliente_id": cliente_id,
            "auditoria_id": auditoria_id,
            "periodo": periodo,
            "ruc_informante": "",
            "nombre_informante": "",
            "tipo_operacion": "operacion",
            "nro_comprobante": None,
            "fecha_comprobante": None,
            "monto_operacion": 0,
            "iva_operacion": 0,
            "retencion_iva": 0,
            "retencion_ire": 0,
        }

        for idx, key in col_map.items():
            val = row[idx] if idx < len(row) else None
            if key in ("monto", "iva", "retencion_iva", "retencion_ire", "retencion"):
                parsed = _parse_monto(val)
                if key == "monto":
                    r["monto_operacion"] = parsed
                elif key == "iva":
                    r["iva_operacion"] = parsed
                elif key == "retencion":
                    r["retencion_iva"] += parsed
                else:
                    r[key] = parsed
            elif key == "fecha":
                r["fecha_comprobante"] = _parse_fecha(val) or None
            elif key == "nro_comprobante":
                r["nro_comprobante"] = str(val).strip() if val else None
            elif key == "tipo_operacion":
                r["tipo_operacion"] = str(val).strip() if val else "operacion"
            else:
                r[key] = str(val).strip() if val is not None else ""

        # Limpiar RUC informante
        r["ruc_informante"] = re.sub(r"[^0-9\-]", "", r["ruc_informante"])

        # Sólo incluir si hay RUC informante o monto > 0
        if r["ruc_informante"] or r["monto_operacion"] > 0:
            registros.append(r)

    return registros
