"""
Cliente SIFEN con persistencia en caché (sifen_cache).
Verifica comprobantes electrónicos por CDC, validando primero su estructura
matemática con Módulo 11 y consultando a la DNIT solo si es necesario.
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import SifenCache
from ingesta.sifen_validator import validar_formato_cdc

logger = logging.getLogger("sifen_client")

# Endpoint REST oficial / de consulta e-Kuatia
SIFEN_REST_URL = "https://ekuatia.set.gov.py/consultas/rest/api/v1/de/{cdc}"


async def consultar_o_validar_cdc(
    db: AsyncSession,
    cdc: str,
    consultar_online: bool = False,
    timeout: float = 4.0
) -> Dict[str, Any]:
    """
    Consulta un CDC verificando primero la caché local.
    Si no está en caché:
      1. Aplica validación algorítmica Módulo 11 (instantánea).
      2. Si es inválido, persiste en sifen_cache como CDC_INVALIDO.
      3. Si es válido y consultar_online=True, hace una petición HTTP a SIFEN.
      4. Si es válido y offline, persiste como FORMATO_VALIDO.
    """
    cdc_limpio = (cdc or "").strip()
    if not cdc_limpio:
        return {"cdc": "", "es_valido": False, "estado": "CDC_VACIO", "error": "CDC no provisto"}

    # 1. Comprobar caché local
    cached = await db.get(SifenCache, cdc_limpio)
    if cached:
        return {
            "cdc": cached.cdc,
            "estado": cached.estado_sifen,
            "es_valido": cached.es_valido,
            "ruc_emisor": cached.ruc_emisor,
            "razon_social": cached.razon_social,
            "timbrado": cached.timbrado,
            "total_comprobante": float(cached.total_comprobante) if cached.total_comprobante is not None else None,
            "iva_10": float(cached.iva_10) if cached.iva_10 is not None else None,
            "iva_5": float(cached.iva_5) if cached.iva_5 is not None else None,
            "en_cache": True
        }

    # 2. Validación matemática del formato
    res_val = validar_formato_cdc(cdc_limpio)
    if not res_val.get("valido"):
        cache_item = SifenCache(
            cdc=cdc_limpio,
            estado_sifen="CDC_INVALIDO",
            ruc_emisor=res_val.get("ruc_emisor"),
            es_valido=False,
            respuesta_raw=res_val
        )
        db.add(cache_item)
        await db.commit()
        return {
            "cdc": cdc_limpio,
            "estado": "CDC_INVALIDO",
            "es_valido": False,
            "error": res_val.get("error"),
            "en_cache": False
        }

    # 3. CDC algorítmicamente correcto
    estado_final = "FORMATO_VALIDO"
    es_valido = True
    razon_social = None
    timbrado = res_val.get("comprobante_formato")
    raw_data = res_val

    if consultar_online:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(SIFEN_REST_URL.format(cdc=cdc_limpio))
                if resp.status_code == 200:
                    data = resp.json()
                    estado_final = data.get("estado", "APROBADO")
                    razon_social = data.get("razonSocialEmisor")
                    raw_data = data
                elif resp.status_code == 404:
                    estado_final = "NO_EXISTE"
                    es_valido = False
        except Exception as e:
            logger.warning(f"Error consultando SIFEN online para CDC {cdc_limpio}: {e}")
            # Mantiene FORMATO_VALIDO ante fallo de conectividad de la DNIT
            estado_final = "FORMATO_VALIDO"

    cache_item = SifenCache(
        cdc=cdc_limpio,
        estado_sifen=estado_final,
        ruc_emisor=res_val.get("ruc_emisor"),
        razon_social=razon_social,
        timbrado=timbrado,
        es_valido=es_valido,
        respuesta_raw=raw_data
    )
    db.add(cache_item)
    await db.commit()

    return {
        "cdc": cdc_limpio,
        "estado": estado_final,
        "es_valido": es_valido,
        "ruc_emisor": res_val.get("ruc_emisor"),
        "razon_social": razon_social,
        "timbrado": timbrado,
        "comprobante_formato": res_val.get("comprobante_formato"),
        "en_cache": False
    }


async def verificar_lote_cdcs(
    db: AsyncSession,
    cdcs: List[str],
    consultar_online: bool = False,
    max_concurrencia: int = 5
) -> Dict[str, Dict[str, Any]]:
    """
    Verifica una lista de CDCs procesando con la base de datos de forma segura.
    Retorna un diccionario mapeando CDC -> Dict resultado.
    """
    resultados: Dict[str, Dict[str, Any]] = {}
    for cdc_item in cdcs:
        if not cdc_item:
            continue
        res = await consultar_o_validar_cdc(db, cdc_item, consultar_online=consultar_online)
        resultados[cdc_item] = res

    return resultados
