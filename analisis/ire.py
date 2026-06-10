"""
Procedimientos de auditoria IRE — Impuesto a la Renta Empresarial.
Formulario 500. Ley 6380/2019 Art. 15-17, Decreto 3107/2019.
"""
import json
from dataclasses import dataclass, field

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo
from db import db as crud

console = Console()

TASAS_DEPRECIACION = {
    "inmuebles":            0.025,
    "maquinaria":           0.10,
    "vehiculos":            0.20,
    "equipos_informaticos": 0.333,
    "muebles_utiles":       0.10,
    "instalaciones":        0.10,
}

ALICUOTA_IRE = 0.10

ARTICULOS = {
    "IRE_GASTO_NO_DEDUCIBLE":    "Art. 16 Ley 6380/2019 — Gastos no deducibles",
    "IRE_DEPRECIACION_EXCEDIDA": "Art. 24 Decreto 3107/2019 — Tasas maximas depreciacion",
    "IRE_INGRESO_NO_DECLARADO":  "Art. 15 Ley 6380/2019 — Hecho generador IRE",
    "IRE_GASTO_SIN_COMPROBANTE": "Art. 16 inc. f) Ley 6380/2019 — Comprobante legal obligatorio",
    "IRE_PARTE_VINCULADA":       "Art. 35 Ley 6380/2019 — Precios de transferencia",
}


@dataclass
class ResultadoAuditoriaIRE:
    ejercicio: str
    hallazgos_generados: int = 0
    ajuste_renta_neta: int = 0
    impuesto_adicional: int = 0
    detalles: list[dict] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


