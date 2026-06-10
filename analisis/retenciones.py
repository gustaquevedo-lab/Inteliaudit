"""
Procedimientos de auditoria de Retenciones IVA e IRE.
Formularios 800-830. Cruces con HECHAUKA.
"""
import re
from dataclasses import dataclass, field

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo
from db import db as crud

console = Console()

TASAS_RETENCION = {
    "iva_servicios_personales":   0.03,
    "iva_compras_normal":         0.03,
    "ire_honorarios":             0.03,
    "pequenos_iva":               0.30,
    "pequenos_ire":               0.025,
}

MULTA_RETENCION_DIA = 0.001
MULTA_RETENCION_MAX = 0.20

ARTICULOS = {
    "RET_NO_PRACTICADA":        "Art. 159 Ley 6380/2019 — Obligacion agente de retencion",
    "RET_NO_DEPOSITADA":        "Art. 175 Ley 125/1991 — Multa 0.1% diaria hasta 20%",
    "RET_DIFERENCIA_HECHAUKA":  "Art. 159 Ley 6380/2019 — Consistencia retenciones declaradas",
}

UMBRAL_SERVICIOS_PERSONALES = 1000000


@dataclass
class ResultadoAuditoriaRetenciones:
    periodo: str
    hallazgos_generados: int = 0
    retenciones_omitidas: int = 0
    retenciones_no_depositadas: int = 0
    detalles: list[dict] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


