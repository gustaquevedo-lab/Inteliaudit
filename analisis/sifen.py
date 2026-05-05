"""
Módulo de validación para el Sistema Integrado de Facturación Electrónica Nacional (SIFEN).
Basado en las especificaciones técnicas de la DNIT (E-Kuatia).
"""
import re
from typing import Dict, Optional

def validar_cdc(cdc: str) -> Dict[str, any]:
    """
    Valida un Código de Control (CDC) de 44 dígitos.
    
    Estructura del CDC:
    - Tipo Documento (2)
    - RUC Emisor (8)
    - DV RUC (1)
    - Establecimiento (3)
    - Punto Expedición (3)
    - Número Comprobante (7)
    - Tipo Emisión (1)
    - Fecha Emisión (8 - AAAAMMDD)
    - Código Seguridad (9)
    - DV CDC (1)
    """
    cdc = re.sub(r"\D", "", cdc)
    
    if len(cdc) != 44:
        return {"valido": False, "error": "Longitud incorrecta (deben ser 44 dígitos)"}

    # 1. Validar dígito verificador del CDC (Módulo 11)
    dv_calculado = calcular_dv_11(cdc[:-1])
    dv_real = int(cdc[-1])
    
    if dv_calculado != dv_real:
        return {"valido": False, "error": "Dígito verificador (DV) inválido"}

    # 2. Desglosar datos para análisis
    data = {
        "valido": True,
        "tipo_documento": cdc[0:2],
        "ruc_emisor": f"{int(cdc[2:10])}-{cdc[10:11]}",
        "establecimiento": cdc[11:14],
        "punto_expedicion": cdc[14:17],
        "numero": cdc[17:24],
        "tipo_emision": "Electrónica" if cdc[24:25] == "1" else "Pre-impresa",
        "fecha_emision": f"{cdc[25:29]}-{cdc[29:31]}-{cdc[31:33]}",
    }
    
    return data

def calcular_dv_11(p_numero: str) -> int:
    """
    Calcula el dígito verificador Módulo 11 según algoritmo de la SET.
    """
    v_total = 0
    v_resto = 0
    v_digit = 0
    v_count = 2
    
    # Recorrer de derecha a izquierda
    for i in range(len(p_numero) - 1, -1, -1):
        v_total += int(p_numero[i]) * v_count
        v_count += 1
        if v_count > 11:
            v_count = 2
            
    v_resto = v_total % 11
    if v_resto > 1:
        v_digit = 11 - v_resto
    else:
        v_digit = 0
        
    return v_digit

def analizar_coherencia_rg90_vs_sifen(registro_rg90: Dict, cdc_data: Dict) -> Dict:
    """
    Compara los datos declarados en el RG90 contra lo codificado en el CDC.
    Detecta discrepancias que podrían indicar manipulación o error de carga.
    """
    discrepancias = []
    
    if registro_rg90.get("ruc_contraparte") != cdc_data["ruc_emisor"].split("-")[0]:
        discrepancias.append("RUC emisor no coincide con CDC")
        
    if str(registro_rg90.get("nro_comprobante")).replace("-", "") != cdc_data["numero"]:
        discrepancias.append("Número de comprobante no coincide con CDC")
        
    if registro_rg90.get("fecha_emision") != cdc_data["fecha_emision"]:
        discrepancias.append("Fecha de emisión no coincide con CDC")
        
    return {
        "coherente": len(discrepancias) == 0,
        "discrepancias": discrepancias
    }
