"""
Análisis inteligente vía Claude API.
Interpreta hallazgos, sugiere procedimientos adicionales y redacta descripciones técnicas.
"""
import json
from typing import Optional

import anthropic
from rich.console import Console

from config.settings import settings

console = Console()

MODEL = "claude-sonnet-4-6"


class ClaudeAuditor:
    """
    Usa Claude para asistir al auditor con interpretación, redacción y análisis.
    """

    def __init__(self):
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # --------------------------------------------------------
    #  Interpretación de hallazgos
    # --------------------------------------------------------

    def interpretar_hallazgos(
        self,
        hallazgos: list[dict],
        contexto_cliente: dict,
    ) -> str:
        """
        Genera un análisis narrativo de los hallazgos para el informe de auditoría.

        Args:
            hallazgos: Lista de hallazgos con montos y tipos
            contexto_cliente: Datos del cliente (ruc, razon_social, actividad, etc.)

        Returns:
            Texto narrativo en español para incluir en el informe
        """
        prompt = _construir_prompt_interpretacion(hallazgos, contexto_cliente)

        response = self._client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=_sistema_auditor(),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    # --------------------------------------------------------
    #  Sugerencia de procedimientos adicionales
    # --------------------------------------------------------

    def sugerir_procedimientos(
        self,
        hallazgos: list[dict],
        impuesto: str,
        contexto_cliente: dict,
    ) -> list[str]:
        """
        Basándose en los hallazgos encontrados, sugiere procedimientos adicionales de auditoría.

        Returns:
            Lista de procedimientos adicionales sugeridos
        """
        prompt = f"""
Estás auditando el {impuesto} de {contexto_cliente.get('razon_social', 'un contribuyente')}
(RUC: {contexto_cliente.get('ruc', '')}, actividad: {contexto_cliente.get('actividad_principal', '')}).

Se encontraron los siguientes hallazgos:
{json.dumps(hallazgos, ensure_ascii=False, indent=2)}

¿Qué procedimientos adicionales de auditoría recomendás ejecutar dado estos hallazgos?
Respondé con una lista numerada, concisa, enfocada en el marco tributario paraguayo (Ley 6380/2019).
"""
        response = self._client.messages.create(
            model=MODEL,
            max_tokens=800,
            system=_sistema_auditor(),
            messages=[{"role": "user", "content": prompt}],
        )
        texto = response.content[0].text
        # Parsear lista numerada
        lineas = [l.strip() for l in texto.split("\n") if l.strip() and l.strip()[0].isdigit()]
        return lineas if lineas else [texto]

    # --------------------------------------------------------
    #  Redacción de conclusión ejecutiva
    # --------------------------------------------------------

    def redactar_conclusion(
        self,
        resumen_contingencias: dict,
        cliente: dict,
        periodo_desde: str,
        periodo_hasta: str,
    ) -> str:
        """
        Redacta el párrafo de conclusión del informe de auditoría.
        """
        prompt = f"""
Redactá el párrafo de conclusión para un informe de auditoría impositiva en Paraguay.

Cliente: {cliente.get('razon_social')} — RUC {cliente.get('ruc')}
Período auditado: {periodo_desde} a {periodo_hasta}
Régimen: {cliente.get('regimen', 'general')}

Resumen de contingencias:
{json.dumps(resumen_contingencias, ensure_ascii=False, indent=2)}

El párrafo debe:
- Estar en español formal paraguayo
- Citar los impuestos auditados
- Mencionar la contingencia total estimada en Guaraníes
- Señalar el nivel de riesgo predominante
- Ser de 3-4 oraciones máximo
- No usar lenguaje alarmista innecesario
"""
        response = self._client.messages.create(
            model=MODEL,
            max_tokens=500,
            system=_sistema_auditor(),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    # --------------------------------------------------------
    #  Clasificación de hallazgo por descripción libre
    # --------------------------------------------------------

    def clasificar_hallazgo(self, descripcion_libre: str) -> dict:
        """
        Dado un texto libre describiendo una irregularidad, identifica
        el tipo de hallazgo, impuesto y artículo legal aplicable.
        """
        prompt = f"""
El auditor describió esta irregularidad:
"{descripcion_libre}"

Clasificala según el sistema Inteliaudit:
- tipo_hallazgo: uno de los tipos del catálogo (IVA_CREDITO_RUC_INACTIVO, IVA_CREDITO_SIN_CDC,
  IVA_COMPROBANTE_NO_DECLARADO, IVA_DIFERENCIA_RG90_DJ, IVA_DEBITO_OMITIDO_HECHAUKA,
  IRE_GASTO_NO_DEDUCIBLE, IRE_DEPRECIACION_EXCEDIDA, IRE_INGRESO_NO_DECLARADO,
  IRE_GASTO_SIN_COMPROBANTE, RET_NO_PRACTICADA, RET_NO_DEPOSITADA, RET_DIFERENCIA_HECHAUKA)
- impuesto: IVA | IRE | RET_IVA | RET_IRE
- articulo_legal: artículo exacto de Ley 6380/2019 o Ley 125/1991
- nivel_riesgo: alto | medio | bajo

Respondé SOLO con JSON válido, sin markdown.
"""
        response = self._client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=_sistema_auditor(),
            messages=[{"role": "user", "content": prompt}],
        )
        try:
            return json.loads(response.content[0].text)
        except json.JSONDecodeError:
            return {"error": "No se pudo parsear respuesta", "raw": response.content[0].text}


# --------------------------------------------------------
#  Prompts internos
# --------------------------------------------------------

def _sistema_auditor() -> str:
    return """Sos un auditor impositivo experto en el sistema tributario paraguayo.
Conocés a fondo la Ley 6380/2019, Ley 125/1991, el Código Tributario,
las Resoluciones Generales SET (RG 24/2014, RG 69/2020, RG 80/2021, RG 90/2021),
y los procedimientos del portal Marangatú.

Respondés siempre en español formal, con precisión técnica.
Citás artículos legales exactos cuando corresponde.
No inventás cifras ni afirmaciones que no estén en los datos provistos."""


def _construir_prompt_interpretacion(hallazgos: list[dict], contexto: dict) -> str:
    resumen_por_tipo: dict = {}
    for h in hallazgos:
        tipo = h.get("tipo_hallazgo", "OTRO")
        if tipo not in resumen_por_tipo:
            resumen_por_tipo[tipo] = {"cantidad": 0, "total_contingencia": 0}
        resumen_por_tipo[tipo]["cantidad"] += 1
        resumen_por_tipo[tipo]["total_contingencia"] += h.get("total_contingencia", 0)

    return f"""
Analizá los siguientes hallazgos de auditoría y redactá una sección de "Observaciones de Auditoría"
para el informe formal.

Cliente: {contexto.get('razon_social')} — RUC {contexto.get('ruc')}
Actividad: {contexto.get('actividad_principal', 'no especificada')}
Régimen: {contexto.get('regimen', 'general')}

Hallazgos encontrados ({len(hallazgos)} en total):
{json.dumps(resumen_por_tipo, ensure_ascii=False, indent=2)}

Detalle de los 5 más significativos:
{json.dumps(sorted(hallazgos, key=lambda x: x.get('total_contingencia', 0), reverse=True)[:5], ensure_ascii=False, indent=2)}

Redactá 2-3 párrafos en español formal, explicando:
1. Los patrones encontrados y su significancia
2. El riesgo tributario para el contribuyente
3. Las acciones correctivas recomendadas
"""
