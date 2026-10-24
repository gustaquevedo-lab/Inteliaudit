"""
Validador algorítmico oficial de Código de Control (CDC) de SIFEN (e-Kuatia).
Basado en el Manual Técnico de Facturación Electrónica de la DNIT (Paraguay).
Aplica cálculo de Dígito Verificador Módulo 11 y extracción de metadatos del CDC (44 dígitos).
"""
from typing import Dict, Any, Optional

TIPOS_DOCUMENTO_SIFEN: Dict[str, str] = {
    "01": "Factura electrónica",
    "04": "Autofactura electrónica",
    "05": "Nota de crédito electrónica",
    "06": "Nota de débito electrónica",
    "07": "Nota de remisión electrónica",
    "08": "Comprobante de retención electrónico",
}

TIPOS_EMISION: Dict[str, str] = {
    "1": "Normal",
    "2": "Contingencia",
}


def calcular_dv_modulo11(cadena_43: str) -> int:
    """
    Calcula el dígito verificador del CDC según el algoritmo oficial DNIT:
    Módulo 11 con base 11 (factores ponderados del 2 al 11 de derecha a izquierda).
    Si el resto es 0 o 1 -> DV = 0.
    En cualquier otro caso -> DV = 11 - resto.
    """
    if not cadena_43 or not cadena_43.isdigit():
        raise ValueError("La cadena para cálculo de DV debe ser puramente numérica")

    suma = 0
    factor = 2
    for digito in reversed(cadena_43):
        suma += int(digito) * factor
        factor += 1
        if factor > 11:
            factor = 2

    resto = suma % 11
    if resto <= 1:
        return 0
    return 11 - resto


def validar_formato_cdc(cdc: str) -> Dict[str, Any]:
    """
    Valida la longitud, estructura y dígito verificador de un CDC de 44 dígitos.
    Si es válido, extrae y formatea todos los metadatos fiscales contenidos.
    """
    if not cdc:
        return {"valido": False, "error": "El CDC no puede estar vacío"}

    cdc_limpio = cdc.strip()
    if len(cdc_limpio) != 44:
        return {
            "valido": False,
            "cdc": cdc_limpio,
            "error": f"El CDC debe tener exactamente 44 dígitos (recibidos: {len(cdc_limpio)})"
        }

    if not cdc_limpio.isdigit():
        return {
            "valido": False,
            "cdc": cdc_limpio,
            "error": "El CDC debe contener únicamente caracteres numéricos"
        }

    cadena_base = cdc_limpio[:43]
    dv_informado = int(cdc_limpio[43])
    dv_esperado = calcular_dv_modulo11(cadena_base)

    tipo_doc_cod = cdc_limpio[0:2]
    ruc_num = cdc_limpio[2:10].lstrip("0") or "0"
    ruc_dv = cdc_limpio[10:11]
    ruc_emisor = f"{ruc_num}-{ruc_dv}"

    est = cdc_limpio[12:15]
    punto_exp = cdc_limpio[15:18]
    num_doc = cdc_limpio[18:25]
    comprobante_formato = f"{est}-{punto_exp}-{num_doc}"

    tipo_emision = cdc_limpio[25:26]
    fecha_raw = cdc_limpio[26:34]
    fecha_emision_str = f"{fecha_raw[0:4]}-{fecha_raw[4:6]}-{fecha_raw[6:8]}"

    if dv_informado != dv_esperado:
        return {
            "valido": False,
            "cdc": cdc_limpio,
            "error": f"Dígito verificador inválido (esperado: {dv_esperado}, informado: {dv_informado})",
            "dv_esperado": dv_esperado,
            "dv_informado": dv_informado,
            "ruc_emisor": ruc_emisor,
            "comprobante_formato": comprobante_formato,
        }

    return {
        "valido": True,
        "cdc": cdc_limpio,
        "tipo_documento_codigo": tipo_doc_cod,
        "tipo_documento_desc": TIPOS_DOCUMENTO_SIFEN.get(tipo_doc_cod, "Desconocido"),
        "ruc_emisor": ruc_emisor,
        "tipo_contribuyente": cdc_limpio[11:12],
        "establecimiento": est,
        "punto_expedicion": punto_exp,
        "numero_documento": num_doc,
        "comprobante_formato": comprobante_formato,
        "tipo_emision_codigo": tipo_emision,
        "tipo_emision_desc": TIPOS_EMISION.get(tipo_emision, "Normal"),
        "fecha_emision_str": fecha_emision_str,
        "tipo_regimen": cdc_limpio[34:35],
        "codigo_seguridad": cdc_limpio[35:43],
        "dv_esperado": dv_esperado,
        "dv_informado": dv_informado,
    }
