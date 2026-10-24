"""
Cliente HTTP nativo para Marangatú (REA - Reverse Engineering API).
Permite verificar sesiones tributarias activas, listar talones RG 90
y descargar comprobantes de compras y ventas sin requerir un navegador Chromium.
"""
import io
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx

logger = logging.getLogger("marangatu_http")

MARANGATU_BASE_URL = "https://marangatu.dnit.gov.py"
ENDPOINT_SESION = f"{MARANGATU_BASE_URL}/eset/publico/consultarSesion.do"
ENDPOINT_TALONES = f"{MARANGATU_BASE_URL}/eset/rg90/talones"
ENDPOINT_DESCARGA = f"{MARANGATU_BASE_URL}/eset/rg90/descargar"


def _limpiar_cookie(cookie_raw: str) -> str:
    """Normaliza y asegura formato de Cookie HTTP."""
    if not cookie_raw:
        return ""
    c = cookie_raw.strip()
    if not c.startswith("JSESSIONID=") and "=" not in c:
        return f"JSESSIONID={c}"
    return c


class MarangatuHttpClient:
    """
    Cliente HTTP asíncrono para interactuar con la SPA de Marangatú.
    """

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.headers_default = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Referer": f"{MARANGATU_BASE_URL}/",
            "Origin": MARANGATU_BASE_URL,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
        }

    async def verificar_sesion(self, cookie: str) -> Dict[str, Any]:
        """
        Verifica si la sesión provista está activa en Marangatú.
        Retorna diccionario con validez y datos del contribuyente logueado.
        """
        cookie_hdr = _limpiar_cookie(cookie)
        headers = {**self.headers_default, "Cookie": cookie_hdr}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(ENDPOINT_SESION, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    autenticado = data.get("autenticado", True)
                    ruc_base = data.get("ruc") or data.get("rucContribuyente", "")
                    dv = data.get("dv", "")
                    ruc_completo = f"{ruc_base}-{dv}" if dv else str(ruc_base)
                    nombre = data.get("razonSocial") or data.get("nombreContribuyente") or "Usuario Marangatú"

                    return {
                        "valido": bool(autenticado and ruc_base),
                        "ruc": ruc_completo,
                        "nombre": nombre,
                        "detalles": data
                    }
                elif resp.status_code in (401, 403):
                    return {
                        "valido": False,
                        "error": "Sesión expirada o inválida. Por favor renueve su acceso a Marangatú."
                    }
                else:
                    return {
                        "valido": False,
                        "error": f"Respuesta inesperada de Marangatú: HTTP {resp.status_code}"
                    }
        except Exception as e:
            logger.error(f"Error verificando sesión en Marangatú: {e}")
            return {
                "valido": False,
                "error": f"Error de conectividad con la DNIT: {str(e)}"
            }

    async def listar_talones_rg90(
        self,
        cookie: str,
        ruc: str,
        periodo: str
    ) -> List[Dict[str, Any]]:
        """
        Consulta los talones de presentación de la RG 90 confirmados ante la DNIT.
        """
        cookie_hdr = _limpiar_cookie(cookie)
        headers = {**self.headers_default, "Cookie": cookie_hdr}
        params = {"ruc": ruc, "periodo": periodo}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(ENDPOINT_TALONES, headers=headers, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("talones", [])
                return []
        except Exception as e:
            logger.error(f"Error listando talones RG 90: {e}")
            return []

    async def descargar_comprobantes(
        self,
        cookie: str,
        id_talon: str
    ) -> bytes:
        """
        Descarga el payload de detalle de comprobantes asociado a un talón de presentación.
        """
        cookie_hdr = _limpiar_cookie(cookie)
        headers = {**self.headers_default, "Cookie": cookie_hdr}
        params = {"idTalon": id_talon}

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(ENDPOINT_DESCARGA, headers=headers, params=params)
                if resp.status_code == 200:
                    return resp.content
                return b""
        except Exception as e:
            logger.error(f"Error descargando comprobantes de talón {id_talon}: {e}")
            return b""


def parsear_registros_marangatu(payload: Any) -> List[Dict[str, Any]]:
    """
    Convierte la lista de registros obtenida desde la API interna de Marangatú
    al esquema estándar de `RG90` utilizado en Inteliaudit.
    """
    if not isinstance(payload, list):
        return []

    registros: List[Dict[str, Any]] = []
    for item in payload:
        tipo = item.get("tipo", "compra").lower()
        if "venta" in tipo:
            tipo_estandar = "venta"
        else:
            tipo_estandar = "compra"

        total = float(item.get("total", 0.0) or 0.0)
        iva10 = float(item.get("iva10", 0.0) or item.get("iva_10", 0.0) or 0.0)
        iva5 = float(item.get("iva5", 0.0) or item.get("iva_5", 0.0) or 0.0)
        grav10 = float(item.get("gravada10", 0.0) or item.get("gravada_10", 0.0) or 0.0)
        grav5 = float(item.get("gravada5", 0.0) or item.get("gravada_5", 0.0) or 0.0)
        exenta = float(item.get("exenta", 0.0) or 0.0)

        registros.append({
            "tipo": tipo_estandar,
            "tipo_comprobante": str(item.get("tipoComprobante", item.get("tipo_comprobante", "109"))),
            "ruc_contraparte": item.get("rucEmisor") or item.get("rucReceptor") or item.get("ruc_contraparte", ""),
            "razon_social_contraparte": item.get("razonSocial") or item.get("razon_social", ""),
            "timbrado": str(item.get("timbrado", "")),
            "establecimiento": str(item.get("establecimiento", "001")),
            "punto_expedicion": str(item.get("puntoExpedicion", "001")),
            "numero_documento": str(item.get("numeroDocumento", "")),
            "fecha_comprobante": str(item.get("fecha", item.get("fecha_comprobante", ""))),
            "gravada_10": grav10,
            "iva_10": iva10,
            "gravada_5": grav5,
            "iva_5": iva5,
            "exenta": exenta,
            "total_comprobante": total,
            "cdc": item.get("cdc")
        })

    return registros
