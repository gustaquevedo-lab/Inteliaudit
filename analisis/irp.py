"""
Procedimientos de auditoría IRP — Impuesto a la Renta Personal.
Ley 6380/2019 Art. 70-80. Alícuota: 8% hasta 10 salarios mínimos / 10% excedente.
Formulario: 510
Contribuyentes: personas físicas con ingresos > 36 salarios mínimos anuales.
"""
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo
from db import db as crud

console = Console()

ARTICULOS_IRP = {
    "IRP_OMISION_INGRESOS": "Art. 72 Ley 6380/2019 — Ingresos omisos IRP",
    "IRP_SALARIO_MINIMO": "Art. 70 Ley 6380/2019 — Umbral obligación IRP",
}


@dataclass
class ResultadoIRP:
    periodo: str
    procedimiento: str
    hallazgos_generados: int = 0
    monto_ajuste: int = 0
    detalles: list[dict] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


class AuditoriaIRP:
    """Ejecuta procedimientos de auditoría IRP para contribuyentes personas físicas."""

    def __init__(self, db: AsyncSession, firma_id: str, auditoria_id: str, materialidad: int = 0):
        self.db = db
        self.firma_id = firma_id
        self.auditoria_id = auditoria_id
        self.materialidad = materialidad

    async def ejecutar(self, cliente_id: str, periodos: list[str]) -> list[ResultadoIRP]:
        resultados = []
        for periodo in periodos:
            resultados.append(await self._verificar_obligacion(cliente_id, periodo))
            resultados.append(await self._verificar_ingresos_omisos(cliente_id, periodo))
        return resultados

    async def _verificar_obligacion(self, cliente_id: str, periodo: str) -> ResultadoIRP:
        """
        Verifica si el contribuyente persona física está obligado a presentar IRP.
        Obligación: ingresos anuales > 36 salarios mínimos.
        Salario mínimo 2024: Gs. 2.794.367 → 36 salarios = Gs. 100.597.212
        """
        resultado = ResultadoIRP(periodo=periodo, procedimiento="Obligación IRP")

        declaraciones = await crud.get_declaraciones(
            self.db, self.firma_id, cliente_id, "510", periodo
        )

        # Obtener datos del cliente para verificar tipo
        cliente = await crud.get_cliente(self.db, self.firma_id, id=cliente_id)
        if not cliente:
            resultado.errores.append("Cliente no encontrado")
            return resultado

        if cliente.tipo_contribuyente != "fisica":
            resultado.errores.append("IRP aplica solo a personas físicas")
            return resultado

        if not declaraciones:
            # Persona física sin DJ IRP — verificar si debería declarar
            # Cruce con RG90 ventas para estimar ingresos
            ventas = await crud.get_rg90(self.db, self.firma_id, cliente_id, periodo, "venta")
            total_ventas = sum(v.total_comprobante for v in ventas)

            # Umbral anualizado (estimar 12 meses desde el período)
            umbral_anual = 100_597_212  # 36 salarios mínimos 2024
            ingresos_anualizados = total_ventas * 12  # Estimación rough

            if ingresos_anualizados > umbral_anual:
                resultado.errores.append(
                    f"Persona física con ingresos estimados Gs. {ingresos_anualizados:,} "
                    f"(anualizados) que superan umbral IRP (Gs. {umbral_anual:,}). "
                    "Debe presentar DJ IRP."
                )

        return resultado

    async def _verificar_ingresos_omisos(self, cliente_id: str, periodo: str) -> ResultadoIRP:
        """Cruce HECHAUKA vs DJ IRP para detectar ingresos no declarados."""
        resultado = ResultadoIRP(periodo=periodo, procedimiento="Ingresos omisos IRP")

        declaraciones = await crud.get_declaraciones(
            self.db, self.firma_id, cliente_id, "510", periodo
        )
        if not declaraciones:
            resultado.errores.append(f"No hay DJ IRP para {periodo}")
            return resultado

        import json
        decl = sorted(declaraciones, key=lambda d: d.nro_rectificativa, reverse=True)[0]
        datos = json.loads(decl.datos_json)

        ingresos_declarados = int(datos.get("renta_neta", 0))

        # Obtener HECHAUKA de terceros que reportaron pagos al contribuyente
        hechauka = await crud.get_hechauka(self.db, self.firma_id, cliente_id, periodo)
        pagos_recibidos = [h for h in hechauka if h.tipo_operacion in ("pago", "honorario")]

        if pagos_recibidos:
            total_pagos = sum(h.monto_operacion for h in pagos_recibidos)
            if total_pagos > ingresos_declarados and (total_pagos - ingresos_declarados) > self.materialidad:
                diferencia = total_pagos - ingresos_declarados
                cont = calcular_contingencia(diferencia, f"{periodo}-20")
                await crud.crear_hallazgo(
                    self.db,
                    firma_id=self.firma_id,
                    auditoria_id=self.auditoria_id,
                    impuesto="IRP",
                    periodo=periodo,
                    tipo_hallazgo="IRP_OMISION_INGRESOS",
                    descripcion=(
                        f"HECHAUKA reporta Gs. {total_pagos:,} de ingresos recibidos vs "
                        f"Gs. {ingresos_declarados:,} en DJ IRP. Diferencia: Gs. {diferencia:,}"
                    ),
                    articulo_legal=ARTICULOS_IRP["IRP_OMISION_INGRESOS"],
                    base_ajuste=diferencia,
                    impuesto_omitido=int(diferencia * 0.10),
                    multa_estimada=cont["multa_estimada"],
                    intereses_estimados=cont["intereses_estimados"],
                    nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                )
                resultado.hallazgos_generados += 1
                resultado.monto_ajuste += diferencia

        return resultado
