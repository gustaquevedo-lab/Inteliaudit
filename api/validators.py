"""
Validadores Pydantic reutilizables para el proyecto Inteliaudit.
Sanitizacion de inputs paraguayos: RUC, periodo, formulario.
"""
import re

RUC_PATTERN = re.compile(r"^\d{1,8}-\d$")
PERIODO_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
FORMULARIOS_VALIDOS = {"120", "500", "800", "810", "820", "830"}


def validar_ruc(ruc: str) -> str:
    """Valida formato de RUC paraguayo (XXXXXXX-D)."""
    if not RUC_PATTERN.match(ruc):
        raise ValueError(f"RUC invalido: '{ruc}'. Formato esperado: XXXXXXX-D")
    return ruc


def validar_periodo(periodo: str) -> str:
    """Valida formato de periodo (YYYY-MM)."""
    if not PERIODO_PATTERN.match(periodo):
        raise ValueError(f"Periodo invalido: '{periodo}'. Formato esperado: YYYY-MM")
    return periodo


def validar_formulario(formulario: str) -> str:
    """Valida que el formulario sea uno de los permitidos."""
    if formulario not in FORMULARIOS_VALIDOS:
        raise ValueError(f"Formulario invalido: '{formulario}'. Opciones: {sorted(FORMULARIOS_VALIDOS)}")
    return formulario
