"""
Parser de extractos bancarios en formatos XLSX y CSV.
Soporta formatos estándar de bancos de Paraguay (Itaú, Continental, BNF, GNB, Atlas, etc.).
"""
import csv
import io
import re
from pathlib import Path
from typing import Optional, Union

import openpyxl

from analisis.bancario import TransaccionBancaria


def _limpiar_texto(val: Optional[str]) -> str:
    if not val:
        return ""
    return str(val).strip()


def _normalizar_header(val: str) -> str:
    s = str(val).lower().strip()
    s = s.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _parsear_monto_py(val: Union[str, int, float, None]) -> int:
    """Convierte cadenas o números de extracto bancario en entero PYG."""
    if val is None or val == "":
        return 0
    if isinstance(val, (int, float)):
        return int(round(val))

    s = str(val).strip()
    if not s:
        return 0

    es_negativo = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    # Remover símbolos de moneda y caracteres que no sean dígitos ni separadores
    s = re.sub(r"[^\d.,]", "", s)

    if not s:
        return 0

    # Determinar si . o , es separador decimal o de miles
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            # Formato estándar PY/ES: 1.000.000,00
            s = s.replace(".", "").replace(",", ".")
        else:
            # Formato US: 1,000,000.00
            s = s.replace(",", "")
    elif "." in s:
        # Puede ser miles (1.000.000) o decimales (1000.50)
        partes = s.split(".")
        if len(partes) > 2 or len(partes[-1]) == 3:
            s = s.replace(".", "")
    elif "," in s:
        # Puede ser miles (1,000,000) o decimales (1000,50)
        partes = s.split(",")
        if len(partes) > 2 or len(partes[-1]) == 3:
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")

    try:
        num = int(round(float(s)))
        return -num if es_negativo else num
    except (ValueError, TypeError):
        return 0


def _normalizar_fecha_iso(val: Union[str, None]) -> str:
    if not val:
        return ""
    s = str(val).strip()
    if " " in s:
        s = s.split(" ")[0]
    # Detección dd/mm/yyyy o dd-mm-yyyy
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", s)
    if m:
        d, mes, y = m.groups()
        if len(y) == 2:
            y = f"20{y}"
        return f"{y}-{int(mes):02d}-{int(d):02d}"
    # Detección yyyy-mm-dd
    m2 = re.match(r"^(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", s)
    if m2:
        y, mes, d = m2.groups()
        return f"{y}-{int(mes):02d}-{int(d):02d}"
    return s[:10]


def parsear_extracto_bancario(archivo_path: Union[str, Path]) -> list[TransaccionBancaria]:
    """
    Lee un archivo XLSX o CSV y extrae la lista de transacciones bancarias.
    """
    path = Path(archivo_path)
    extension = path.suffix.lower()

    filas_crudas: list[list[str]] = []

    if extension in [".xlsx", ".xls"]:
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        for row in ws.iter_rows(values_only=True):
            if any(cell is not None for cell in row):
                filas_crudas.append([str(c) if c is not None else "" for c in row])
    elif extension == ".csv":
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            sample = f.read(2048)
            f.seek(0)
            delimiter = ";" if ";" in sample and sample.count(";") > sample.count(",") else ","
            reader = csv.reader(f, delimiter=delimiter)
            for row in reader:
                if any(row):
                    filas_crudas.append(row)
    else:
        raise ValueError(f"Formato no soportado: {extension}")

    if not filas_crudas:
        return []

    # Encontrar la fila de cabecera buscando columnas de fecha/concepto
    header_idx = -1
    col_fecha = -1
    col_desc = -1
    col_debito = -1
    col_credito = -1
    col_monto = -1
    col_ref = -1

    for idx, fila in enumerate(filas_crudas[:15]):
        norm_row = [_normalizar_header(c) for c in fila]
        for col_i, h in enumerate(norm_row):
            if any(k in h for k in ["fecha", "date", "fec"]):
                col_fecha = col_i
            elif any(k in h for k in ["concepto", "descripcion", "detalle", "movimiento", "glosa"]):
                col_desc = col_i
            elif any(k in h for k in ["debito", "debitos", "egreso", "salida", "retiro", "cargo"]):
                col_debito = col_i
            elif any(k in h for k in ["credito", "creditos", "ingreso", "entrada", "deposito", "abono"]):
                col_credito = col_i
            elif any(k in h for k in ["monto", "importe", "valor"]):
                col_monto = col_i
            elif any(k in h for k in ["referencia", "comprobante", "nro"]):
                col_ref = col_i

        if col_fecha != -1 and (col_desc != -1 or col_monto != -1 or (col_debito != -1 and col_credito != -1)):
            header_idx = idx
            break

    # Si no se encontró cabecera explícita, asumir columnas estándar: [0: Fecha, 1: Concepto, 2: Débito/Monto, 3: Crédito]
    if header_idx == -1:
        header_idx = 0
        col_fecha = 0
        col_desc = 1 if len(filas_crudas[0]) > 1 else 0
        col_monto = 2 if len(filas_crudas[0]) > 2 else -1

    transacciones: list[TransaccionBancaria] = []

    for fila in filas_crudas[header_idx + 1:]:
        if len(fila) <= col_fecha:
            continue

        raw_fecha = fila[col_fecha].strip()
        fecha = _normalizar_fecha_iso(raw_fecha)
        if not fecha or len(fecha) < 8:
            continue

        desc = fila[col_desc].strip() if col_desc != -1 and len(fila) > col_desc else "Movimiento bancario"
        ref = fila[col_ref].strip() if col_ref != -1 and len(fila) > col_ref else None

        monto = 0
        tipo = "ingreso"

        if col_debito != -1 and col_credito != -1:
            debito_val = _parsear_monto_py(fila[col_debito]) if len(fila) > col_debito else 0
            credito_val = _parsear_monto_py(fila[col_credito]) if len(fila) > col_credito else 0

            if credito_val > 0:
                monto = credito_val
                tipo = "ingreso"
            elif debito_val > 0:
                monto = -debito_val
                tipo = "egreso"
            elif debito_val < 0:
                monto = debito_val
                tipo = "egreso"
            else:
                continue
        elif col_monto != -1 and len(fila) > col_monto:
            monto_val = _parsear_monto_py(fila[col_monto])
            if monto_val == 0:
                continue
            monto = monto_val
            tipo = "ingreso" if monto_val > 0 else "egreso"
        else:
            continue

        transacciones.append(
            TransaccionBancaria(
                fecha=fecha,
                descripcion=desc,
                monto=monto,
                tipo=tipo,
                referencia=ref,
            )
        )

    return transacciones
