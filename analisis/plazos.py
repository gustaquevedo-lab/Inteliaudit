"""
Gestión de plazos y prescripción tributaria.
Calcula ventanas de fiscalización, plazos de prescripción y alertas.

Marco legal:
- Art. 218 Ley 125/1991: Prescripción de la acción de cobro (5 años)
- Art. 219 Ley 125/1991: Prescripción de la acción fiscalizadora (3 años)
- Art. 131 Ley 125/1991: Plazo para determinación de obligaciones
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from db import db as crud

console = Console()


@dataclass
class ObligacionConPlazo:
    impuesto: str
    periodo: str
    fecha_vencimiento: str
    fecha_presentacion: Optional[str] = None
    estado: str = "pendiente"  # "pendiente" | "presentada" | "vencida" | "prescrita"
    dias_para_vencer: Optional[int] = None
    dias_para_prescribir: Optional[int] = None
    nivel_riesgo: str = "bajo"


@dataclass
class ResultadoPlazos:
    fecha_calculo: str
    obligaciones: list[ObligacionConPlazo] = field(default_factory=list)
    ventanas_fiscalizacion: list[dict] = field(default_factory=list)
    alertas: list[dict] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


# Calendario de vencimientos por último dígito RUC
CALENDARIO_VENCIMIENTO = {
    # IVA Form 120 - mes siguiente según último dígito
    "120": {
        1: "10", 2: "11", 3: "12", 4: "13", 5: "14",
        6: "15", 7: "16", 8: "17", 9: "18", 0: "19",
    },
}


class GestionPlazos:
    """Gestiona plazos de vencimiento y prescripción tributaria."""

    def __init__(self, db: AsyncSession, firma_id: str):
        self.db = db
        self.firma_id = firma_id

    async def calcular_plazos(
        self,
        cliente_id: str,
        fecha_calculo: Optional[str] = None,
    ) -> ResultadoPlazos:
        """
        Calcula plazos de vencimiento y prescripción para todas las obligaciones.
        
        Args:
            cliente_id: ID del cliente
            fecha_calculo: Fecha de cálculo (default: hoy)
        """
        resultado = ResultadoPlazos(
            fecha_calculo=fecha_calculo or datetime.now().strftime("%Y-%m-%d")
        )

        cliente = await crud.get_cliente(self.db, self.firma_id, id=cliente_id)
        if not cliente:
            resultado.errores.append("Cliente no encontrado")
            return resultado

        fecha_calc = datetime.strptime(resultado.fecha_calculo, "%Y-%m-%d")

        # =========================================================
        # 1. Calcular prescripción de períodos anteriores
        # =========================================================
        resultado.ventanas_fiscalizacion = await self._calcular_ventanas_fiscalizacion(
            cliente_id, fecha_calc
        )

        # =========================================================
        # 2. Verificar obligaciones pendientes
        # =========================================================
        resultado.obligaciones = await self._verificar_obligaciones(
            cliente_id, fecha_calc
        )

        # =========================================================
        # 3. Generar alertas
        # =========================================================
        resultado.alertas = self._generar_alertas(resultado, fecha_calc)

        return resultado

    async def _calcular_ventanas_fiscalizacion(
        self,
        cliente_id: str,
        fecha_calculo: datetime,
    ) -> list[dict]:
        """
        Calcula las ventanas de fiscalización abiertas.
        
        Prescripción acción fiscalizadora: 3 años (Art. 219 Ley 125/1991)
        Prescripción acción cobro: 5 años (Art. 218 Ley 125/1991)
        """
        ventanas = []

        # Generar períodos de los últimos 5 años
        for anio_offset in range(6):
            anio = fecha_calculo.year - anio_offset
            for mes in range(1, 13):
                periodo = f"{anio}-{mes:02d}"
                fecha_periodo = datetime(anio, mes, 28)  # Fin del mes aproximado

                # Prescripción fiscalizadora (3 años)
                fecha_prescripcion_fiscal = fecha_periodo + timedelta(days=3*365)
                prescrito_fiscal = fecha_calculo > fecha_prescripcion_fiscal

                # Prescripción cobro (5 años)
                fecha_prescripcion_cobro = fecha_periodo + timedelta(days=5*365)
                prescrito_cobro = fecha_calculo > fecha_prescripcion_cobro

                # Estado de presentación
                declaraciones = await crud.get_declaraciones(
                    self.db, self.firma_id, cliente_id, "120", periodo
                )
                estado = "presentada" if declaraciones else "pendiente"

                if prescrito_fiscal:
                    estado = "prescrita"

                ventana = {
                    "periodo": periodo,
                    "estado": estado,
                    "prescrito_fiscal": prescrito_fiscal,
                    "prescrito_cobro": prescrito_cobro,
                    "fecha_prescripcion_fiscal": fecha_prescripcion_fiscal.strftime("%Y-%m-%d"),
                    "fecha_prescripcion_cobro": fecha_prescripcion_cobro.strftime("%Y-%m-%d"),
                    "dias_para_prescribir_fiscal": max(0, (fecha_prescripcion_fiscal - fecha_calculo).days),
                    "dias_para_prescribir_cobro": max(0, (fecha_prescripcion_cobro - fecha_calculo).days),
                }
                ventanas.append(ventana)

        return ventanas

    async def _verificar_obligaciones(
        self,
        cliente_id: str,
        fecha_calculo: datetime,
    ) -> list[ObligacionConPlazo]:
        """Verifica el estado de obligaciones tributarias."""
        obligaciones = []

        # Obtener declaraciones del cliente
        from sqlalchemy import select
        from db.models import Declaracion

        result = await self.db.execute(
            select(Declaracion).where(
                Declaracion.firma_id == self.firma_id,
                Declaracion.cliente_id == cliente_id,
            ).order_by(Declaracion.periodo.desc()).limit(24)
        )
        declaraciones = list(result.scalars().all())

        # Agrupar por formulario y período
        for decl in declaraciones:
            fecha_prescripcion = datetime.strptime(decl.periodo + "-28", "%Y-%m-%d") + timedelta(days=5*365)
            dias_para_prescribir = max(0, (fecha_prescripcion - fecha_calculo).days)

            obligacion = ObligacionConPlazo(
                impuesto=decl.formulario,
                periodo=decl.periodo,
                fecha_vencimiento="",
                fecha_presentacion=decl.fecha_presentacion,
                estado=decl.estado_declaracion,
                dias_para_prescribir=dias_para_prescribir,
                nivel_riesgo="bajo" if dias_para_prescribir > 365 else "medio" if dias_para_prescribir > 180 else "alto",
            )
            obligaciones.append(obligacion)

        return obligaciones

    def _generar_alertas(self, resultado: ResultadoPlazos, fecha_calculo: datetime) -> list[dict]:
        """Genera alertas de plazos y prescripción."""
        alertas = []

        # Alertas de prescripción próxima
        for ventana in resultado.ventanas_fiscalizacion:
            if ventana["dias_para_prescribir_fiscal"] <= 180 and ventana["dias_para_prescribir_fiscal"] > 0:
                alertas.append({
                    "tipo": "prescripcion_proxima",
                    "nivel": "alto" if ventana["dias_para_prescribir_fiscal"] <= 90 else "medio",
                    "periodo": ventana["periodo"],
                    "mensaje": (
                        f"Período {ventana['periodo']}: prescripción fiscalizadora en "
                        f"{ventana['dias_para_prescribir_fiscal']} días "
                        f"({ventana['fecha_prescripcion_fiscal']})"
                    ),
                    "dias_restantes": ventana["dias_para_prescribir_fiscal"],
                })

        # Alertas de obligaciones prescritas
        for ventana in resultado.ventanas_fiscalizacion:
            if ventana["prescrito_fiscal"] and ventana["estado"] == "pendiente":
                alertas.append({
                    "tipo": "prescrita_no_presentada",
                    "nivel": "info",
                    "periodo": ventana["periodo"],
                    "mensaje": (
                        f"Período {ventana['periodo']}: obligación prescrita "
                        f"(fiscalización venció {ventana['fecha_prescripcion_fiscal']})"
                    ),
                })

        # Ordenar alertas por nivel de riesgo
        nivel_orden = {"alto": 0, "medio": 1, "bajo": 2, "info": 3}
        alertas.sort(key=lambda a: nivel_orden.get(a["nivel"], 99))

        return alertas

    def calcular_fecha_prescripcion(self, periodo: str, tipo: str = "fiscal") -> str:
        """
        Calcula fecha de prescripción para un período específico.
        
        Args:
            periodo: YYYY-MM
            tipo: "fiscal" (3 años) o "cobro" (5 años)
        """
        anio, mes = map(int, periodo.split("-"))
        fecha_periodo = datetime(anio, mes, 28)
        
        if tipo == "fiscal":
            fecha_prescripcion = fecha_periodo + timedelta(days=3*365)
        else:
            fecha_prescripcion = fecha_periodo + timedelta(days=5*365)
        
        return fecha_prescripcion.strftime("%Y-%m-%d")

    def esta_en_ventana_fiscalizacion(self, periodo: str, fecha_calculo: Optional[str] = None) -> bool:
        """Verifica si un período está dentro de la ventana de fiscalización."""
        fecha_calc = datetime.strptime(fecha_calculo or datetime.now().strftime("%Y-%m-%d"), "%Y-%m-%d")
        fecha_prescripcion = datetime.strptime(
            self.calcular_fecha_prescripcion(periodo, "fiscal"), "%Y-%m-%d"
        )
        return fecha_calc <= fecha_prescripcion
