"""
Procedimientos de auditoría de Retenciones IVA e IRE.
Formularios 800-830. Cruces con HECHAUKA.
"""
from dataclasses import dataclass, field

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo
from db import db as crud

console = Console()

# Tasas de retención principales
TASAS_RETENCION = {
    "iva_servicios_personales":   0.03,   # 30% del IVA = 3% sobre precio
    "iva_compras_normal":         0.03,   # agentes de retención designados
    "ire_honorarios":             0.03,   # hasta 3% sobre importe bruto
    "pequenos_iva":               0.30,   # 30% del IVA
    "pequenos_ire":               0.025,  # 2.5% sobre importe
}

MULTA_RETENCION_DIA = 0.001   # 0.1% por día de mora (Art. 175 Ley 125/1991)
MULTA_RETENCION_MAX = 0.20    # tope 20%

ARTICULOS = {
    "RET_NO_PRACTICADA":        "Art. 159 Ley 6380/2019 — Obligación agente de retención",
    "RET_NO_DEPOSITADA":        "Art. 175 Ley 125/1991 — Multa 0.1% diaria hasta 20%",
    "RET_DIFERENCIA_HECHAUKA":  "Art. 159 Ley 6380/2019 — Consistencia retenciones declaradas",
}


@dataclass
class ResultadoAuditoriaRetenciones:
    periodo: str
    hallazgos_generados: int = 0
    retenciones_omitidas: int = 0
    retenciones_no_depositadas: int = 0
    detalles: list[dict] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


class AuditoriaRetenciones:
    """Procedimientos de auditoría de retenciones IVA e IRE."""

    def __init__(self, db: AsyncSession, firma_id: str, auditoria_id: str, materialidad: int = 0):
        self.db = db
        self.firma_id = firma_id
        self.auditoria_id = auditoria_id
        self.materialidad = materialidad

    async def ejecutar_auditoria_completa(
        self,
        cliente_id: str,
        periodos: list[str],
    ) -> list[ResultadoAuditoriaRetenciones]:
        resultados = []
        for periodo in periodos:
            console.print(f"[blue]Retenciones:[/] auditando período {periodo}...")
            resultados.append(await self.auditar_periodo(cliente_id, periodo))
        return resultados

    async def auditar_periodo(self, cliente_id: str, periodo: str) -> ResultadoAuditoriaRetenciones:
        resultado = ResultadoAuditoriaRetenciones(periodo=periodo)

        r1 = await self.cruce_hechauka_vs_declaraciones(cliente_id, periodo)
        resultado.hallazgos_generados += r1

        return resultado

    # --------------------------------------------------------
    #  Cruce HECHAUKA vs Declaraciones de retenciones
    # --------------------------------------------------------

    async def cruce_hechauka_vs_declaraciones(self, cliente_id: str, periodo: str) -> int:
        """
        Compara retenciones que terceros dicen haberle practicado al cliente
        (según HECHAUKA) con lo que el cliente declaró en sus Forms. 800/820.

        Si hay retenciones en HECHAUKA no declaradas por el agente → hallazgo.
        """
        hechauka = await crud.get_hechauka(self.db, self.firma_id, cliente_id, periodo)
        retenciones_hechauka = [h for h in hechauka if h.tipo_operacion in ("retencion_practicada", "retencion")]

        if not retenciones_hechauka:
            return 0

        # Suma total de retenciones según HECHAUKA
        total_iva_hechauka = sum(h.retencion_iva for h in retenciones_hechauka)
        total_ire_hechauka = sum(h.retencion_ire for h in retenciones_hechauka)

        hallazgos = 0
        # TODO: comparar vs declarado y generar hallazgos por diferencia
        console.print(f"[dim]Retenciones {periodo}: HECHAUKA reporta Gs. {total_iva_hechauka:,} IVA + Gs. {total_ire_hechauka:,} IRE retenidos[/]")

        return hallazgos

    # --------------------------------------------------------
    #  Helpers de cálculo
    # --------------------------------------------------------

    @staticmethod
    def calcular_retencion_iva(importe_bruto: int, tipo: str = "servicios_personales") -> dict:
        """
        Calcula la retención IVA sobre un pago.

        Args:
            importe_bruto: Monto del pago en PYG (IVA incluido)
            tipo: Tipo de pago — ver TASAS_RETENCION

        Returns:
            Dict con iva_incluido, retencion_iva, neto_a_pagar
        """
        tasa = TASAS_RETENCION.get(f"iva_{tipo}", TASAS_RETENCION["iva_servicios_personales"])
        iva_incluido = int(importe_bruto / 11 * 1)  # IVA al 10% incluido
        retencion = int(importe_bruto * tasa)
        return {
            "importe_bruto": importe_bruto,
            "iva_incluido": iva_incluido,
            "retencion_iva": retencion,
            "neto_a_pagar": importe_bruto - retencion,
        }

    @staticmethod
    def calcular_multa_retencion(
        retencion_omitida: int,
        fecha_vencimiento: str,
        fecha_calculo: str | None = None,
    ) -> dict:
        """
        Calcula multa por retención practicada y no depositada.
        0.1% por día de mora hasta 20% máximo. Art. 175 Ley 125/1991.
        """
        from datetime import date

        fecha_v = date.fromisoformat(fecha_vencimiento)
        fecha_c = date.today() if not fecha_calculo else date.fromisoformat(fecha_calculo)
        dias = max(0, (fecha_c - fecha_v).days)
        tasa_multa = min(dias * MULTA_RETENCION_DIA, MULTA_RETENCION_MAX)
        multa = int(retencion_omitida * tasa_multa)
        return {
            "retencion_omitida": retencion_omitida,
            "dias_mora": dias,
            "tasa_multa": tasa_multa,
            "multa": multa,
            "total": retencion_omitida + multa,
        }
