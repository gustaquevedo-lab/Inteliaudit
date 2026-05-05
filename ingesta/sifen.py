"""
Cliente SIFEN — consulta y validación de comprobantes electrónicos (e-Kuatia).
RG 69/2020 — implementación factura electrónica Paraguay.
"""
import xml.etree.ElementTree as ET
from typing import Optional

import httpx
from rich.console import Console

console = Console()

# Endpoint público de consulta de CDC
SIFEN_CONSULTA_URL = "https://ekuatia.set.gov.py/consultas/rest/api/v1/de/{cdc}"
SIFEN_LOTE_URL = "https://ekuatia.set.gov.py/consultas/rest/api/v1/de"


class SifenClient:
    """
    Consulta comprobantes electrónicos en SIFEN usando el CDC como identificador.
    """

    def __init__(self, timeout: int = 15):
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True)

    async def __aenter__(self) -> "SifenClient":
        return self

    async def __aexit__(self, *_) -> None:
        await self._client.aclose()

    # --------------------------------------------------------
    #  Consulta individual
    # --------------------------------------------------------

    async def consultar_cdc(self, cdc: str) -> dict:
        """
        Consulta un comprobante electrónico por CDC.

        Args:
            cdc: Código de Control de 44 dígitos

        Returns:
            Dict con datos del comprobante + campo 'encontrado' (bool)
        """
        if not _validar_cdc(cdc):
            return {"cdc": cdc, "encontrado": False, "error": "CDC inválido (no tiene 44 dígitos numéricos)"}

        try:
            resp = await self._client.get(SIFEN_CONSULTA_URL.format(cdc=cdc))
            if resp.status_code == 404:
                return {"cdc": cdc, "encontrado": False}
            resp.raise_for_status()
            datos = resp.json()
            return _parsear_respuesta_sifen(datos)
        except httpx.HTTPStatusError as e:
            return {"cdc": cdc, "encontrado": False, "error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            return {"cdc": cdc, "encontrado": False, "error": str(e)}

    # --------------------------------------------------------
    #  Consulta en lote
    # --------------------------------------------------------

    async def verificar_lote(self, cdcs: list[str]) -> dict[str, dict]:
        """
        Verifica una lista de CDCs. Retorna dict {cdc: resultado}.
        Hace las consultas con concurrencia controlada para no saturar SIFEN.
        """
        import asyncio

        resultados: dict[str, dict] = {}
        semaforo = asyncio.Semaphore(5)  # máx 5 consultas simultáneas

        async def consultar_con_semaforo(cdc: str) -> None:
            async with semaforo:
                resultados[cdc] = await self.consultar_cdc(cdc)
                await asyncio.sleep(0.2)  # cortesía al servicio

        await asyncio.gather(*[consultar_con_semaforo(cdc) for cdc in cdcs])
        return resultados

    # --------------------------------------------------------
    #  Parseo de XML e-Kuatia
    # --------------------------------------------------------

    @staticmethod
    def parsear_xml(xml_str: str) -> dict:
        """
        Parsea el XML de un Documento Electrónico (DE) según RG 69/2020.
        Extrae los campos relevantes para auditoría.
        """
        return _parsear_xml_de(xml_str)


# --------------------------------------------------------
#  Helpers
# --------------------------------------------------------

def _validar_cdc(cdc: str) -> bool:
    return len(cdc) == 44 and cdc.isdigit()


def _parsear_respuesta_sifen(datos: dict) -> dict:
    """Normaliza la respuesta JSON de la API SIFEN al formato interno."""
    # La estructura exacta depende de la versión del API SIFEN
    # Ajustar según respuesta real del endpoint
    return {
        "cdc": datos.get("id", ""),
        "encontrado": True,
        "tipo_de": datos.get("tipoDE", ""),
        "ruc_emisor": datos.get("rucEmisor", ""),
        "nombre_emisor": datos.get("nombreEmisor", ""),
        "ruc_receptor": datos.get("rucReceptor", ""),
        "nombre_receptor": datos.get("nombreReceptor", ""),
        "fecha_emision": datos.get("fechaEmision", ""),
        "timbrado": datos.get("numerotimbrado", ""),
        "establecimiento": datos.get("establecimiento", ""),
        "punto_expedicion": datos.get("puntoExpedicion", ""),
        "nro_comprobante": datos.get("numero", ""),
        "base_gravada_10": int(datos.get("gravado10", 0) or 0),
        "base_gravada_5": int(datos.get("gravado5", 0) or 0),
        "monto_exento": int(datos.get("exento", 0) or 0),
        "iva_total": int(datos.get("ivaTotal", 0) or 0),
        "total_comprobante": int(datos.get("total", 0) or 0),
        "estado_sifen": datos.get("estado", "aprobado").lower(),
        "xml_raw": datos.get("xmlDE", None),
    }


def _parsear_xml_de(xml_str: str) -> dict:
    """
    Extrae campos clave del XML de un Documento Electrónico (DE) e-Kuatia.
    Estructura según RG 69/2020.
    """
    try:
        root = ET.fromstring(xml_str)
        ns = {"de": "http://ekuatia.set.gov.py/sifen/xsd"}

        def find(path: str) -> Optional[str]:
            el = root.find(path, ns)
            return el.text if el is not None else None

        # Datos de timbrado
        tipo_de = find(".//de:gTimb/de:dTiDE")
        timbrado = find(".//de:gTimb/de:dNumTim")
        establecimiento = find(".//de:gTimb/de:dEst")
        punto_expedicion = find(".//de:gTimb/de:dPunExp")
        nro_comprobante = find(".//de:gTimb/de:dNumDoc")

        # Datos generales
        fecha_emision = find(".//de:gDatGralOpe/de:dFeEmiDE")
        ruc_receptor = find(".//de:gDatGralOpe/de:gDatRec/de:dRucRec")
        nombre_receptor = find(".//de:gDatGralOpe/de:gDatRec/de:dNomRec")

        # Emisor está en gEmis
        ruc_emisor = find(".//de:gEmis/de:dRucEm")
        nombre_emisor = find(".//de:gEmis/de:dNomEmi")

        # Totales
        base_10 = int(find(".//de:gTotSub/de:dTotGravOp10") or "0")
        base_5 = int(find(".//de:gTotSub/de:dTotGravOp5") or "0")
        exento = int(find(".//de:gTotSub/de:dTotExe") or "0")
        iva_total = int(find(".//de:gTotSub/de:dTotIVA") or "0")
        total = int(find(".//de:gTotSub/de:dTotGe") or "0")

        # CDC
        cdc = find(".//de:Id")

        return {
            "cdc": cdc,
            "tipo_de": tipo_de,
            "ruc_emisor": ruc_emisor,
            "nombre_emisor": nombre_emisor,
            "ruc_receptor": ruc_receptor,
            "nombre_receptor": nombre_receptor,
            "timbrado": timbrado,
            "establecimiento": establecimiento,
            "punto_expedicion": punto_expedicion,
            "nro_comprobante": nro_comprobante,
            "fecha_emision": fecha_emision,
            "base_gravada_10": base_10,
            "base_gravada_5": base_5,
            "monto_exento": exento,
            "iva_total": iva_total,
            "total_comprobante": total,
            "encontrado": True,
        }
    except ET.ParseError as e:
        return {"encontrado": False, "error": f"XML inválido: {e}"}
