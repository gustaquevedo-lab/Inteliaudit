"""
Rate limiter para llamadas a IA por firma.
Plan Pro: 50 llamadas/mes, Enterprise: ilimitado.
"""
import time
from typing import Optional

from config.plans import PLAN_ALIAS_MAP, get_plan

_usage: dict[str, dict] = {}  # {firma_id: {month_key: count}}


def _month_key() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m")


def check_ia_rate_limit(firma_id: str, firma_plan: str) -> tuple[bool, Optional[str], int]:
    """
    Verifica si la firma puede hacer una llamada IA.
    Retorna: (puede_pasar, mensaje_error, usos_en_periodo)
    """
    plan_key = PLAN_ALIAS_MAP.get(firma_plan, firma_plan)
    plan_cfg = get_plan(plan_key)

    if not plan_cfg.tiene_ia:
        return False, "IA disponible solo en plan Pro y Enterprise", 0

    if plan_cfg.max_clientes is None:
        # Enterprise: ilimitado
        return True, None, 0

    # Pro: limite de 50 llamadas/mes
    mkey = _month_key()
    firma_usage = _usage.setdefault(firma_id, {})
    count = firma_usage.get(mkey, 0)
    limit = 50

    if count >= limit:
        return False, f"Límite mensual de IA alcanzado ({limit} llamadas). Actualizá a Enterprise para uso ilimitado.", count

    return True, None, count


def increment_ia_usage(firma_id: str):
    """Incrementa el contador de uso de IA para la firma."""
    mkey = _month_key()
    _usage.setdefault(firma_id, {}).setdefault(mkey, 0)
    _usage[firma_id][mkey] += 1


def get_ia_usage(firma_id: str) -> dict:
    """Retorna el uso de IA de la firma en el período actual."""
    mkey = _month_key()
    count = _usage.get(firma_id, {}).get(mkey, 0)
    return {"periodo": mkey, "llamadas_realizadas": count}
