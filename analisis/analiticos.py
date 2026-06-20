"""
Procedimientos analíticos de auditoría impositiva.
Análisis de ratios, tendencias y detección de anomalías.

Procedimientos:
1. Análisis de rentabilidad (margen bruto, neto)
2. Análisis de liquidez y solvencia
3. Tendencias período a período
4. Detección de anomalías estadísticas
5. Comparación con benchmarks de industria
"""
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import formatear_pyg
from db import db as crud

console = Console()


@dataclass
class RatioAnalitico:
    nombre: str
    valor: float
    unidad: str  # "%" | "veces" | "dias"
    periodo: str
    benchmark_min: Optional[float] = None
    benchmark_max: Optional[float] = None
    dentro_rango: Optional[bool] = None
    observacion: Optional[str] = None


@dataclass
class ResultadoAnalitico:
    periodo: str
    procedimiento: str
    ratios: list[RatioAnalitico] = field(default_factory=list)
    anomalias: list[dict] = field(default_factory=list)
    tendencias: list[dict] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    errores: list[str] = field(default_factory=list)


# Benchmarks por tipo de actividad económica (Paraguay)
BENCHMARKS = {
    "comercio": {
        "margen_bruto": (0.10, 0.35),
        "margen_net": (0.02, 0.12),
        "razon_corriente": (1.0, 3.0),
        "razon_endeudamiento": (0.2, 0.8),
        "rotacion_inventario": (4, 12),
    },
    "servicios": {
        "margen_bruto": (0.30, 0.70),
        "margen_net": (0.05, 0.25),
        "razon_corriente": (1.0, 4.0),
        "razon_endeudamiento": (0.1, 0.6),
    },
    "industria": {
        "margen_bruto": (0.15, 0.45),
        "margen_net": (0.03, 0.15),
        "razon_corriente": (1.0, 2.5),
        "razon_endeudamiento": (0.3, 0.7),
        "rotacion_inventario": (3, 8),
    },
}


