"""
Generador de cédulas analíticas (papeles de trabajo).
Cada cédula documenta el procedimiento realizado, la evidencia y la conclusión.
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from db import db as crud


async def generar_cedula(
    db: AsyncSession,
    auditoria_id: str,
    codigo: str,
    nombre: str,
    impuesto: str,
    periodo: str,
    tipo: str,
    datos: dict,
    hallazgos_ids: Optional[list[str]] = None,
    preparado_por: str = "Inteliaudit",
) -> str:
    """
    Crea una cédula analítica en la DB y retorna su ID.

    Args:
        tipo: 'cruce' | 'calculo' | 'conciliacion' | 'resumen'
        datos: Estructura libre con el contenido de la cédula
        hallazgos_ids: IDs de hallazgos relacionados
    """
    from db.models import Cedula
    cedula = Cedula(
        auditoria_id=auditoria_id,
        codigo=codigo,
        nombre=nombre,
        impuesto=impuesto,
        periodo=periodo,
        tipo=tipo,
        datos_json=json.dumps(datos, ensure_ascii=False),
        hallazgos_refs=json.dumps(hallazgos_ids or [], ensure_ascii=False),
        preparado_por=preparado_por,
    )
    db.add(cedula)
    await db.flush()
    return cedula.id


def construir_cedula_cruce_rg90_form120(
    periodo: str,
    compras: list[dict],
    ventas: list[dict],
    declaracion_120: dict,
) -> dict:
    """
    Construye la estructura de datos de la cédula de cruce RG90 vs Form.120.
    """
    total_cf_rg90 = sum(c.get("iva_total", 0) for c in compras)
    total_df_rg90 = sum(v.get("iva_total", 0) for v in ventas)

    cf_declarado = int(declaracion_120.get("credito_fiscal", 0))
    df_declarado = int(declaracion_120.get("debito_fiscal", 0))

    return {
        "titulo": f"Cruce RG90 vs Formulario 120 — Período {periodo}",
        "procedimiento": "Comparación de totales de IVA crédito y débito entre RG90 presentada y Form.120",
        "base_legal": "RG 90/2021 + Art. 97 Ley 6380/2019",
        "fecha_preparacion": datetime.now().isoformat(),
        "resumen": {
            "credito_fiscal": {
                "segun_rg90": total_cf_rg90,
                "segun_form120": cf_declarado,
                "diferencia": total_cf_rg90 - cf_declarado,
                "cantidad_comprobantes": len(compras),
            },
            "debito_fiscal": {
                "segun_rg90": total_df_rg90,
                "segun_form120": df_declarado,
                "diferencia": total_df_rg90 - df_declarado,
                "cantidad_comprobantes": len(ventas),
            },
        },
        "conclusion": _concluir_cruce(total_cf_rg90, cf_declarado, total_df_rg90, df_declarado),
    }


def construir_cedula_ruc_inactivos(
    periodo: str,
    comprobantes_ruc_inactivo: list[dict],
) -> dict:
    """Cédula de comprobantes con RUC inactivo/cancelado."""
    total_credito_riesgo = sum(c.get("iva_total", 0) for c in comprobantes_ruc_inactivo)
    return {
        "titulo": f"Validación RUC Proveedores — Período {periodo}",
        "procedimiento": "Verificación de estado RUC de todos los proveedores en RG90 compras",
        "base_legal": "Art. 95 Ley 6380/2019 — Requisitos crédito fiscal",
        "fecha_preparacion": datetime.now().isoformat(),
        "hallazgos": comprobantes_ruc_inactivo,
        "total_credito_en_riesgo": total_credito_riesgo,
        "conclusion": (
            f"Se identificaron {len(comprobantes_ruc_inactivo)} comprobante(s) de proveedores "
            f"con RUC inactivo o cancelado. Crédito fiscal en riesgo: Gs. {total_credito_riesgo:,}."
        ) if comprobantes_ruc_inactivo else "No se encontraron comprobantes con RUC inactivo.",
    }


def _concluir_cruce(cf_rg90: int, cf_120: int, df_rg90: int, df_120: int) -> str:
    observaciones = []
    diff_cf = cf_rg90 - cf_120
    diff_df = df_rg90 - df_120

    if diff_cf == 0 and diff_df == 0:
        return "Los totales de RG90 cuadran exactamente con los declarados en Form.120. Sin observaciones."

    if diff_cf != 0:
        dir_cf = "mayor" if diff_cf > 0 else "menor"
        observaciones.append(f"Crédito fiscal RG90 es Gs. {abs(diff_cf):,} {dir_cf} al declarado en Form.120")
    if diff_df != 0:
        dir_df = "mayor" if diff_df > 0 else "menor"
        observaciones.append(f"Débito fiscal RG90 es Gs. {abs(diff_df):,} {dir_df} al declarado en Form.120")

    return "Se detectaron diferencias: " + "; ".join(observaciones) + "."
