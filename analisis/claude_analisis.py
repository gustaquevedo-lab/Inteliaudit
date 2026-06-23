"""
Analisis inteligente via IA — Gemini (default) o Claude.
Genera narrativa profesional de hallazgos de auditoria.
"""
import json
from typing import Optional

from rich.console import Console

from analisis.ai_provider import AIProvider
from config.settings import settings

console = Console()


def generar_narrativa_hallazgo(
    hallazgo: dict,
    cliente: dict,
    auditoria: dict,
    provider: Optional[str] = None,
) -> str:
    """
    Genera narrativa profesional de un hallazgo usando IA.

    Args:
        hallazgo: Dict con tipo_hallazgo, descripcion, articulo_legal,
                  impuesto_omitido, multa_estimada, intereses_estimados,
                  total_contingencia, nivel_riesgo, periodo
        cliente: Dict con razon_social, ruc, actividad_principal
        auditoria: Dict con periodo_desde, periodo_hasta
        provider: "gemini" | "claude" (default: settings.ai_provider)

    Returns:
        Texto narrativo en espanol (2-3 parrafos)
    """
    ai = AIProvider(provider)

    system_prompt = """Sos un auditor impositivo senior en Paraguay especializado en Ley 6380/2019.
Conoces a fondo la legislacion tributaria paraguaya, la Ley 125/1991, el Decreto 3107/2019,
y las Resoluciones Generales SET (RG 24/2014, RG 69/2020, RG 80/2021, RG 90/2021).

Respondes siempre en espanol formal, con precision tecnica y citando articulos legales exactos.
No inventas cifras ni afirmaciones que no esten en los datos provistos."""

    user_prompt = f"""
Redacta una narrativa profesional del siguiente hallazgo de auditoria en 2-3 parrafos.

DATOS DEL CLIENTE:
Razon Social: {cliente.get('razon_social', 'N/A')}
RUC: {cliente.get('ruc', 'N/A')}
Actividad: {cliente.get('actividad_principal', 'N/A')}
Periodo auditado: {auditoria.get('periodo_desde', 'N/A')} a {auditoria.get('periodo_hasta', 'N/A')}

HALLAZGO:
Tipo: {hallazgo.get('tipo_hallazgo', 'N/A')}
Periodo: {hallazgo.get('periodo', 'N/A')}
Descripcion: {hallazgo.get('descripcion', 'N/A')}
Articulo Legal: {hallazgo.get('articulo_legal', 'N/A')}
Base de Ajuste: Gs. {hallazgo.get('base_ajuste', 0):,}
Impuesto Omitido: Gs. {hallazgo.get('impuesto_omitido', 0):,}
Multa Estimada (50%): Gs. {hallazgo.get('multa_estimada', 0):,}
Intereses Estimados (1%/mes): Gs. {hallazgo.get('intereses_estimados', 0):,}
Total Contingencia: Gs. {hallazgo.get('total_contingencia', 0):,}
Nivel de Riesgo: {hallazgo.get('nivel_riesgo', 'N/A')}

INSTRUCCIONES:
- Redacta una NARRATIVA TÉCNICA DE AUDITORÍA para un informe, NO una nota de comunicación, correo o carta (prohibido incluir saludos como 'Estimados señores', firmas o introducciones conversacionales). El texto debe empezar directamente describiendo el hallazgo.
- NO utilices formato Markdown en absoluto (evita usar asteriscos '**' o '*' para negritas o listas). Debe ser texto plano separado por párrafos con saltos de línea.
- Redacta en espanol formal paraguayo.
- Estructura la narrativa en 2 o 3 párrafos cubriendo:
  1. Condición (el hecho irregular detectado y periodo).
  2. Criterio (el artículo legal aplicable y su relevancia).
  3. Efecto/Contingencia (cuantificación del impuesto omitido, multa del 50% e intereses del 1% mensual).
- Tono: formal, objetivo, tecnico pero comprensible para el directorio de la empresa.
- 2-3 parrafos como maximo.
"""

    try:
        return ai.generar(system_prompt, user_prompt, max_tokens=1200)
    except Exception as e:
        return f"[Error al generar narrativa: {e}]"


def generar_resumen_ejecutivo(
    cliente: dict,
    auditoria: dict,
    hallazgos: list[dict],
    resumen: dict,
    provider: Optional[str] = None,
) -> str:
    """Genera resumen ejecutivo de la auditoria completa usando IA."""
    ai = AIProvider(provider)
    system_prompt = """Sos un auditor impositivo senior en Paraguay especializado en Ley 6380/2019.
Redactas resumenes ejecutivos para directorios de empresas."""

    user_prompt = f"""
Redacta un resumen ejecutivo de auditoria impositiva de 3-4 parrafos.

CLIENTE: {cliente.get('razon_social', 'N/A')} — RUC {cliente.get('ruc', 'N/A')}
PERIODO: {auditoria.get('periodo_desde', 'N/A')} a {auditoria.get('periodo_hasta', 'N/A')}
ACTIVIDAD: {cliente.get('actividad_principal', 'N/A')}
REGIMEN: {cliente.get('regimen', 'N/A')}

HALLAZGOS TOTALES: {resumen.get('cantidad_hallazgos', 0)}
CONTINGENCIA TOTAL: Gs. {resumen.get('total_contingencia', 0):,}
POR RIESGO: Alto={resumen.get('por_riesgo', {}).get('alto', 0)}, Medio={resumen.get('por_riesgo', {}).get('medio', 0)}, Bajo={resumen.get('por_riesgo', {}).get('bajo', 0)}

Hallazgos mas significativos:
{json.dumps(hallazgos[:5] if hallazgos else [], ensure_ascii=False, indent=2, default=str)}

Incluir: alcance, principales hallazgos ordenados por materialidad, contingencia fiscal total, recomendaciones.
Tono profesional, directo, sin tecnicismos innecesarios.
"""
    try:
        return ai.generar(system_prompt, user_prompt, max_tokens=1500)
    except Exception as e:
        return f"[Error al generar resumen: {e}]"