class AuditoriaIRE:

    def __init__(self, db: AsyncSession, firma_id: str, auditoria_id: str, materialidad: int = 0):
        self.db = db
        self.firma_id = firma_id
        self.auditoria_id = auditoria_id
        self.materialidad = materialidad

    async def ejecutar_auditoria(self, cliente_id: str, ejercicio: str) -> ResultadoAuditoriaIRE:
        resultado = ResultadoAuditoriaIRE(ejercicio=ejercicio)
        console.print(f"[blue]IRE:[/] auditando ejercicio {ejercicio}...")

        h1 = await self.verificar_depreciaciones(cliente_id, ejercicio)
        h2 = await self.verificar_gastos_sin_comprobante(cliente_id, ejercicio)
        h3 = await self.conciliar_resultado_contable(cliente_id, ejercicio)

        resultado.hallazgos_generados = h1 + h2 + h3
        return resultado

    async def _get_form_500(self, cliente_id: str, ejercicio: str):
        """Obtiene el Form.500 mas reciente para el ejercicio."""
        decls = await crud.get_declaraciones(self.db, self.firma_id, cliente_id, "500", ejercicio)
        if not decls:
            return None, {}
        decl = sorted(decls, key=lambda d: d.nro_rectificativa, reverse=True)[0]
        return decl, json.loads(decl.datos_json)

    async def conciliar_resultado_contable(self, cliente_id: str, ejercicio: str) -> int:
        """Cruza ingresos declarados en Form.500 vs ventas en RG90 del mismo ejercicio."""
        decl, datos = await self._get_form_500(cliente_id, ejercicio)
        if not decl:
            console.print(f"[yellow]IRE {ejercicio}: no se encontro Form.500[/]")
            return 0

        total_ingresos = int(datos.get("total_ingresos", datos.get("ingresos_brutos", 0)))
        renta_neta = int(datos.get("renta_neta", datos.get("renta_neta_imponible", 0)))
        gastos = int(datos.get("total_gastos", datos.get("gastos_deducidos", 0)))

        if not total_ingresos:
            return 0

        # Sumar ventas de RG90 para todo el ejercicio
        total_ventas_rg90 = 0
        for mes in range(1, 13):
            p = f"{ejercicio}-{mes:02d}"
            ventas = await crud.get_rg90(self.db, self.firma_id, cliente_id, p, "venta")
            total_ventas_rg90 += sum(v.iva_total for v in ventas)

        diferencia = abs(total_ingresos - total_ventas_rg90)

        if diferencia > self.materialidad and total_ventas_rg90 > 0:
            impuesto_omitido = int(diferencia * ALICUOTA_IRE)
            cont = calcular_contingencia(impuesto_omitido, f"{ejercicio}-12-31")
            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="IRE",
                periodo=ejercicio,
                tipo_hallazgo="IRE_INGRESO_NO_DECLARADO",
                descripcion=f"Ingresos declarados en Form.500 (Gs. {total_ingresos:,}) difieren de ventas RG90 (Gs. {total_ventas_rg90:,}). Diferencia: Gs. {diferencia:,}",
                articulo_legal=ARTICULOS["IRE_INGRESO_NO_DECLARADO"],
                base_ajuste=diferencia,
                impuesto_omitido=impuesto_omitido,
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
            )
            return 1
        return 0

    async def verificar_depreciaciones(self, cliente_id: str, ejercicio: str) -> int:
        """Verifica depreciacion contra tasas maximas del Decreto 3107."""
        decl, datos = await self._get_form_500(cliente_id, ejercicio)
        if not decl:
            return 0

        depreciaciones = datos.get("depreciaciones", datos.get("depreciacion", {}))
        if not depreciaciones or not isinstance(depreciaciones, dict):
            return 0

        hallazgos = 0
        for categoria, valor_anual in depreciaciones.items():
            cat = categoria.lower().replace(" ", "_").replace("-", "_")
            tasa_max = TASAS_DEPRECIACION.get(cat)
            if not tasa_max:
                continue

            valor_activo = int(datos.get(f"valor_{categoria}", 0)) or int(valor_anual / tasa_max) if tasa_max else 0
            if valor_activo <= 0:
                continue

            tasa_real = valor_anual / valor_activo if valor_activo > 0 else 0
            if tasa_real > tasa_max:
                exceso = int(valor_anual - (valor_activo * tasa_max))
                impuesto_omitido = int(exceso * ALICUOTA_IRE)
                cont = calcular_contingencia(impuesto_omitido, f"{ejercicio}-12-31")

                await crud.crear_hallazgo(
                    self.db,
                    firma_id=self.firma_id,
                    auditoria_id=self.auditoria_id,
                    impuesto="IRE",
                    periodo=ejercicio,
                    tipo_hallazgo="IRE_DEPRECIACION_EXCEDIDA",
                    descripcion=f"Depreciacion de {categoria}: tasa aplicada {tasa_real:.1%} supera tasa maxima {tasa_max:.1%}. Exceso: Gs. {exceso:,}",
                    articulo_legal=ARTICULOS["IRE_DEPRECIACION_EXCEDIDA"],
                    base_ajuste=exceso,
                    impuesto_omitido=impuesto_omitido,
                    multa_estimada=cont["multa_estimada"],
                    intereses_estimados=cont["intereses_estimados"],
                    nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                )
                hallazgos += 1

        return hallazgos

    async def verificar_gastos_sin_comprobante(self, cliente_id: str, ejercicio: str) -> int:
        """Compara gastos declarados en Form.500 vs comprobantes de compra en RG90."""
        decl, datos = await self._get_form_500(cliente_id, ejercicio)
        if not decl:
            return 0

        gastos_declarados = int(datos.get("total_gastos", datos.get("gastos_deducidos", 0)))
        if not gastos_declarados:
            return 0

        # Sumar compras RG90 de todo el ejercicio
        total_compras_rg90 = 0
        for mes in range(1, 13):
            p = f"{ejercicio}-{mes:02d}"
            compras = await crud.get_rg90(self.db, self.firma_id, cliente_id, p, "compra")
            total_compras_rg90 += sum(c.total_comprobante for c in compras)

        max_admitido = int(total_compras_rg90 * 1.1)
        diferencia = gastos_declarados - max_admitido

        if diferencia > self.materialidad and total_compras_rg90 > 0:
            impuesto_omitido = int(diferencia * ALICUOTA_IRE)
            cont = calcular_contingencia(impuesto_omitido, f"{ejercicio}-12-31")

            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="IRE",
                periodo=ejercicio,
                tipo_hallazgo="IRE_GASTO_SIN_COMPROBANTE",
                descripcion=f"Gastos declarados en Form.500 (Gs. {gastos_declarados:,}) superan comprobantes RG90 (Gs. {total_compras_rg90:,}). Diferencia sin respaldo: Gs. {diferencia:,}",
                articulo_legal=ARTICULOS["IRE_GASTO_SIN_COMPROBANTE"],
                base_ajuste=diferencia,
                impuesto_omitido=impuesto_omitido,
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
            )
            return 1
        return 0

    @staticmethod
    def verificar_limite_representacion(ingresos_brutos: int, gastos_representacion: int) -> dict:
        limite = int(ingresos_brutos * 0.01)
        exceso = max(0, gastos_representacion - limite)
        ajuste_ire = int(exceso * ALICUOTA_IRE)
        return {
            "gastos_declarados": gastos_representacion,
            "limite_admitido": limite,
            "exceso": exceso,
            "ajuste_ire": ajuste_ire,
        }

    @staticmethod
    def verificar_limite_donaciones(renta_bruta: int, donaciones: int) -> dict:
        limite = int(renta_bruta * 0.01)
        exceso = max(0, donaciones - limite)
        ajuste_ire = int(exceso * ALICUOTA_IRE)
        return {
            "donaciones_declaradas": donaciones,
            "limite_admitido": limite,
            "exceso": exceso,
            "ajuste_ire": ajuste_ire,
        }

    @staticmethod
    def calcular_depreciacion_maxima(valor_activo: int, categoria: str, años_usados: int = 0) -> dict:
        tasa = TASAS_DEPRECIACION.get(categoria.lower(), 0.10)
        vida_util = int(1 / tasa)
        cuota_anual = int(valor_activo * tasa)
        años_restantes = max(0, vida_util - años_usados)
        return {
            "categoria": categoria,
            "tasa_maxima": tasa,
            "vida_util_años": vida_util,
            "cuota_anual_maxima": cuota_anual,
            "años_restantes": años_restantes,
            "valor_libro": int(valor_activo * (1 - tasa * años_usados)),
        }
