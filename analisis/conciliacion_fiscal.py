"""
Conciliación contable → fiscal (IRE).
Reconciliación entre resultado contable y base imponible del IRE.

Procedimientos:
1. Partida por partida: resultado contable → renta neta imponible
2. Identificación de gastos no deducibles (Art. 16 Ley 6380/2019)
3. Ajustes extracontables (depreciación, provisiones, etc.)
4. Diferencias permanentes vs temporarias
5. Verificación de tasas de depreciación (Decreto 3107/2019)
"""
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo, formatear_pyg
from db import db as crud

console = Console()

ARTICULOS = {
    "IRE_GASTO_NO_DEDUCIBLE": "Art. 16 Ley 6380/2019 — Gastos no deducibles",
    "IRE_DEPREC_EXCESO": "Art. 16 Ley 6380/2019 + Decreto 3107/2019 — Tasas de depreciación",
    "IRE_VINCULADA": "Art. 35 Ley 6380/2019 — Partes vinculadas (arm's length)",
    "IRE_BASE_IMPONIBLE": "Art. 14 Ley 6380/2019 — Determinación renta neta",
    "IRE_DONACION_EXCESO": "Art. 16 Ley 6380/2019 — Donaciones > 1% renta bruta",
}

# Tasas máximas de depreciación (Decreto 3107/2019)
TASAS_DEPRECIACION = {
    "inmuebles": 0.025,         # 2.5% anual (40 años)
    "maquinaria": 0.10,         # 10% anual (10 años)
    "vehiculos": 0.20,          # 20% anual (5 años)
    "equipos_informaticos": 0.333,  # 33.3% anual (3 años)
    "muebles_utiles": 0.10,     # 10% anual (10 años)
    "instalaciones": 0.10,      # 10% anual (10 años)
}

# Gastos no deducibles del Art. 16
GASTOS_NO_DEDUCIBLES = {
    "multas": "Multas y recargos pagados a SET",
    "intereses_mora": "Intereses moratorios pagados a SET",
    "gastos_personales": "Gastos personales del dueño/socios",
    "retiros": "Retiros de socios",
    "donaciones_exceso": "Donaciones que superan 1% renta bruta",
    "gastos_representacion_exceso": "Gastos de representación > 1% ingresos brutos",
    "intereses_vinculadas_exceso": "Intereses a partes vinculadas > LIBOR + 3%",
}


@dataclass
class AjusteExtracontable:
    concepto: str
    tipo: str  # "suma" | "resta"
    monto: int
    articulo_legal: str
    es_permanente: bool = True  # True = permanente, False = temporal
    descripcion: str = ""


@dataclass
class ResultadoConciliacionFiscal:
    periodo: str
    procedimiento: str
    resultado_contable: int = 0
    ajustes_suma: int = 0  # gastos no deducibles, etc.
    ajustes_resta: int = 0  # ingresos exentos, etc.
    renta_neta_imponible: int = 0
    impuesto_esperado: int = 0
    impuesto_declarado: int = 0
    diferencia: int = 0
    ajustes: list[AjusteExtracontable] = field(default_factory=list)
    hallazgos_generados: int = 0
    monto_ajuste: int = 0
    errores: list[str] = field(default_factory=list)


