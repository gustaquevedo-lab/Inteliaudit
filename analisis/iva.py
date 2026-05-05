"""
Procedimientos de auditoría IVA.
Cruces centrales según CLAUDE.md: RG90 vs Form.120 vs SIFEN vs HECHAUKA.
"""
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo
from db import db as crud
from db.models import RG90

console = Console()

# Artículos legales por tipo de hallazgo
ARTICULOS = {
    "IVA_CREDITO_RUC_INACTIVO":       "Art. 95 Ley 6380/2019 — Requisitos crédito fiscal",
    "IVA_CREDITO_SIN_CDC":            "Art. 95 Ley 6380/2019 + RG 80/2021 — CDC obligatorio",
    "IVA_COMPROBANTE_NO_DECLARADO":   "Art. 97 Ley 6380/2019 — Obligación declaración",
    "IVA_DIFERENCIA_RG90_DJ":         "Art. 97 Ley 6380/2019 — Consistencia DJ",
    "IVA_DEBITO_OMITIDO_HECHAUKA":    "Art. 93 Ley 6380/2019 — Débito fiscal omitido",
    "IVA_NOTA_CREDITO_NO_APLICADA":   "Art. 95 Ley 6380/2019 — NC reduce crédito",
}


@dataclass
class ResultadoCruceIVA:
    periodo: str
    cruce: str
    hallazgos_generados: int = 0
    monto_ajuste: int = 0
    detalles: list[dict] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