class ProcedimientosAnaliticos:
    """Ejecuta procedimientos analíticos de auditoría."""

    def __init__(self, db: AsyncSession, firma_id: str, auditoria_id: str, materialidad: int = 0):
        self.db = db
        self.firma_id = firma_id
        self.auditoria_id = auditoria_id
        self.materialidad = materialidad

    async def ejecutar(
        self,
        cliente_id: str,
        periodo_actual: str,
        periodo_anterior: Optional[str] = None,
    ) -> ResultadoAnalitico:
        """
        Ejecuta todos los procedimientos analíticos.
        
        Args:
            cliente_id: ID del cliente
            periodo_actual: Período YYYY-MM a analizar
            periodo_anterior: Período anterior para comparación (opcional)
        """
        resultado = ResultadoAnalitico(
            periodo=periodo_actual,
            procedimiento="Procedimientos Analíticos"
        )

        cliente = await crud.get_cliente(self.db, self.firma_id, id=cliente_id)
        if not cliente:
            resultado.errores.append("Cliente no encontrado")
            return resultado

        # Obtener datos del período actual
        datos_actual = await self._obtener_datos_periodo(cliente_id, periodo_actual)
        datos_anterior = None
        if periodo_anterior:
            datos_anterior = await self._obtener_datos_periodo(cliente_id, periodo_anterior)

        # 1. Calcular ratios
        ratios = self._calcular_ratios(datos_actual, periodo_actual, cliente.actividad_principal)
        resultado.ratios = ratios

        # 2. Comparar con benchmarks
        self._comparar_benchmarks(resultado, cliente.actividad_principal)

        # 3. Análisis de tendencias
        if datos_anterior:
            tendencias = self._analizar_tendencias(datos_actual, datos_anterior, periodo_actual)
            resultado.tendencias = tendencias

        # 4. Detectar anomalías
        anomalias = self._detectar_anomalias(datos_actual, ratios)
        resultado.anomalias = anomalias

        # 5. Generar alertas
        self._generar_alertas(resultado)

        return resultado

    async def _obtener_datos_periodo(self, cliente_id: str, periodo: str) -> dict:
        """Obtiene datos financieros del período desde RG90 y declaraciones."""
        # Ventas (ingresos)
        rg90_ventas = await crud.get_rg90(
            self.db, self.firma_id, cliente_id, periodo, "venta"
        )
        total_ventas = sum(v.total_comprobante for v in rg90_ventas)
        iva_ventas = sum(v.iva_total for v in rg90_ventas)
        ventas_gravadas_10 = sum(v.base_gravada_10 for v in rg90_ventas)
        ventas_gravadas_5 = sum(v.base_gravada_5 for v in rg90_ventas)
        ventas_exentas = sum(v.monto_exento for v in rg90_ventas)

        # Compras (costos)
        rg90_compras = await crud.get_rg90(
            self.db, self.firma_id, cliente_id, periodo, "compra"
        )
        total_compras = sum(c.total_comprobante for c in rg90_compras)
        iva_compras = sum(c.iva_total for c in rg90_compras)

        # IVA pagado/devuelto
        declaraciones_iva = await crud.get_declaraciones(
            self.db, self.firma_id, cliente_id, "120", periodo
        )
        import json
        iva_a_pagar = 0
        if declaraciones_iva:
            decl = sorted(declaraciones_iva, key=lambda d: d.nro_rectificativa, reverse=True)[0]
            datos = json.loads(decl.datos_json)
            iva_a_pagar = int(datos.get("iva_a_pagar", 0))

        return {
            "total_ventas": total_ventas,
            "iva_ventas": iva_ventas,
            "ventas_gravadas_10": ventas_gravadas_10,
            "ventas_gravadas_5": ventas_gravadas_5,
            "ventas_exentas": ventas_exentas,
            "total_compras": total_compras,
            "iva_compras": iva_compras,
            "iva_a_pagar": iva_a_pagar,
            "utilidad_bruta": total_ventas - total_compras,
            "nro_proveedores_unicos": len(set(c.ruc_contraparte for c in rg90_compras)),
            "nro_clientes_unicos": len(set(v.ruc_contraparte for v in rg90_ventas)),
        }

    def _calcular_ratios(self, datos: dict, periodo: str, actividad: str) -> list[RatioAnalitico]:
        """Calcula ratios financieros e impositivos."""
        ratios = []

        # Margen bruto
        if datos["total_ventas"] > 0:
            margen_bruto = datos["utilidad_bruta"] / datos["total_ventas"]
            ratios.append(RatioAnalitico(
                nombre="Margen Bruto",
                valor=round(margen_bruto * 100, 2),
                unidad="%",
                periodo=periodo,
                observacion=f"Utilidad bruta / Ventas totales",
            ))

        # Participación IVA (IVA pagado / ventas gravadas)
        ventas_gravadas = datos["ventas_gravadas_10"] + datos["ventas_gravadas_5"]
        if ventas_gravadas > 0:
            participacion_iva = datos["iva_a_pagar"] / ventas_gravadas * 100
            ratios.append(RatioAnalitico(
                nombre="Participación IVA sobre Ventas Gravadas",
                valor=round(participacion_iva, 2),
                unidad="%",
                periodo=periodo,
                observacion="IVA a pagar / Ventas gravadas (esperado ~10% para ventas al 10%)",
            ))

        # Concentración de clientes
        if datos["nro_clientes_unicos"] > 0:
            ratios.append(RatioAnalitico(
                nombre="Clientes Únicos Declarados",
                valor=datos["nro_clientes_unicos"],
                unidad="personas",
                periodo=periodo,
            ))

        # Concentración de proveedores
        if datos["nro_proveedores_unicos"] > 0:
            ratios.append(RatioAnalitico(
                nombre="Proveedores Únicos Declarados",
                valor=datos["nro_proveedores_unicos"],
                unidad="personas",
                periodo=periodo,
            ))

        # Ratio compras/ventas
        if datos["total_ventas"] > 0:
            ratio_compras_ventas = datos["total_compras"] / datos["total_ventas"]
            ratios.append(RatioAnalitico(
                nombre="Ratio Compras / Ventas",
                valor=round(ratio_compras_ventas, 2),
                unidad="veces",
                periodo=periodo,
                observacion="Compras totales / Ventas totales",
            ))

        # IVA omitido estimado (crédito fiscal excesivo)
        if datos["iva_compras"] > datos["iva_ventas"]:
            excedente_cf = datos["iva_compras"] - datos["iva_ventas"]
            ratios.append(RatioAnalitico(
                nombre="Excedente Crédito Fiscal",
                valor=excedente_cf,
                unidad="Gs.",
                periodo=periodo,
                observacion="CF excede DF — verificar proporcionalidad",
            ))

        return ratios

    def _comparar_benchmarks(self, resultado: ResultadoAnalitico, actividad: str):
        """Compara ratios con benchmarks de la industria."""
        benchmarks = BENCHMARKS.get(actividad.lower().split()[0], {})
        
        for ratio in resultado.ratios:
            benchmark_key = ratio.nombre.lower().replace(" ", "_")
            if benchmark_key in benchmarks:
                min_val, max_val = benchmarks[benchmark_key]
                ratio.benchmark_min = min_val
                ratio.benchmark_max = max_val
                ratio.dentro_rango = min_val <= ratio.valor <= max_val
                if not ratio.dentro_rango:
                    resultado.anomalias.append({
                        "tipo": "ratio_fuera_rango",
                        "ratio": ratio.nombre,
                        "valor": ratio.valor,
                        "rango_esperado": f"{min_val} - {max_val}",
                        "unidad": ratio.unidad,
                    })

    def _analizar_tendencias(self, actual: dict, anterior: dict, periodo: str) -> list[dict]:
        """Analiza variaciones entre períodos."""
        tendencias = []
        
        campos_clave = [
            ("total_ventas", "Ventas totales"),
            ("total_compras", "Compras totales"),
            ("iva_a_pagar", "IVA a pagar"),
            ("utilidad_bruta", "Utilidad bruta"),
        ]

        for campo, nombre in campos_clave:
            val_actual = actual.get(campo, 0)
            val_anterior = anterior.get(campo, 0)
            
            if val_anterior > 0:
                variacion_pct = ((val_actual - val_anterior) / val_anterior) * 100
                variacion_abs = val_actual - val_anterior
                
                tendencias.append({
                    "campo": nombre,
                    "periodo_anterior": val_anterior,
                    "periodo_actual": val_actual,
                    "variacion_pct": round(variacion_pct, 2),
                    "variacion_abs": variacion_abs,
                    "direccion": "sube" if variacion_pct > 0 else "baja" if variacion_pct < 0 else "igual",
                })

                # Alerta si variación > 30%
                if abs(variacion_pct) > 30:
                    resultado_obj = ResultadoAnalitico(periodo=periodo, procedimiento="")
                    resultado_obj.anomalias.append({
                        "tipo": "variacion_significativa",
                        "campo": nombre,
                        "variacion_pct": round(variacion_pct, 1),
                        "periodo_anterior": val_anterior,
                        "periodo_actual": val_actual,
                    })

        return tendencias

    def _detectar_anomalias(self, datos: dict, ratios: list[RatioAnalitico]) -> list[dict]:
        """Detecta anomalías estadísticas en los datos."""
        anomalias = []

        # Anomalía 1: IVA pagado muy bajo vs ventas
        if datos["total_ventas"] > 0:
            ratio_iva = datos["iva_a_pagar"] / datos["total_ventas"]
            if ratio_iva < 0.03:  # Menos del 3% de IVA sobre ventas
                anomalias.append({
                    "tipo": "iva_anomalmante_bajo",
                    "descripcion": f"IVA a pagar ({formatear_pyg(datos['iva_a_pagar'])}) es menos del 3% de ventas ({formatear_pyg(datos['total_ventas'])})",
                    "riesgo": "medio",
                })

        # Anomalía 2: Compras > 95% de ventas (margen cero o negativo)
        if datos["total_ventas"] > 0:
            ratio = datos["total_compras"] / datos["total_ventas"]
            if ratio > 0.95:
                anomalias.append({
                    "tipo": "margen_insostenible",
                    "descripcion": f"Compras representan {ratio*100:.0f}% de ventas — margen insostenible",
                    "riesgo": "alto",
                })

        # Anomalía 3: Crédito fiscal excesivo
        if datos["iva_compras"] > datos["iva_ventas"] * 1.5:
            anomalias.append({
                "tipo": "cf_excesivo",
                "descripcion": f"CF ({formatear_pyg(datos['iva_compras'])}) supera 1.5x DF ({formatear_pyg(datos['iva_ventas'])})",
                "riesgo": "alto",
            })

        return anomalias

    def _generar_alertas(self, resultado: ResultadoAnalitico):
        """Genera alertas para el auditor."""
        for anomalia in resultado.anomalias:
            if anomalia.get("riesgo") == "alto":
                resultado.alertas.append(
                    f"[ALTO] {anomalia.get('tipo', 'Anomalía')}: {anomalia.get('descripcion', '')}"
                )
            elif anomalia.get("riesgo") == "medio":
                resultado.alertas.append(
                    f"[MEDIO] {anomalia.get('tipo', 'Anomalía')}: {anomalia.get('descripcion', '')}"
                )
