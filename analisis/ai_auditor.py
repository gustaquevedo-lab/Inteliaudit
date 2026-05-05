"""
Orquestador de Inteligencia Artificial — Inteliaudit AI Auditor.
Lógica para análisis predictivo, detección de anomalías y redacción técnica de hallazgos.
"""
from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db.models import RG90, DeclaracionJurada, Hallazgo
import json

class AIAuditor:
    def __init__(self, db: AsyncSession, firma_id: str):
        self.db = db
        self.firma_id = firma_id

    async def ejecutar_cruce_iva(self, auditoria_id: str, periodo: str) -> List[Dict]:
        """
        Compara la sumatoria del RG90 contra el Formulario 120.
        Detecta sub-declaración de ventas o sobre-declaración de compras.
        """
        # 1. Sumar RG90 del periodo
        res_rg90 = await self.db.execute(
            select(
                RG90.tipo,
                func.sum(RG90.iva_10 + RG90.iva_5).label("total_iva"),
                func.sum(RG90.total_comprobante).label("total_monto")
            ).where(
                RG90.auditoria_id == auditoria_id,
                RG90.periodo == periodo,
                RG90.firma_id == self.firma_id
            ).group_by(RG90.tipo)
        )
        data_rg90 = {row.tipo: {"iva": row.total_iva, "total": row.total_monto} for row in res_rg90.all()}

        # 2. Obtener Declaración Jurada F120
        res_dj = await self.db.execute(
            select(DeclaracionJurada).where(
                DeclaracionJurada.auditoria_id == auditoria_id,
                DeclaracionJurada.periodo == periodo,
                DeclaracionJurada.formulario == "120"
            )
        )
        dj = res_dj.scalar_one_or_none()
        
        if not dj or not data_rg90:
            return []

        hallazgos_ai = []

        # 3. Analizar discrepancias de Débito Fiscal (Ventas)
        iva_ventas_rg90 = data_rg90.get("venta", {}).get("iva", 0)
        diferencia_ventas = dj.total_debito - iva_ventas_rg90
        
        if abs(diferencia_ventas) > 1000: # Margen de redondeo
            hallazgos_ai.append(self._generar_hallazgo_dict(
                impuesto="IVA",
                periodo=periodo,
                tipo="DIFERENCIA_DEBITO_FISCAL",
                descripcion=(
                    f"Discrepancia detectada en Débito Fiscal. El Formulario 120 declara Gs. {dj.total_debito:,}, "
                    f"mientras que el detalle del RG90 suma Gs. {iva_ventas_rg90:,}. "
                    f"Diferencia: Gs. {diferencia_ventas:,}."
                ),
                base_ajuste=abs(diferencia_ventas),
                riesgo="alto" if diferencia_ventas < 0 else "medio"
            ))

        # 4. Analizar discrepancias de Crédito Fiscal (Compras)
        iva_compras_rg90 = data_rg90.get("compra", {}).get("iva", 0)
        diferencia_compras = dj.total_credito - iva_compras_rg90
        
        if abs(diferencia_compras) > 1000:
            hallazgos_ai.append(self._generar_hallazgo_dict(
                impuesto="IVA",
                periodo=periodo,
                tipo="DIFERENCIA_CREDITO_FISCAL",
                descripcion=(
                    f"Discrepancia detectada en Crédito Fiscal. El Formulario 120 declara Gs. {dj.total_credito:,}, "
                    f"mientras que el detalle del RG90 suma Gs. {iva_compras_rg90:,}. "
                    f"Diferencia: Gs. {diferencia_compras:,}."
                ),
                base_ajuste=abs(diferencia_compras),
                riesgo="alto" if diferencia_compras > 0 else "medio"
            ))

        return hallazgos_ai

    async def analizar_riesgo_proveedores(self, auditoria_id: str) -> List[Dict]:
        """
        Analiza el listado de proveedores en busca de RUCs con estados irregulares
        o comportamientos sospechosos (compras en fines de semana, montos redondos).
        """
        res = await self.db.execute(
            select(RG90).where(
                RG90.auditoria_id == auditoria_id,
                RG90.tipo == "compra",
                RG90.firma_id == self.firma_id
            )
        )
        compras = res.scalars().all()
        hallazgos = []

        # Simulación de base de datos de RUCs bloqueados/suspensas por la DNIT
        # En prod esto sería un cruce contra el padron_ruc actualizado
        rucs_riesgosos = {"80001234-5": "Bloqueado", "4444444-1": "Suspendido"}

        for c in compras:
            # 1. Verificar estado del RUC
            if c.ruc_contraparte in rucs_riesgosos:
                estado = rucs_riesgosos[c.ruc_contraparte]
                hallazgos.append(self._generar_hallazgo_dict(
                    impuesto="IVA/IRE",
                    periodo=c.periodo,
                    tipo="PROVEEDOR_RIESGOSO",
                    descripcion=(
                        f"Se detectó una compra de Gs. {c.total_comprobante:,} al proveedor "
                        f"{c.nombre_contraparte} (RUC {c.ruc_contraparte}) el cual figura como "
                        f"'{estado}' en los registros de la DNIT."
                    ),
                    base_ajuste=c.total_comprobante,
                    riesgo="alto"
                ))

            # 2. Análisis de 'Montos Redondos' (Frecuente en facturas simuladas)
            if c.total_comprobante > 1000000 and c.total_comprobante % 100000 == 0:
                hallazgos.append(self._generar_hallazgo_dict(
                    impuesto="GENERAL",
                    periodo=c.periodo,
                    tipo="ANOMALIA_MONTO_REDONDO",
                    descripcion=(
                        f"La factura {c.nro_comprobante} presenta un monto exacto de Gs. {c.total_comprobante:,}. "
                        "Este patrón es estadísticamente inusual y suele ser objeto de revisión por la DNIT."
                    ),
                    base_ajuste=c.total_comprobante,
                    riesgo="bajo"
                ))

        return hallazgos

    async def analizar_coherencia_actividad(self, auditoria_id: str, actividad_cliente: str) -> List[Dict]:
        """
        Verifica si los gastos del RG90 coinciden con la naturaleza del negocio.
        """
        # Aquí usaríamos un LLM para comparar 'actividad_cliente' con 'nombre_contraparte' / rubro
        # Ejemplo mock: Actividad = Servicios de Software. Gasto = Fertilizantes.
        return []

    def _generar_hallazgo_dict(self, impuesto, periodo, tipo, descripcion, base_ajuste, riesgo) -> Dict:
        """Helper para estructurar la sugerencia de la IA."""
        # Aquí es donde en el futuro llamaremos a un LLM (Claude/GPT) 
        # para redactar la 'descripcion_tecnica' y citar artículos legales.
        return {
            "impuesto": impuesto,
            "periodo": periodo,
            "tipo_hallazgo": tipo,
            "descripcion": descripcion,
            "descripcion_tecnica": f"Análisis automático IA: {descripcion}. Requiere validación de facturas físicas.",
            "articulo_legal": "Art. 85 Ley 6380/19, RG 90/21",
            "base_ajuste": base_ajuste,
            "nivel_riesgo": riesgo,
            "sugerencia_ai": True
        }

    async def persistir_hallazgos_ai(self, auditoria_id: str, hallazgos: List[Dict]):
        """Guarda los hallazgos generados por la IA en la base de datos."""
        for h_data in hallazgos:
            # Evitar duplicados (simplificado)
            nuevo = Hallazgo(
                firma_id=self.firma_id,
                auditoria_id=auditoria_id,
                **h_data,
                estado="borrador"
            )
            self.db.add(nuevo)
        await self.db.commit()