class AuditoriaRetenciones:

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
            console.print(f"[blue]Retenciones:[/] auditando periodo {periodo}...")
            resultados.append(await self.auditar_periodo(cliente_id, periodo))
        return resultados

    async def auditar_periodo(self, cliente_id: str, periodo: str) -> ResultadoAuditoriaRetenciones:
        resultado = ResultadoAuditoriaRetenciones(periodo=periodo)

        h1 = await self.cruce_hechauka_vs_declaraciones(cliente_id, periodo)
        h2 = await self.verificar_retenciones_omitidas(cliente_id, periodo)

        resultado.hallazgos_generados = h1 + h2
        return resultado

    async def _get_forms_retencion(self, cliente_id: str, periodo: str):
        """Obtiene todos los formularios de retencion (800, 810, 820, 830) del periodo."""
        forms = []
        for f in ("800", "810", "820", "830"):
            decls = await crud.get_declaraciones(self.db, self.firma_id, cliente_id, f, periodo)
            for d in decls:
                forms.append(d)
        return sorted(forms, key=lambda d: d.nro_rectificativa, reverse=True) if forms else []

    async def cruce_hechauka_vs_declaraciones(self, cliente_id: str, periodo: str) -> int:
        """
        Compara retenciones en HECHAUKA contra las declaradas en Forms. 800/820/830.
        Detecta retenciones no depositadas y diferencias con lo declarado por terceros.
        """
        hechauka = await crud.get_hechauka(self.db, self.firma_id, cliente_id, periodo)
        if not hechauka:
            return 0

        # Retenciones segun HECHAUKA
        total_ret_iva = sum(h.retencion_iva for h in hechauka)
        total_ret_ire = sum(h.retencion_ire for h in hechauka)

        # Retenciones declaradas en Forms. 800/820/830
        forms = await self._get_forms_retencion(cliente_id, periodo)
        total_ret_iva_declarado = 0
        total_ret_ire_declarado = 0

        import json
        for f in forms:
            datos = json.loads(f.datos_json)
            total_ret_iva_declarado += int(datos.get("retencion_iva", datos.get("total_retencion_iva", 0)))
            total_ret_ire_declarado += int(datos.get("retencion_ire", datos.get("total_retencion_ire", 0)))

        hallazgos = 0

        # Diferencias en IVA
        diff_iva = abs(total_ret_iva - total_ret_iva_declarado)
        if diff_iva > self.materialidad and (total_ret_iva > 0 or total_ret_iva_declarado > 0):
            cont = calcular_contingencia(diff_iva, f"{periodo}-20")
            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="RETENCIONES",
                periodo=periodo,
                tipo_hallazgo="RET_DIFERENCIA_HECHAUKA",
                descripcion=f"Diferencia en retenciones IVA: HECHAUKA reporta Gs. {total_ret_iva:,} vs declarado Gs. {total_ret_iva_declarado:,}. Diferencia: Gs. {diff_iva:,}",
                articulo_legal=ARTICULOS["RET_DIFERENCIA_HECHAUKA"],
                base_ajuste=diff_iva,
                impuesto_omitido=diff_iva,
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
            )
            hallazgos += 1

        # Diferencias en IRE
        diff_ire = abs(total_ret_ire - total_ret_ire_declarado)
        if diff_ire > self.materialidad and (total_ret_ire > 0 or total_ret_ire_declarado > 0):
            cont = calcular_contingencia(diff_ire, f"{periodo}-20")
            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="RETENCIONES",
                periodo=periodo,
                tipo_hallazgo="RET_DIFERENCIA_HECHAUKA",
                descripcion=f"Diferencia en retenciones IRE: HECHAUKA reporta Gs. {total_ret_ire:,} vs declarado Gs. {total_ret_ire_declarado:,}. Diferencia: Gs. {diff_ire:,}",
                articulo_legal=ARTICULOS["RET_DIFERENCIA_HECHAUKA"],
                base_ajuste=diff_ire,
                impuesto_omitido=diff_ire,
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
            )
            hallazgos += 1

        # Retenciones en HECHAUKA sin formularios presentados
        if (total_ret_iva > 0 or total_ret_ire > 0) and not forms:
            total_no_declarado = total_ret_iva + total_ret_ire
            cont = calcular_contingencia(total_no_declarado, f"{periodo}-20")
            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="RETENCIONES",
                periodo=periodo,
                tipo_hallazgo="RET_NO_DEPOSITADA",
                descripcion=f"HECHAUKA reporta Gs. {total_no_declarado:,} en retenciones sin formulario de declaracion presentado (800/810/820/830) para {periodo}.",
                articulo_legal=ARTICULOS["RET_NO_DEPOSITADA"],
                base_ajuste=total_no_declarado,
                impuesto_omitido=total_no_declarado,
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
            )
            hallazgos += 1

        return hallazgos

    async def verificar_retenciones_omitidas(self, cliente_id: str, periodo: str) -> int:
        """
        Busca pagos a proveedores de servicios personales sin retencion practicada.
        Si el proveedor es persona fisica y el monto > umbral, debio retener.
        """
        compras = await crud.get_rg90(self.db, self.firma_id, cliente_id, periodo, "compra")
        if not compras:
            return 0

        hallazgos = 0

        # RUCs de persona fisica: formato tipico XXXXXXX-D con D que no es de empresa
        rucs_persona_fisica = []

        # Analizar RUCs de proveedores para detectar presuntas personas fisicas
        for c in compras:
            if c.iva_total > UMBRAL_SERVICIOS_PERSONALES and c.ruc_contraparte:
                ruc_limpio = re.sub(r"[^\d]", "", c.ruc_contraparte)
                if len(ruc_limpio) <= 8:
                    rucs_persona_fisica.append(c)

        # Verificar si ya se practico retencion (buscando en HECHAUKA)
        hechauka = await crud.get_hechauka(self.db, self.firma_id, cliente_id, periodo)

        for compra in rucs_persona_fisica[:20]:
            ya_retenido = any(
                h.ruc_informante == compra.ruc_contraparte and
                h.retencion_iva > 0
                for h in hechauka
            )
            if ya_retenido:
                continue

            # Determinar la retencion que debio practicarse
            iva_incluido = int(compra.iva_total)
            base_retencion = int(compra.total_comprobante)
            retencion_debida = int(base_retencion * TASAS_RETENCION["iva_servicios_personales"])

            if retencion_debida <= 0:
                continue

            cont = calcular_contingencia(retencion_debida, compra.fecha_emision)

            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="RETENCIONES",
                periodo=periodo,
                tipo_hallazgo="RET_NO_PRACTICADA",
                descripcion=f"Pago a proveedor RUC {compra.ruc_contraparte} ({compra.nombre_contraparte or 's/n'}) por Gs. {compra.total_comprobante:,} sin retencion. Retencion omitida estimada: Gs. {retencion_debida:,}",
                articulo_legal=ARTICULOS["RET_NO_PRACTICADA"],
                base_ajuste=base_retencion,
                impuesto_omitido=retencion_debida,
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                evidencias=[{"tipo": "rg90", "id": compra.id, "ruc_proveedor": compra.ruc_contraparte}],
            )
            hallazgos += 1

        return hallazgos

    @staticmethod
    def calcular_retencion_iva(importe_bruto: int, tipo: str = "servicios_personales") -> dict:
        iva_incluido = int(importe_bruto / 11 * 1)
        retencion = int(importe_bruto * TASAS_RETENCION.get(f"iva_{tipo}", 0.03))
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