class ConciliacionFiscal:
    """
    Ejecuta la conciliación contable → fiscal (IRE).
    
    Flujo:
    1. Obtener resultado contable del período
    2. Identificar gastos no deducibles
    3. Calcular depreciaciones
    4. Verificar donaciones
    5. Detectar operaciones con vinculadas
    6. Calcular renta neta imponible
    7. Comparar con IRE declarado
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
        resultado_contable: int = 0,
        gastos_operativos: Optional[dict] = None,
    ) -> ResultadoConciliacionFiscal:
        """
        Ejecuta la conciliación contable → fiscal.
        
        Args:
            cliente_id: ID del cliente
            periodo: Período YYYY-MM (o ejercicio fiscal YYYY)
            resultado_contable: Resultado antes de impuestos (contable)
            gastos_operativos: Desglose de gastos para análisis de deducibilidad
        """
        resultado = ResultadoConciliacionFiscal(
            periodo=periodo,
            procedimiento="Conciliación Contable → Fiscal (IRE)"
        )

        resultado.resultado_contable = resultado_contable

        cliente = await crud.get_cliente(self.db, self.firma_id, id=cliente_id)
        if not cliente:
            resultado.errores.append("Cliente no encontrado")
            return resultado

        # Obtener datos del período
        declaraciones_ire = await crud.get_declaraciones(
            self.db, self.firma_id, cliente_id, "500", periodo
        )

        if declaraciones_ire:
            import json
            decl = sorted(declaraciones_ire, key=lambda d: d.nro_rectificativa, reverse=True)[0]
            datos = json.loads(decl.datos_json)
            resultado.impuesto_declarado = int(datos.get("ire_a_pagar", 0))

        # =========================================================
        # 1. Analizar gastos no deducibles
        # =========================================================
        if gastos_operativos:
            await self._analizar_gastos_no_deducibles(gastos_operativos, resultado)

        # =========================================================
        # 2. Obtener RG90 para análisis de compras
        # =========================================================
        rg90_compras = await crud.get_rg90(
            self.db, self.firma_id, cliente_id, periodo, "compra"
        )

        # =========================================================
        # 3. Verificar gastos con comprobantes de RUC inactivo
        # =========================================================
        await self._verificar_comprobantes_ruc_inactivo(rg90_compras, resultado)

        # =========================================================
        # 4. Calcular renta neta imponible
        # =========================================================
        resultado.renta_neta_imponible = (
            resultado.resultado_contable
            + resultado.ajustes_suma
            - resultado.ajustes_resta
        )

        # =========================================================
        # 5. Calcular IRE esperado (10%)
        # =========================================================
        if resultado.renta_neta_imponible > 0:
            resultado.impuesto_esperado = int(resultado.renta_neta_imponible * 0.10)

        # =========================================================
        # 6. Comparar con IRE declarado
        # =========================================================
        resultado.diferencia = resultado.impuesto_esperado - resultado.impuesto_declarado

        if abs(resultado.diferencia) > self.materialidad:
            cont = calcular_contingencia(abs(resultado.diferencia), f"{periodo}-20")
            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="IRE",
                periodo=periodo,
                tipo_hallazgo="IRE_BASE_IMPONIBLE",
                descripcion=(
                    f"Conciliación contable→fiscal:\n"
                    f"Resultado contable: Gs. {resultado.resultado_contable:,}\n"
                    f"Ajustes (+): Gs. {resultado.ajustes_suma:,}\n"
                    f"Ajustes (-): Gs. {resultado.ajustes_resta:,}\n"
                    f"Renta neta imponible: Gs. {resultado.renta_neta_imponible:,}\n"
                    f"IRE esperado (10%): Gs. {resultado.impuesto_esperado:,}\n"
                    f"IRE declarado: Gs. {resultado.impuesto_declarado:,}\n"
                    f"Diferencia: Gs. {resultado.diferencia:,}"
                ),
                articulo_legal=ARTICULOS["IRE_BASE_IMPONIBLE"],
                base_ajuste=resultado.renta_neta_imponible,
                impuesto_omitido=abs(resultado.diferencia),
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                evidencias=[{
                    "tipo": "conciliacion_fiscal",
                    "resultado_contable": resultado.resultado_contable,
                    "ajustes_suma": resultado.ajustes_suma,
                    "ajustes_resta": resultado.ajustes_resta,
                    "renta_neta": resultado.renta_neta_imponible,
                    "ire_esperado": resultado.impuesto_esperado,
                    "ire_declarado": resultado.impuesto_declarado,
                }],
            )
            resultado.hallazgos_generados += 1
            resultado.monto_ajuste = abs(resultado.diferencia)

        return resultado

    async def _analizar_gastos_no_deducibles(
        self,
        gastos: dict,
        resultado: ResultadoConciliacionFiscal,
    ):
        """Analiza gastos y identifica los no deducibles."""
        for concepto, monto in gastos.items():
            concepto_lower = concepto.lower()
            
            # Detectar gastos no deducibles
            es_no_deducible = False
            articulo = ""
            
            if "multa" in concepto_lower or "recargo" in concepto_lower:
                es_no_deducible = True
                articulo = GASTOS_NO_DEDUCIBLES["multas"]
            elif "interes" in concepto_lower and "mora" in concepto_lower:
                es_no_deducible = True
                articulo = GASTOS_NO_DEDUCIBLES["intereses_mora"]
            elif "personal" in concepto_lower or "dueño" in concepto_lower or "socio" in concepto_lower:
                es_no_deducible = True
                articulo = GASTOS_NO_DEDUCIBLES["gastos_personales"]
            elif "retiro" in concepto_lower:
                es_no_deducible = True
                articulo = GASTOS_NO_DEDUCIBLES["retiros"]
            elif "donacion" in concepto_lower or "donación" in concepto_lower:
                # Verificar si supera 1% de renta bruta
                if resultado.resultado_contable > 0:
                    limite_donaciones = int(resultado.resultado_contable * 0.01)
                    if monto > limite_donaciones:
                        excedente = monto - limite_donaciones
                        es_no_deducible = True
                        articulo = GASTOS_NO_DEDUCIBLES["donaciones_exceso"]
                        monto = excedente  # Solo el excedente es no deducible

            if es_no_deducible and monto > 0:
                resultado.ajustes.append(AjusteExtracontable(
                    concepto=concepto,
                    tipo="suma",
                    monto=monto,
                    articulo_legal=articulo,
                    es_permanente=True,
                    descripcion=f"Gasto no deducible: {concepto}",
                ))
                resultado.ajustes_suma += monto

    async def _verificar_comprobantes_ruc_inactivo(
        self,
        rg90_compras: list,
        resultado: ResultadoConciliacionFiscal,
    ):
        """Verifica que los comprobantes de compra no tengan RUC inactivo."""
        compras_ruc_inactivo = [c for c in rg90_compras if c.ruc_activo is False]
        
        total_inactivo = sum(c.iva_total for c in compras_ruc_inactivo)
        
        if total_inactivo > 0:
            resultado.ajustes.append(AjusteExtracontable(
                concepto="Compras con RUC proveedor inactivo",
                tipo="suma",
                monto=total_inactivo,
                articulo_legal=ARTICULOS["IRE_GASTO_NO_DEDUCIBLE"],
                es_permanente=True,
                descripcion=(
                    f"{len(compras_ruc_inactivo)} compras por Gs. {total_inactivo:,} "
                    f"con RUC de proveedor inactivo/cancelado"
                ),
            ))
            resultado.ajustes_suma += total_inactivo
