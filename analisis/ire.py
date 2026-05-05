"""
Procedimientos de auditoría IRE — Impuesto a la Renta Empresarial.
Formulario 500. Ley 6380/2019 Art. 15-17, Decreto 3107/2019.
"""
from dataclasses import dataclass, field

from rich.console import Console
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import calcular_contingencia, clasificar_riesgo
from db import db as crud

console = Console()

# Tasas de depreciación máximas — Decreto 3107/2019
TASAS_DEPRECIACION = {
    "inmuebles":            0.025,   # 2.5% anual (40 años)
    "maquinaria":           0.10,    # 10% (10 años)
    "vehiculos":            0.20,    # 20% (5 años)
    "equipos_informaticos": 0.333,   # 33.3% (3 años)
    "muebles_utiles":       0.10,    # 10% (10 años)
    "instalaciones":        0.10,    # 10% (10 años)
}

ALICUOTA_IRE = 0.10  # 10% Ley 6380/2019 Art. 17

ARTICULOS = {
    "IRE_GASTO_NO_DEDUCIBLE":    "Art. 16 Ley 6380/2019 — Gastos no deducibles",
    "IRE_DEPRECIACION_EXCEDIDA": "Art. 24 Decreto 3107/2019 — Tasas máximas depreciación",
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
    """Procedimientos de auditoría IRE para un ejercicio fiscal."""

    def __init__(self, db: AsyncSession, firma_id: str, auditoria_id: str, materialidad: int = 0):
        self.db = db
        self.firma_id = firma_id
        self.auditoria_id = auditoria_id
        self.materialidad = materialidad

    async def ejecutar_auditoria(self, cliente_id: str, ejercicio: str) -> ResultadoAuditoriaIRE:
        """
        Ejecuta todos los procedimientos IRE para un ejercicio (YYYY).
        """
        resultado = ResultadoAuditoriaIRE(ejercicio=ejercicio)
        console.print(f"[blue]IRE:[/] auditando ejercicio {ejercicio}...")

        r1 = await self.verificar_depreciaciones(cliente_id, ejercicio)
        r2 = await self.verificar_gastos_sin_comprobante(cliente_id, ejercicio)
        r3 = await self.conciliar_resultado_contable(cliente_id, ejercicio)

        resultado.hallazgos_generados = r1 + r2 + r3
        return resultado

    # --------------------------------------------------------
    #  Depreciaciones
    # --------------------------------------------------------

    async def verificar_depreciaciones(self, cliente_id: str, ejercicio: str) -> int:
        """
        Verifica que las depreciaciones no superen tasas máximas del Decreto 3107.
        Retorna cantidad de hallazgos generados.
        """
        # TODO: requiere estados contables con detalle de activo fijo
        # Comparar tasa declarada vs tasa máxima por categoría
        console.print(f"[dim]IRE: verificación de depreciaciones {ejercicio} — pendiente datos contables[/]")
        return 0

    # --------------------------------------------------------
    #  Gastos sin comprobante
    # --------------------------------------------------------

    async def verificar_gastos_sin_comprobante(self, cliente_id: str, ejercicio: str) -> int:
        """
        Identifica gastos en estados contables sin respaldo en comprobantes SET.
        Retorna cantidad de hallazgos generados.
        """
        # TODO: cruce estados contables vs declaraciones/RG90
        # Categorías de alto riesgo: honorarios, servicios, gastos de representación
        console.print(f"[dim]IRE: verificación gastos sin comprobante {ejercicio} — pendiente datos contables[/]")
        return 0

    # --------------------------------------------------------
    #  Conciliación resultado contable vs base imponible
    # --------------------------------------------------------

    async def conciliar_resultado_contable(self, cliente_id: str, ejercicio: str) -> int:
        """
        Compara el resultado contable con la renta neta declarada en Form.500.
        Las diferencias no justificadas son potenciales ajustes.
        """
        declaraciones = await crud.get_declaraciones(self.db, self.firma_id, cliente_id, "500", ejercicio)
        if not declaraciones:
            console.print(f"[yellow]⚠[/] IRE {ejercicio}: no se encontró Form.500")
            return 0

        import json
        decl = sorted(declaraciones, key=lambda d: d.nro_rectificativa, reverse=True)[0]
        datos = json.loads(decl.datos_json)

        # TODO: parsear campos específicos del Form.500
        # renta_neta_declarada = datos.get("renta_neta_imponible", 0)
        # Comparar vs resultado contable de estados_contables

        return 0

    # --------------------------------------------------------
    #  Límites deducibilidad
    # --------------------------------------------------------

    @staticmethod
    def verificar_limite_representacion(ingresos_brutos: int, gastos_representacion: int) -> dict:
        """
        Verifica límite del 1% sobre ingresos brutos para gastos de representación.
        Art. 16 inc. j) Ley 6380/2019.
        """
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
        """
        Verifica límite del 1% sobre renta bruta para donaciones.
        Art. 16 inc. k) Ley 6380/2019.
        """
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
        """
        Calcula la depreciación máxima admisible para un activo.

        Args:
            valor_activo: Valor de costo del activo en PYG
            categoria: Clave de TASAS_DEPRECIACION
            años_usados: Años ya depreciados anteriormente

        Returns:
            Dict con cuota_anual_max, vida_util, años_restantes
        """
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
