"""
AI Copilot para auditoría impositiva.
Chat contextual sobre hallazgos, recomendaciones y análisis.
"""
from typing import Optional
from rich.console import Console

console = Console()

SYSTEM_PROMPT = """Eres un asistente experto en auditoría impositiva para Paraguay.
Tu rol es ayudar al auditor con:
- Análisis de hallazgos detectados por el sistema
- Recomendaciones de acción para cada tipo de hallazgo
- Explicación de la base legal aplicable
- Estimación de impacto financiero
- Sugerencias de procedimientos adicionales
- Respuestas a preguntas sobre normativa tributaria paraguaya

Marco legal relevante:
- Ley 6380/2019 (Modernización tributaria): IRE, IRP, IDU, IRNR, IVA
- Ley 125/1991 (Código tributario): multas, prescripción, recursos
- RG 69/2020, RG 80/2021, RG 90/2021 (e-Kuatia, RG90)
- RG 24/2014 (Comprobantes de venta)

Responde SIEMPRE en español. Sé conciso y técnico. Cita artículos específicos.
Si no sabes algo, di "No tengo información suficiente para responder eso."
"""


class AuditoriaCopilot:
    """Chat copilot para la auditoría actual."""

    def __init__(self, firma_id: str, auditoria_id: str):
        self.firma_id = firma_id
        self.auditoria_id = auditoria_id
        self._provider = None

    def _get_provider(self):
        if self._provider:
            return self._provider
        try:
            from analisis.ai_provider import AIProvider
            self._provider = AIProvider()
        except Exception:
            self._provider = None
        return self._provider

    async def preguntar(
        self,
        pregunta: str,
        contexto_hallazgos: Optional[list[dict]] = None,
        contexto_cliente: Optional[dict] = None,
    ) -> str:
        """
        Responde una pregunta sobre la auditoría actual.
        Incluye contexto de hallazgos y cliente si se proveen.
        """
        provider = self._get_provider()
        if not provider:
            return "IA no configurada. Verificar ANTHROPIC_API_KEY o GEMINI_API_KEY en settings."

        context_parts = []

        if contexto_cliente:
            context_parts.append(
                f"Cliente: {contexto_cliente.get('razon_social', 'N/A')} "
                f"(RUC {contexto_cliente.get('ruc', 'N/A')})"
            )

        if contexto_hallazgos:
            hallazgos_texto = []
            for h in contexto_hallazgos[:10]:
                hallazgos_texto.append(
                    f"- [{h.get('nivel_riesgo', '?').upper()}] {h.get('tipo_hallazgo', '?')}: "
                    f"{h.get('descripcion', '')[:200]} "
                    f"(Contingencia: Gs. {h.get('total_contingencia', 0):,})"
                )
            context_parts.append("Hallazgos detectados:\n" + "\n".join(hallazgos_texto))

        contexto = "\n\n".join(context_parts) if context_parts else "Sin contexto adicional."

        user_prompt = f"Contexto de la auditoría:\n{contexto}\n\nPregunta del auditor:\n{pregunta}"

        try:
            respuesta = provider.generar(SYSTEM_PROMPT, user_prompt, max_tokens=1500)
            return respuesta
        except Exception as e:
            return f"Error al consultar IA: {str(e)}"

    async def analizar_hallazgo(self, hallazgo: dict) -> str:
        """Genera un análisis detallado de un hallazgo específico."""
        provider = self._get_provider()
        if not provider:
            return "IA no configurada."

        prompt = f"""Analiza este hallazgo de auditoría impositiva y proporciona:
1. Resumen del problema
2. Impacto fiscal estimado
3. Base legal aplicable (citar artículos)
4. Recomendaciones de acción
5. Riesgo de fiscalización por parte de la SET

Hallazgo:
- Tipo: {hallazgo.get('tipo_hallazgo', 'N/A')}
- Período: {hallazgo.get('periodo', 'N/A')}
- Descripción: {hallazgo.get('descripcion', 'N/A')}
- Base de ajuste: Gs. {hallazgo.get('base_ajuste', 0):,}
- Impuesto omitido: Gs. {hallazgo.get('impuesto_omitido', 0):,}
- Multa estimada: Gs. {hallazgo.get('multa_estimada', 0):,}
- Intereses estimados: Gs. {hallazgo.get('intereses_estimados', 0):,}
- Total contingencia: Gs. {hallazgo.get('total_contingencia', 0):,}
- Nivel de riesgo: {hallazgo.get('nivel_riesgo', 'N/A')}
- Artículo legal: {hallazgo.get('articulo_legal', 'N/A')}"""

        try:
            return provider.generar(SYSTEM_PROMPT, prompt, max_tokens=2000)
        except Exception as e:
            return f"Error al analizar hallazgo: {str(e)}"

    async def sugerir_procedimientos(self, impuestos_en_alcance: list[str]) -> str:
        """Sugiere procedimientos de auditoría adicionales según los impuestos en alcance."""
        provider = self._get_provider()
        if not provider:
            return "IA no configurada."

        prompt = f"""Basado en los siguientes impuestos en alcance: {', '.join(impuestos_en_alcance)},
sugiere procedimientos de auditoría adicionales que deberían realizarse.
Para cada procedimiento indica:
- Nombre del procedimiento
- Objetivo
- Fuente de datos necesaria
- Riesgo que mitiga
- Artículo legal de referencia

Enfócate en procedimientos que no sean los cruces automáticos estándar (RG90, SIFEN, HECHAUKA)."""

        try:
            return provider.generar(SYSTEM_PROMPT, prompt, max_tokens=1500)
        except Exception as e:
            return f"Error al generar sugerencias: {str(e)}"
