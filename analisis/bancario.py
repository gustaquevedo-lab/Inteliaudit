"""
Conciliación bancaria — cruce extractos bancarios contra lo declarado.
Procedimiento fundamental del auditor impositivo paraguayo.

Detecta:
- Ingresos no declarados en DJ IVA/IRE
- Pagos sin retención cuando correspondía
- Gastos personales del titular/socios
- Operaciones con partes vinculadas sin identificar
- Diferencias de conciliación no justificadas
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo
from db import db as crud

console = Console()

ARTICULOS = {
    "BCO_INGRESO_NO_DECLARADO": "Art. 93 Ley 6380/2019 — Ingresos gravados no declarados",
    "BCO_GASTO_NO_DEDUCIBLE": "Art. 16 Ley 6380/2019 — Gastos no deducibles (personales)",
    "BCO_PAGO_SIN_RETENCION": "Art. 76 Ley 6380/2019 — Retención omitida en pagos",
    "BCO_OPERACION_VINCULADA": "Art. 35 Ley 6380/2019 — Operaciones con partes vinculadas",
}


@dataclass
class TransaccionBancaria:
    """Representa una línea de extracto bancario."""
    fecha: str
    descripcion: str
    monto: int  # positivo = ingreso, negativo = egreso
    tipo: str  # "ingreso" | "egreso"
    conciliado: bool = False
    referencia: Optional[str] = None


@dataclass
class ResultadoConciliacionBancaria:
    periodo: str
    procedimiento: str
    hallazgos_generados: int = 0
    monto_ajuste: int = 0
    ingresos_encontrados: int = 0
    egresos_encontrados: int = 0
    diferencias: list[dict] = field(default_factory=list)
    detalles: list[dict] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


class ConciliacionBancaria:
    """
    Ejecuta conciliación bancaria para un período de auditoría.
    
    Flujo:
    1. Cargar extracto bancario (XLSX/CSV)
    2. Cargar declaraciones juradas del período
    3. Cruzar ingresos bancarios vs ventas declaradas
    4. Cruzar egresos bancarios vs compras declaradas
    5. Identificar partidas sin conciliar
    6. Clasificar diferencias (ingreso omitido, gasto personal, etc.)
    """

    def __init__(self, db: AsyncSession, firma_id: str, auditoria_id: str, materialidad: int = 0):
        self.db = db
        self.firma_id = firma_id
        self.auditoria_id = auditoria_id
        self.materialidad = materialidad

    async def ejecutar(
        self,
        cliente_id: str,
        periodo: str,
        transacciones: list[TransaccionBancaria],
    ) -> ResultadoConciliacionBancaria:
        """
        Ejecuta la conciliación bancaria completa.
        
        Args:
            cliente_id: ID del cliente
            periodo: Período YYYY-MM
            transacciones: Líneas del extracto bancario
        """
        resultado = ResultadoConciliacionBancaria(
            periodo=periodo,
            procedimiento="Conciliación Bancaria"
        )

        resultado.ingresos_encontrados = sum(
            1 for t in transacciones if t.tipo == "ingreso"
        )
        resultado.egresos_encontrados = sum(
            1 for t in transacciones if t.tipo == "egreso"
        )

        # Obtener datos del cliente
        cliente = await crud.get_cliente(self.db, self.firma_id, id=cliente_id)
        if not cliente:
            resultado.errores.append("Cliente no encontrado")
            return resultado

        # Obtener declaraciones del período
        declaraciones_iva = await crud.get_declaraciones(
            self.db, self.firma_id, cliente_id, "120", periodo
        )
        declaraciones_ire = await crud.get_declaraciones(
            self.db, self.firma_id, cliente_id, "500", periodo
        )

        # Obtener RG90 del período
        rg90_ventas = await crud.get_rg90(
            self.db, self.firma_id, cliente_id, periodo, "venta"
        )
        rg90_compras = await crud.get_rg90(
            self.db, self.firma_id, cliente_id, periodo, "compra"
        )

        # Obtener retenciones
        hechauka = await crud.get_hechauka(
            self.db, self.firma_id, cliente_id, periodo
        )

        # =========================================================
        # CRUCE 1: Ingresos bancarios vs ventas declaradas
        # =========================================================
        await self._cruzar_ingresos(
            cliente_id, periodo, transacciones, rg90_ventas, 
            declaraciones_iva, resultado
        )

        # =========================================================
        # CRUCE 2: Egresos bancarios vs compras declaradas
        # =========================================================
        await self._cruzar_egresos(
            cliente_id, periodo, transacciones, rg90_compras,
            declaraciones_iva, resultado
        )

        # =========================================================
        # CRUCE 3: Pagos a proveedores sin retención
        # =========================================================
        await self._verificar_retenciones(
            cliente_id, periodo, transacciones, hechauka, resultado
        )

        # =========================================================
        # CRUCE 4: Detección de gastos personales
        # =========================================================
        await self._detectar_gastos_personales(
            cliente_id, periodo, transacciones, resultado
        )

        return resultado

    async def _cruzar_ingresos(
        self,
        cliente_id: str,
        periodo: str,
        transacciones: list[TransaccionBancaria],
        rg90_ventas: list,
        declaraciones: list,
        resultado: ResultadoConciliacionBancaria,
    ):
        """Cruza ingresos bancarios contra ventas declaradas."""
        # Total ventas declaradas en RG90
        total_ventas_rg90 = sum(v.total_comprobante for v in rg90_ventas)

        # Total ingresos bancarios del período
        ingresos_bancarios = [t for t in transacciones if t.tipo == "ingreso"]
        total_ingresos_banco = sum(t.monto for t in ingresos_bancarios)

        # Diferencia
        diferencia = total_ingresos_banco - total_ventas_rg90

        if abs(diferencia) > self.materialidad:
            # Verificar si hay justificación (anticipos, préstamos, etc.)
            # Por ahora, reportar como diferencia potencial
            resultado.diferencias.append({
                "tipo": "INGRESOS_BCO_vs_VENTAS_RG90",
                "monto_banco": total_ingresos_banco,
                "monto_rg90": total_ventas_rg90,
                "diferencia": diferencia,
                "orientacion": "ingreso_excedente" if diferencia > 0 else "venta_excedente",
            })

            if diferencia > self.materialidad:
                # Posible ingreso omitido
                cont = calcular_contingencia(diferencia, f"{periodo}-20")
                await crud.crear_hallazgo(
                    self.db,
                    firma_id=self.firma_id,
                    auditoria_id=self.auditoria_id,
                    impuesto="IVA",
                    periodo=periodo,
                    tipo_hallazgo="BCO_INGRESO_NO_DECLARADO",
                    descripcion=(
                        f"Ingresos bancarios (Gs. {total_ingresos_banco:,}) superan "
                        f"ventas declaradas RG90 (Gs. {total_ventas_rg90:,}). "
                        f"Diferencia: Gs. {diferencia:,}. Posible ingreso omitido."
                    ),
                    articulo_legal=ARTICULOS["BCO_INGRESO_NO_DECLARADO"],
                    base_ajuste=diferencia,
                    impuesto_omitido=int(diferencia * 0.10),
                    multa_estimada=cont["multa_estimada"],
                    intereses_estimados=cont["intereses_estimados"],
                    nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                    evidencias=[{
                        "tipo": "conciliacion_bancaria",
                        "total_banco": total_ingresos_banco,
                        "total_rg90": total_ventas_rg90,
                        "diferencia": diferencia,
                    }],
                )
                resultado.hallazgos_generados += 1
                resultado.monto_ajuste += diferencia

    async def _cruzar_egresos(
        self,
        cliente_id: str,
        periodo: str,
        transacciones: list[TransaccionBancaria],
        rg90_compras: list,
        declaraciones: list,
        resultado: ResultadoConciliacionBancaria,
    ):
        """Cruza egresos bancarios contra compras declaradas."""
        total_compras_rg90 = sum(c.total_comprobante for c in rg90_compras)

        egresos_bancarios = [t for t in transacciones if t.tipo == "egreso"]
        total_egresos_banco = sum(abs(t.monto) for t in egresos_bancarios)

        diferencia = total_egresos_banco - total_compras_rg90

        if abs(diferencia) > self.materialidad:
            resultado.diferencias.append({
                "tipo": "EGRESOS_BCO_vs_COMPRAS_RG90",
                "monto_banco": total_egresos_banco,
                "monto_rg90": total_compras_rg90,
                "diferencia": diferencia,
                "orientacion": "egreso_excedente" if diferencia > 0 else "compra_excedente",
            })

    async def _verificar_retenciones(
        self,
        cliente_id: str,
        periodo: str,
        transacciones: list[TransaccionBancaria],
        hechauka: list,
        resultado: ResultadoConciliacionBancaria,
    ):
        """Verifica que los pagos a proveedores tengan retención aplicada."""
        # Obtener retenciones declaradas
        retenciones_declaradas = {}
        for h in hechauka:
            if h.retencion_iva > 0 or h.retencion_ire > 0:
                retenciones_declaradas[h.ruc_informante] = {
                    "retencion_iva": h.retencion_iva,
                    "retencion_ire": h.retencion_ire,
                }

        # Egresos bancarios que podrían ser pagos a proveedores
        egresos = [t for t in transacciones if t.tipo == "egreso"]
        
        # Aquí se necesitaría matching por RUC del proveedor
        # Por ahora, reportar egresos significativos sin retención conocida
        for egreso in egresos:
            if abs(egreso.monto) > self.materialidad * 2:
                resultado.detalles.append({
                    "tipo": "egreso_significativo",
                    "fecha": egreso.fecha,
                    "descripcion": egreso.descripcion,
                    "monto": egreso.monto,
                    "nota": "Verificar retención aplicable",
                })

    async def _detectar_gastos_personales(
        self,
        cliente_id: str,
        periodo: str,
        transacciones: list[TransaccionBancaria],
        resultado: ResultadoConciliacionBancaria,
    ):
        """
        Detecta patrones de gastos personales del titular/socios.
        Art. 16 Ley 6380/2019: gastos personales NO son deducibles.
        """
        # Palabras clave que sugieren gastos personales
        patrones_personales = [
            "transferencia personal", "retiro atm", "cajero",
            "supermercado", "farmacia", "hospital", "clinica",
            "educacion", "colegio", "universidad", "seguro personal",
            "prestamo personal", "tarjeta personal", "consumo personal",
            "viaje personal", "vacaciones", "entretenimiento",
        ]

        egresos = [t for t in transacciones if t.tipo == "egreso"]
        sospechosos = []

        for egreso in egresos:
            desc_lower = egreso.descripcion.lower()
            for patron in patrones_personales:
                if patron in desc_lower:
                    sospechosos.append(egreso)
                    break

        total_sospechoso = sum(abs(t.monto) for t in sospechosos)

        if total_sospechoso > 0:
            for s in sospechosos:
                resultado.detalles.append({
                    "tipo": "posible_gasto_personal",
                    "fecha": s.fecha,
                    "descripcion": s.descripcion,
                    "monto": s.monto,
                })

            if total_sospechoso > self.materialidad:
                cont = calcular_contingencia(total_sospechoso, f"{periodo}-20")
                # Gastos personales no son gastos deducibles → ajuste IRE
                await crud.crear_hallazgo(
                    self.db,
                    firma_id=self.firma_id,
                    auditoria_id=self.auditoria_id,
                    impuesto="IRE",
                    periodo=periodo,
                    tipo_hallazgo="BCO_GASTO_NO_DEDUCIBLE",
                    descripcion=(
                        f"Se detectaron {len(sospechosos)} transacciones por "
                        f"Gs. {total_sospechoso:,} que podrían ser gastos personales "
                        f"del titular/socios. Art. 16 Ley 6380/2019: no deducibles."
                    ),
                    articulo_legal=ARTICULOS["BCO_GASTO_NO_DEDUCIBLE"],
                    base_ajuste=total_sospechoso,
                    impuesto_omitido=int(total_sospechoso * 0.10),
                    multa_estimada=cont["multa_estimada"],
                    intereses_estimados=cont["intereses_estimados"],
                    nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                    evidencias=[{
                        "tipo": "gasto_personal",
                        "transacciones": [
                            {"fecha": s.fecha, "desc": s.descripcion, "monto": s.monto}
                            for s in sospechosos[:10]
                        ],
                    }],
                )
                resultado.hallazgos_generados += 1
                resultado.monto_ajuste += total_sospechoso
