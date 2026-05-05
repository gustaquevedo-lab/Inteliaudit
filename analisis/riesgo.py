"""
Cuantificación de contingencias tributarias.
Cálculo de multas e intereses según Ley 125/1991 Art. 175.
"""
from datetime import date, datetime
from typing import Optional


# ============================================================
#  Constantes legales
# ============================================================

# Art. 175 Ley 125/1991
MULTA_OMISION_SIMPLE = 0.50   # 50% del impuesto omitido
MULTA_CONTUMACIA = 1.00       # 100% — reincidencia

# Tasa de interés moratorio SET (verificar tasa vigente en cada ejercicio)
# Históricamente 1% mensual; puede cambiar por resolución SET
TASA_INTERES_MENSUAL = 0.01   # 1% mensual

# Umbrales materialidad por defecto (PYG)
MATERIALIDAD_ALTA = 10_000_000    # 10 millones
MATERIALIDAD_MEDIA = 2_000_000    # 2 millones
MATERIALIDAD_BAJA = 500_000       # 500 mil


# ============================================================
#  Cálculo principal
# ============================================================

def calcular_contingencia(
    impuesto_omitido: int,
    fecha_omision: str,
    fecha_calculo: Optional[str] = None,
    reincidente: bool = False,
) -> dict:
    """
    Calcula la contingencia total de un hallazgo tributario.

    Args:
        impuesto_omitido: Monto del impuesto omitido en PYG
        fecha_omision: Fecha de vencimiento del período omitido (YYYY-MM-DD)
        fecha_calculo: Fecha a la cual calcular (default: hoy)
        reincidente: Si aplica multa por contumacia (100% en vez de 50%)

    Returns:
        Dict con: impuesto, multa, intereses, total_contingencia, meses, tasa_multa
    """
    hoy = date.today() if not fecha_calculo else _parse_fecha(fecha_calculo)
    omision = _parse_fecha(fecha_omision)

    meses = _diferencia_meses(omision, hoy)

    tasa_multa = MULTA_CONTUMACIA if reincidente else MULTA_OMISION_SIMPLE
    multa = int(impuesto_omitido * tasa_multa)
    intereses = int(impuesto_omitido * TASA_INTERES_MENSUAL * meses)
    total = impuesto_omitido + multa + intereses

    return {
        "impuesto_omitido": impuesto_omitido,
        "multa_estimada": multa,
        "intereses_estimados": intereses,
        "total_contingencia": total,
        "meses_mora": meses,
        "tasa_multa": tasa_multa,
        "fecha_omision": fecha_omision,
        "fecha_calculo": hoy.isoformat(),
    }


def calcular_contingencia_lote(
    hallazgos: list[dict],
    fecha_calculo: Optional[str] = None,
) -> list[dict]:
    """
    Calcula contingencias para una lista de hallazgos.
    Cada dict debe tener: impuesto_omitido, fecha_omision.
    """
    return [
        {**h, **calcular_contingencia(
            h["impuesto_omitido"],
            h["fecha_omision"],
            fecha_calculo,
            h.get("reincidente", False),
        )}
        for h in hallazgos
    ]


# ============================================================
#  Clasificación de riesgo
# ============================================================

def clasificar_riesgo(
    total_contingencia: int,
    materialidad: int = 0,
) -> str:
    """
    Clasifica el nivel de riesgo de un hallazgo según su contingencia.

    Args:
        total_contingencia: Monto total de contingencia en PYG
        materialidad: Umbral de materialidad de la auditoría

    Returns:
        'alto' | 'medio' | 'bajo'
    """
    umbral_alto = max(MATERIALIDAD_ALTA, materialidad * 5)
    umbral_medio = max(MATERIALIDAD_MEDIA, materialidad)

    if total_contingencia >= umbral_alto:
        return "alto"
    elif total_contingencia >= umbral_medio:
        return "medio"
    return "bajo"


def clasificar_riesgo_lote(hallazgos: list[dict], materialidad: int = 0) -> list[dict]:
    """Clasifica nivel de riesgo para una lista de hallazgos."""
    for h in hallazgos:
        h["nivel_riesgo"] = clasificar_riesgo(h.get("total_contingencia", 0), materialidad)
    return hallazgos


