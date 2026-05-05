"""
Configuración centralizada de planes de Inteliaudit.
Usada por backend (validación de límites) y frontend (UI de features).
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlanConfig:
    id: str
    nombre: str
    precio_mensual: int  # Gs.
    precio_anual: int    # Gs. (con 15% descuento aplicado)
    max_clientes: Optional[int]  # None = ilimitados
    max_usuarios: Optional[int]
    tiene_ia: bool
    tiene_credenciales_encriptadas: bool
    tiene_portal_cliente: bool
    tiene_api_personalizada: bool
    tiene_logo_firma: bool
    soporte: str  # "email" | "whatsapp" | "dedicado_sla"
    onboarding: bool
    trial_dias: int = 7
    # Features que se muestran en UI
    features: list[str] = field(default_factory=list)


PLANES: dict[str, PlanConfig] = {
    "starter": PlanConfig(
        id="starter",
        nombre="Starter",
        precio_mensual=490_000,
        precio_anual=4_998_000,   # ~416.500/mes (15% off)
        max_clientes=5,
        max_usuarios=3,
        tiene_ia=False,
        tiene_credenciales_encriptadas=False,
        tiene_portal_cliente=False,
        tiene_api_personalizada=False,
        tiene_logo_firma=False,
        soporte="email",
        onboarding=False,
        features=[
            "Análisis automático IVA + IRE + Retenciones",
            "Cruce RG90 vs SIFEN vs HECHAUKA",
            "Generación de informes Word + PDF",
            "Hasta 3 usuarios por firma",
            "Soporte por email",
            "Audit trail completo de acciones",
        ],
    ),
    "pro": PlanConfig(
        id="pro",
        nombre="Pro",
        precio_mensual=890_000,
        precio_anual=9_078_000,   # ~756.500/mes (15% off)
        max_clientes=15,
        max_usuarios=8,
        tiene_ia=True,
        tiene_credenciales_encriptadas=True,
        tiene_portal_cliente=False,
        tiene_api_personalizada=False,
        tiene_logo_firma=False,
        soporte="whatsapp",
        onboarding=False,
        features=[
            "Todo lo del plan Starter",
            "Análisis con IA — detección inteligente de hallazgos",
            "Narrativa automática de hallazgos con base legal",
            "Sugerencias de procedimientos por IA",
            "Hasta 8 usuarios por firma",
            "Credenciales Marangatú encriptadas AES-256",
            "Plan de trabajo con checklist automático",
            "Evidencias y notas por hallazgo",
            "Soporte prioritario WhatsApp",
        ],
    ),
    "enterprise": PlanConfig(
        id="enterprise",
        nombre="Enterprise",
        precio_mensual=1_790_000,
        precio_anual=18_258_000,  # ~1.521.500/mes (15% off)
        max_clientes=None,  # ilimitados
        max_usuarios=None,  # ilimitados
        tiene_ia=True,
        tiene_credenciales_encriptadas=True,
        tiene_portal_cliente=True,
        tiene_api_personalizada=True,
        tiene_logo_firma=True,
        soporte="dedicado_sla",
        onboarding=True,
        features=[
            "Todo lo del plan Pro",
            "IA ilimitada — sin restricciones de uso",
            "Usuarios ilimitados",
            "Logo e identidad de firma en informes",
            "Portal de cliente para compartir hallazgos",
            "Onboarding y capacitación del equipo",
            "Soporte dedicado con SLA",
            "API personalizada para integraciones",
        ],
    ),
}

# Alias para compatibilidad con datos existentes
PLAN_ALIAS_MAP = {
    "trial": "pro",       # trial = degustación del plan Pro
    "professional": "pro",
    "starter": "starter",
    "enterprise": "enterprise",
}


def get_plan(plan_id: str) -> PlanConfig:
    """Obtiene la configuración de un plan, resolviendo aliases."""
    resolved = PLAN_ALIAS_MAP.get(plan_id, plan_id)
    return PLANES[resolved]


def can_use_ia(plan_id: str) -> bool:
    return get_plan(plan_id).tiene_ia


def can_add_cliente(plan_id: str, current_count: int) -> bool:
    cfg = get_plan(plan_id)
    if cfg.max_clientes is None:
        return True
    return current_count < cfg.max_clientes


def can_add_usuario(plan_id: str, current_count: int) -> bool:
    cfg = get_plan(plan_id)
    if cfg.max_usuarios is None:
        return True
    return current_count < cfg.max_usuarios