class AuditoriaIVA:
    """
    Ejecuta todos los procedimientos de auditoría IVA para una auditoría.
    Orden obligatorio definido en CLAUDE.md.
    """

    def __init__(self, db: AsyncSession, firma_id: str, auditoria_id: str, materialidad: int = 0):
        self.db = db
        self.firma_id = firma_id
        self.auditoria_id = auditoria_id
        self.materialidad = materialidad

    async def ejecutar_auditoria_completa(
        self,
        cliente_id: str,
        periodos: list[str],
    ) -> list[ResultadoCruceIVA]:
        """
        Ejecuta los 5 cruces IVA para todos los períodos en alcance.
        Genera hallazgos automáticamente en la DB.
        """
        resultados = []
        for periodo in periodos:
            console.print(f"[blue]IVA:[/] auditando período {periodo}...")
            resultados += await self._auditar_periodo(cliente_id, periodo)
        return resultados

    async def _auditar_periodo(self, cliente_id: str, periodo: str) -> list[ResultadoCruceIVA]:
        resultados = []

        r1 = await self.cruce_rg90_vs_form120(cliente_id, periodo)
        r2 = await self.cruce_rg90_vs_sifen(cliente_id, periodo)
        r3 = await self.cruce_sifen_vs_rg90(cliente_id, periodo)
        r4 = await self.cruce_rg90_vs_hechauka(cliente_id, periodo)
        r5 = await self.cruce_ruc_proveedores(cliente_id, periodo)

        return [r1, r2, r3, r4, r5]

    # --------------------------------------------------------
    #  Cruce 1: RG90 vs Form.120
    # --------------------------------------------------------

    async def cruce_rg90_vs_form120(self, cliente_id: str, periodo: str) -> ResultadoCruceIVA:
        """
        Verifica que los totales de RG90 coincidan con lo declarado en Form.120.
        Diferencia → hallazgo IVA_DIFERENCIA_RG90_DJ.
        """
        resultado = ResultadoCruceIVA(periodo=periodo, cruce="RG90 vs Form.120")

        declaraciones = await crud.get_declaraciones(self.db, self.firma_id, cliente_id, "120", periodo)
        if not declaraciones:
            resultado.errores.append(f"No se encontró Form.120 para {periodo}")
            return resultado

        # Tomar la última rectificativa
        decl = sorted(declaraciones, key=lambda d: d.nro_rectificativa, reverse=True)[0]

        import json
        datos_dj = json.loads(decl.datos_json)

        compras = await crud.get_rg90(self.db, self.firma_id, cliente_id, periodo, "compra")
        ventas = await crud.get_rg90(self.db, self.firma_id, cliente_id, periodo, "venta")

        total_cf_rg90 = sum(c.iva_total for c in compras)
        total_df_rg90 = sum(v.iva_total for v in ventas)

        cf_declarado = int(datos_dj.get("credito_fiscal", 0))
        df_declarado = int(datos_dj.get("debito_fiscal", 0))

        diferencia_cf = abs(total_cf_rg90 - cf_declarado)
        diferencia_df = abs(total_df_rg90 - df_declarado)

        if diferencia_cf > self.materialidad:
            cont = calcular_contingencia(diferencia_cf, f"{periodo}-20")
            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="IVA",
                periodo=periodo,
                tipo_hallazgo="IVA_DIFERENCIA_RG90_DJ",
                descripcion=f"Diferencia entre crédito fiscal RG90 (Gs. {total_cf_rg90:,}) y Form.120 (Gs. {cf_declarado:,}). Diferencia: Gs. {diferencia_cf:,}",
                articulo_legal=ARTICULOS["IVA_DIFERENCIA_RG90_DJ"],
                base_ajuste=diferencia_cf,
                impuesto_omitido=diferencia_cf,
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
            )
            resultado.hallazgos_generados += 1
            resultado.monto_ajuste += diferencia_cf

        if diferencia_df > self.materialidad:
            cont = calcular_contingencia(diferencia_df, f"{periodo}-20")
            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="IVA",
                periodo=periodo,
                tipo_hallazgo="IVA_DIFERENCIA_RG90_DJ",
                descripcion=f"Diferencia entre débito fiscal RG90 (Gs. {total_df_rg90:,}) y Form.120 (Gs. {df_declarado:,}). Diferencia: Gs. {diferencia_df:,}",
                articulo_legal=ARTICULOS["IVA_DIFERENCIA_RG90_DJ"],
                base_ajuste=diferencia_df,
                impuesto_omitido=diferencia_df,
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
            )
            resultado.hallazgos_generados += 1
            resultado.monto_ajuste += diferencia_df

        return resultado

    # --------------------------------------------------------
    #  Cruce 2: RG90 compras vs SIFEN
    # --------------------------------------------------------

    async def cruce_rg90_vs_sifen(self, cliente_id: str, periodo: str) -> ResultadoCruceIVA:
        """
        Para cada comprobante con CDC en RG90, verifica que exista y sea válido en SIFEN.
        CDC no encontrado → hallazgo IVA_CREDITO_SIN_CDC (posible comprobante apócrifo).
        """
        resultado = ResultadoCruceIVA(periodo=periodo, cruce="RG90 vs SIFEN")
        compras = await crud.get_rg90(self.db, self.firma_id, cliente_id, periodo, "compra")

        for compra in compras:
            if not compra.cdc:
                # Comprobante sin CDC emitido después de obligatoriedad e-Kuatia
                if compra.fecha_emision >= "2022-01-01":
                    await self._generar_hallazgo_sin_cdc(compra)
                    resultado.hallazgos_generados += 1
                    resultado.monto_ajuste += compra.iva_total
                continue

            sifen = await crud.get_sifen_por_cdc(self.db, self.firma_id, compra.cdc)
            if not sifen:
                # CDC no consultado aún — marcar para validación posterior
                await crud.marcar_validacion_rg90(self.db, compra.id, en_sifen=None)
                continue

            if sifen.estado_sifen in ("cancelado", "inutilizado"):
                # Comprobante cancelado — crédito inválido
                cont = calcular_contingencia(compra.iva_total, compra.fecha_emision)
                await crud.crear_hallazgo(
                    self.db,
                    firma_id=self.firma_id,
                    auditoria_id=self.auditoria_id,
                    impuesto="IVA",
                    periodo=periodo,
                    tipo_hallazgo="IVA_CREDITO_SIN_CDC",
                    descripcion=f"Comprobante CDC {compra.cdc[:12]}... estado {sifen.estado_sifen} en SIFEN. Crédito fiscal inválido: Gs. {compra.iva_total:,}",
                    articulo_legal=ARTICULOS["IVA_CREDITO_SIN_CDC"],
                    base_ajuste=compra.base_gravada_10 + compra.base_gravada_5,
                    impuesto_omitido=compra.iva_total,
                    multa_estimada=cont["multa_estimada"],
                    intereses_estimados=cont["intereses_estimados"],
                    nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                    evidencias=[{"tipo": "rg90", "id": compra.id, "cdc": compra.cdc}],
                )
                resultado.hallazgos_generados += 1
                resultado.monto_ajuste += compra.iva_total

        return resultado

    # --------------------------------------------------------
    #  Cruce 3: SIFEN recibidas vs RG90 (crédito omitido)
    # --------------------------------------------------------

    async def cruce_sifen_vs_rg90(self, cliente_id: str, periodo: str) -> ResultadoCruceIVA:
        """
        Detecta facturas electrónicas recibidas en SIFEN que NO están en RG90.
        """
        resultado = ResultadoCruceIVA(periodo=periodo, cruce="SIFEN recibidas vs RG90")
        resultado.errores.append("Cruce SIFEN→RG90 requiere descarga de comprobantes recibidos desde Marangatú")
        return resultado

    # --------------------------------------------------------
    #  Cruce 4: RG90 ventas vs HECHAUKA
    # --------------------------------------------------------

    async def cruce_rg90_vs_hechauka(self, cliente_id: str, periodo: str) -> ResultadoCruceIVA:
        """
        Compara ventas declaradas en RG90 con lo que los compradores informaron en HECHAUKA.
        Ventas en HECHAUKA no en RG90 → hallazgo IVA_DEBITO_OMITIDO_HECHAUKA.
        """
        resultado = ResultadoCruceIVA(periodo=periodo, cruce="RG90 ventas vs HECHAUKA")

        ventas_rg90 = await crud.get_rg90(self.db, self.firma_id, cliente_id, periodo, "venta")
        hechauka = await crud.get_hechauka(self.db, self.firma_id, cliente_id, periodo)

        if not hechauka:
            resultado.errores.append(f"No hay datos HECHAUKA para {periodo}. Importar XLSX desde Marangatú.")
            return resultado

        # Set de comprobantes declarados en RG90 ventas
        nros_declarados = {
            f"{v.ruc_contraparte}_{v.nro_comprobante}"
            for v in ventas_rg90
        }

        total_omitido = 0
        for reg in hechauka:
            clave = f"{reg.ruc_informante}_{reg.nro_comprobante}"
            if clave not in nros_declarados and reg.iva_operacion > 0:
                total_omitido += reg.iva_operacion
                resultado.detalles.append({
                    "ruc_informante": reg.ruc_informante,
                    "nombre_informante": reg.nombre_informante,
                    "nro_comprobante": reg.nro_comprobante,
                    "iva_omitido": reg.iva_operacion,
                })

        if total_omitido > self.materialidad:
            cont = calcular_contingencia(total_omitido, f"{periodo}-20")
            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="IVA",
                periodo=periodo,
                tipo_hallazgo="IVA_DEBITO_OMITIDO_HECHAUKA",
                descripcion=f"HECHAUKA reporta {len(resultado.detalles)} comprobante(s) de venta no declarados en RG90. Débito fiscal omitido estimado: Gs. {total_omitido:,}",
                articulo_legal=ARTICULOS["IVA_DEBITO_OMITIDO_HECHAUKA"],
                base_ajuste=total_omitido * 10,
                impuesto_omitido=total_omitido,
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                evidencias=resultado.detalles[:20],
            )
            resultado.hallazgos_generados += 1
            resultado.monto_ajuste += total_omitido

        return resultado

    # --------------------------------------------------------
    #  Cruce 5: RUC proveedores activos
    # --------------------------------------------------------

    async def cruce_ruc_proveedores(self, cliente_id: str, periodo: str) -> ResultadoCruceIVA:
        """
        Verifica que los RUCs de proveedores en RG90 compras estén activos en SET.
        RUC inactivo/cancelado → crédito fiscal inválido.
        """
        resultado = ResultadoCruceIVA(periodo=periodo, cruce="RUC proveedores activos")

        compras = await crud.get_rg90(self.db, self.firma_id, cliente_id, periodo, "compra")
        compras_ruc_inactivo = [c for c in compras if c.ruc_activo is False]

        for compra in compras_ruc_inactivo:
            if compra.iva_total < self.materialidad:
                continue
            cont = calcular_contingencia(compra.iva_total, compra.fecha_emision)
            await crud.crear_hallazgo(
                self.db,
                firma_id=self.firma_id,
                auditoria_id=self.auditoria_id,
                impuesto="IVA",
                periodo=periodo,
                tipo_hallazgo="IVA_CREDITO_RUC_INACTIVO",
                descripcion=f"Crédito fiscal de Gs. {compra.iva_total:,} de proveedor RUC {compra.ruc_contraparte} ({compra.nombre_contraparte}) con estado inactivo/cancelado en SET.",
                articulo_legal=ARTICULOS["IVA_CREDITO_RUC_INACTIVO"],
                base_ajuste=compra.base_gravada_10 + compra.base_gravada_5,
                impuesto_omitido=compra.iva_total,
                multa_estimada=cont["multa_estimada"],
                intereses_estimados=cont["intereses_estimados"],
                nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
                evidencias=[{"tipo": "rg90", "id": compra.id, "ruc_proveedor": compra.ruc_contraparte}],
            )
            resultado.hallazgos_generados += 1
            resultado.monto_ajuste += compra.iva_total

        return resultado

    # --------------------------------------------------------
    #  Helpers internos
    # --------------------------------------------------------

    async def _generar_hallazgo_sin_cdc(self, compra: RG90) -> None:
        cont = calcular_contingencia(compra.iva_total, compra.fecha_emision)
        await crud.crear_hallazgo(
            self.db,
            firma_id=self.firma_id,
            auditoria_id=self.auditoria_id,
            impuesto="IVA",
            periodo=compra.periodo,
            tipo_hallazgo="IVA_CREDITO_SIN_CDC",
            descripcion=f"Comprobante {compra.nro_comprobante} de {compra.nombre_contraparte} (RUC {compra.ruc_contraparte}) sin CDC siendo posterior a obligatoriedad e-Kuatia. Crédito fiscal en riesgo: Gs. {compra.iva_total:,}",
            articulo_legal=ARTICULOS["IVA_CREDITO_SIN_CDC"],
            base_ajuste=compra.base_gravada_10 + compra.base_gravada_5,
            impuesto_omitido=compra.iva_total,
            multa_estimada=cont["multa_estimada"],
            intereses_estimados=cont["intereses_estimados"],
            nivel_riesgo=clasificar_riesgo(cont["total_contingencia"], self.materialidad),
            evidencias=[{"tipo": "rg90", "id": compra.id}],
        )