# ============================================================
#  Resumen de contingencias
# ============================================================

def resumir_contingencias(hallazgos: list[dict]) -> dict:
    """
    Genera resumen ejecutivo de contingencias por impuesto y nivel de riesgo.

    Args:
        hallazgos: Lista de dicts con total_contingencia, impuesto, nivel_riesgo

    Returns:
        Dict con totales y desgloses
    """
    resumen: dict = {
        "total_impuesto": 0,
        "total_multa": 0,
        "total_intereses": 0,
        "total_contingencia": 0,
        "por_impuesto": {},
        "por_riesgo": {"alto": 0, "medio": 0, "bajo": 0},
        "cantidad_hallazgos": len(hallazgos),
    }

    for h in hallazgos:
        if h.get("estado") == "descartado":
            continue

        impuesto = h.get("impuesto", "OTRO")
        riesgo = h.get("nivel_riesgo", "medio")

        resumen["total_impuesto"] += h.get("impuesto_omitido", 0)
        resumen["total_multa"] += h.get("multa_estimada", 0)
        resumen["total_intereses"] += h.get("intereses_estimados", 0)
        resumen["total_contingencia"] += h.get("total_contingencia", 0)
        resumen["por_riesgo"][riesgo] = resumen["por_riesgo"].get(riesgo, 0) + h.get("total_contingencia", 0)

        if impuesto not in resumen["por_impuesto"]:
            resumen["por_impuesto"][impuesto] = {
                "impuesto_omitido": 0,
                "multa": 0,
                "intereses": 0,
                "total": 0,
                "cantidad": 0,
            }
        d = resumen["por_impuesto"][impuesto]
        d["impuesto_omitido"] += h.get("impuesto_omitido", 0)
        d["multa"] += h.get("multa_estimada", 0)
        d["intereses"] += h.get("intereses_estimados", 0)
        d["total"] += h.get("total_contingencia", 0)
        d["cantidad"] += 1

    return resumen


# ============================================================
#  Cálculos IVA específicos
# ============================================================

def calcular_iva_sobre_monto(monto_total: int, tasa: int = 10) -> tuple[int, int]:
    """
    Descompone un monto con IVA incluido en base imponible e IVA.

    Args:
        monto_total: Monto total con IVA incluido (PYG)
        tasa: 10 o 5

    Returns:
        (base_imponible, iva)
    """
    divisor = 1 + (tasa / 100)
    base = int(monto_total / divisor)
    iva = monto_total - base
    return base, iva


def proporcionalidad_cf(
    credito_fiscal_total: int,
    ventas_gravadas: int,
    ventas_totales: int,
) -> int:
    """
    Calcula el crédito fiscal admitido por proporcionalidad.
    Aplica cuando el contribuyente tiene operaciones gravadas y exentas.
    Art. 97 Ley 6380/2019.
    """
    if ventas_totales == 0:
        return 0
    proporcion = ventas_gravadas / ventas_totales
    return int(credito_fiscal_total * proporcion)


# ============================================================
#  Helpers
# ============================================================

def _parse_fecha(fecha: str) -> date:
    """Parsea fecha en formato YYYY-MM-DD o YYYY-MM."""
    if len(fecha) == 7:
        # YYYY-MM → último día del mes
        año, mes = int(fecha[:4]), int(fecha[5:7])
        import calendar
        ultimo_dia = calendar.monthrange(año, mes)[1]
        return date(año, mes, ultimo_dia)
    return date.fromisoformat(fecha)


def _diferencia_meses(desde: date, hasta: date) -> int:
    """Calcula diferencia en meses completos entre dos fechas."""
    return max(0, (hasta.year - desde.year) * 12 + (hasta.month - desde.month))


def formatear_pyg(monto: int) -> str:
    """Formatea un monto PYG con separadores de miles. Ej: 1500000 → '1.500.000'"""
    return f"{monto:,.0f}".replace(",", ".")
