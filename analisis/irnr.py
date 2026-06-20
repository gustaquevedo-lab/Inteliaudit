"""
Procedimientos de auditoría IRNR — Impuesto a la Renta de No Residentes.
Ley 6380/2019 Art. 81-88. Alícuota: 15% general sobre renta de fuente paraguaya.
Formulario: 520
Obligación: pagos a no residentes por servicios, intereses, regalías, etc.
"""
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo
from db import db as crud

console = Console()

ARTICULOS_IRNR = {
    "IRNR_PAGO_SIN_RETENCION": "Art. 82 Ley 6380/2019 — Retención IRNR obligatoria",
    "IRNR_BASE_IMPONIBLE": "Art. 83 Ley 6380/2019 — Base imponible IRNR",
}


@dataclass
class ResultadoIRNR:
    periodo: str
    procedimiento: str
    hallazgos_generados: int = 0
    monto_ajuste: int = 0
    detalles: list[dict] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


class AuditoriaIRNR:
    """Ejecuta procedimientos de auditoría IRNR para pagos a no residentes."""

    def __init__(self, db: AsyncSession, firma_id: str, auditoria_id: str, materialidad: int = 0):
        self.db = db
        self.firma_id = firma_id
        self.auditoria_id = auditoria_id
        self.materialidad = materialidad

    async def ejecutar(self, cliente_id: str, periodos: list[str]) -> list[ResultadoIRNR]:
        resultados = []
        for periodo in periodos:
            resultados.append(await self._verificar_retencion_irnr(cliente_id, periodo))
            resultados.append(await self._verificar_base_imponible(cliente_id, periodo))
        return resultados

    async def _verificar_retencion_irnr(self, cliente_id: str, periodo: str) -> ResultadoIRNR:
        """
        Verifica que los pagos a no residentes tengan retención IRNR aplicada.
        Cruce: compras a proveedores no residentes vs retenciones IRNR declaradas.
        """
        resultado = ResultadoIRNR(periodo=periodo, procedimiento="Retención IRNR")

        # Obtener RG90 compras de proveedores no residentes (RUC que no empieza con 80/90)
        compras = await crud.get_rg90(self.db, self.firma_id, cliente_id, periodo, "compra")

        # Identificar proveedores no residentes (simplificado: RUC sin formato paraguayo)
        compras_no_residentes = [
            c for c in compras
            if c.ruc_contraparte and not c.ruc_contraparte.startswith(("80", "90"))
            and not c.ruc_contraparte.startswith("5")
        ]

        if not compras_no_residentes:
            return resultado

        # Obtener declaraciones IRNR
        declaraciones = await crud.get_declaraciones(
            self.db, self.firma_id, cliente_id, "520", periodo
        )

        import json
        retenciones_declaradas = 0
        if declaraciones:
            decl = sorted(declaraciones, key=lambda d: d.nro_rectificativa, reverse=True)[0]
            datos = json.loads(decl.datos_json)
            retenciones_declaradas = int(datos.get("retencion_irnr", 0))

        total_pagado = sum(c.total_comprobante for c in compras_no_residentes)
        retencion_esperada = int(total_pagado * 0.15)  # 15% IRNR

        if retenciones_declaradas < retencion_esperada:
            diferencia = retencion_esperada - retenciones_declaradas
            if diferencia > self.materialidad:
                cont = calcular_contingencia(diferencia, f"{periodo}-20")
                await crud.crear_hallazgo(
                    self.db,
                    firma_id=self.firma_id,
                    auditoria_id=self.auditoria_id,
                    impuesto="IRNR",
                    periodo=periodo,
                    tipo_hallazgo="IRNR_PAGO_SIN_RETENCION",
                    descripcion=(
                        f"Pagos a no residentes por Gs. {total_pagado:,}. "
                        f"Retención IRNR declarada: Gs. {retenciones_declaradas:,}. "
                        f"Retención esperada (15%): Gs. {retencion_esperada:,}. "
                        f"Diferencia: Gs. {diferencia:,}"
                    ),
                    articulo_legal=ARTICULOS_IRNR["IRNR_PAGO_SIN_RETENCION"],
                    base_ajuste=total_pagado,
                    impuesto_omitido=diferencia,
                    multa_estimada=cont["multa_estimada"],
                    intereses_estimados=cont["intereses_estimados"],
                    nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                    evidencias=[
                        {
                            "ruc_proveedor": c.ruc_contraparte,
                            "nombre": c.nombre_contraparte,
                            "monto": c.total_comprobante,
                        }
                        for c in compras_no_residentes[:10]
                    ],
                )
                resultado.hallazgos_generados += 1
                resultado.monto_ajuste += diferencia

        return resultado

    async def _verificar_base_imponible(self, cliente_id: str, periodo: str) -> ResultadoIRNR:
        """Verifica que la base imponible IRNR incluya todos los conceptos gravados."""
        resultado = ResultadoIRNR(periodo=periodo, procedimiento="Base imponible IRNR")

        declaraciones = await crud.get_declaraciones(
            self.db, self.firma_id, cliente_id, "520", periodo
        )
        if not declaraciones:
            resultado.errores.append(f"No hay DJ IRNR para {periodo}")
            return resultado

        import json
        decl = sorted(declaraciones, key=lambda d: d.nro_rectificativa, reverse=True)[0]
        datos = json.loads(decl.datos_json)

        base_imponible = int(datos.get("base_imponible", 0))
        retencion = int(datos.get("retencion_irnr", 0))

        if base_imponible > 0 and retencion == 0:
            resultado.errores.append(
                f"DJ IRNR declara base imponible (Gs. {base_imponible:,}) pero retención cero."
            )

        return resultado
