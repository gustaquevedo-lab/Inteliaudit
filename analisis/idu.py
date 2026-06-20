"""
Procedimientos de auditoría IDU — Impuesto a los Dividendos y Utilidades.
Ley 6380/2019 Art. 46-50. Alícuota: 8% residentes, 15% no residentes.
Formulario: 530
"""
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo
from db import db as crud

console = Console()

ARTICULOS_IDU = {
    "IDU_DISTRIBUCION_SIN_RETENCION": "Art. 46 Ley 6380/2019 — Retención IDU sobre dividendos",
    "IDU_DIFERENCIA_DJ": "Art. 48 Ley 6380/2019 — Consistencia DJ IDU",
    "IDU_DIVIDENDO_SIN_DECLARAR": "Art. 46 Ley 6380/2019 — Hecho generador no declarado",
}


@dataclass
class ResultadoIDU:
    periodo: str
    procedimiento: str
    hallazgos_generados: int = 0
    monto_ajuste: int = 0
    detalles: list[dict] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


class AuditoriaIDU:
    """Ejecuta procedimientos de auditoría IDU para una auditoría."""

    def __init__(self, db: AsyncSession, firma_id: str, auditoria_id: str, materialidad: int = 0):
        self.db = db
        self.firma_id = firma_id
        self.auditoria_id = auditoria_id
        self.materialidad = materialidad

    async def ejecutar(self, cliente_id: str, periodos: list[str]) -> list[ResultadoIDU]:
        resultados = []
        for periodo in periodos:
            resultados.append(await self._verificar_distribucion(cliente_id, periodo))
            resultados.append(await self._verificar_dj_idu(cliente_id, periodo))
        return resultados

    async def _verificar_distribucion(self, cliente_id: str, periodo: str) -> ResultadoIDU:
        """
        Verifica que las distribuciones de dividendos tengan retención IDU aplicada.
        Cruce: pagos a socios/accionistas vs retenciones IDU declaradas.
        """
        resultado = ResultadoIDU(periodo=periodo, procedimiento="Distribución IDU")

        # Obtener declaraciones IDU (Form.530)
        declaraciones = await crud.get_declaraciones(
            self.db, self.firma_id, cliente_id, "530", periodo
        )

        # Obtener retenciones recibidas por el cliente
        hechauka = await crud.get_hechauka(self.db, self.firma_id, cliente_id, periodo)

        if not declaraciones and not hechauka:
            resultado.errores.append(f"No hay datos IDU para {periodo}")
            return resultado

        # Si hay pagos reportados en HECHAUKA pero no hay DJ IDU
        pagos_con_retencion = [h for h in hechauka if h.tipo_operacion == "retencion_idu"]
        if pagos_con_retencion and not declaraciones:
            total_retencion = sum(h.retencion_ire for h in pagos_con_retencion)
            if total_retencion > self.materialidad:
                cont = calcular_contingencia(total_retencion, f"{periodo}-20")
                await crud.crear_hallazgo(
                    self.db,
                    firma_id=self.firma_id,
                    auditoria_id=self.auditoria_id,
                    impuesto="IDU",
                    periodo=periodo,
                    tipo_hallazgo="IDU_DISTRIBUCION_SIN_RETENCION",
                    descripcion=(
                        f"Se detectaron {len(pagos_con_retencion)} retenciones IDU por "
                        f"Gs. {total_retencion:,} en HECHAUKA, pero no se presentó DJ IDU (Form.530)."
                    ),
                    articulo_legal=ARTICULOS_IDU["IDU_DISTRIBUCION_SIN_RETENCION"],
                    base_ajuste=total_retencion * 12.5,
                    impuesto_omitido=total_retencion,
                    multa_estimada=cont["multa_estimada"],
                    intereses_estimados=cont["intereses_estimados"],
                    nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                )
                resultado.hallazgos_generados += 1
                resultado.monto_ajuste += total_retencion

        return resultado

    async def _verificar_dj_idu(self, cliente_id: str, periodo: str) -> ResultadoIDU:
        """Verifica consistencia entre DJ IDU y datos contables/HECHAUKA."""
        resultado = ResultadoIDU(periodo=periodo, procedimiento="Consistencia DJ IDU")

        declaraciones = await crud.get_declaraciones(
            self.db, self.firma_id, cliente_id, "530", periodo
        )
        if not declaraciones:
            resultado.errores.append(f"No hay DJ IDU para {periodo}")
            return resultado

        import json
        decl = sorted(declaraciones, key=lambda d: d.nro_rectificativa, reverse=True)[0]
        datos = json.loads(decl.datos_json)

        # Verificar que el monto declarado sea consistente
        dividendos_declarados = int(datos.get("dividendos_distribuidos", 0))
        retencion_declarada = int(datos.get("retencion_idu", 0))

        if dividendos_declarados > 0 and retencion_declarada == 0:
            resultado.errores.append(
                f"DJ IDU declara dividendos (Gs. {dividendos_declarados:,}) pero retención cero. "
                "Posible omisión de retención."
            )

        return resultado
