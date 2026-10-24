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
    firma_id: str,
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
    """
    datos_completos = {
        "impuesto": impuesto,
        "periodo": periodo,
        "tipo": tipo,
        "preparado_por": preparado_por,
        "hallazgos_refs": hallazgos_ids or [],
        "fecha_preparacion": datetime.now().isoformat(),
        **datos,
    }
    return await crud.crear_cedula(
        db=db,
        firma_id=firma_id,
        auditoria_id=auditoria_id,
        codigo=codigo,
        nombre=nombre,
        datos_json=json.dumps(datos_completos, ensure_ascii=False),
    )


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


async def compilar_cedulas_auditoria(db: AsyncSession, firma_id: str, auditoria_id: str) -> list[dict]:
    """Compila el legajo de papeles de trabajo según la NIA 230 para la auditoría."""
    from sqlalchemy import delete
    from db.models import Cedula

    # Limpiar cédulas previas de esta auditoría para regenerar legajo fresco
    await db.execute(delete(Cedula).where(Cedula.auditoria_id == auditoria_id, Cedula.firma_id == firma_id))

    auditoria = await crud.get_auditoria(db, firma_id, auditoria_id)
    if not auditoria:
        raise ValueError("Auditoría no encontrada")
    cliente = await crud.get_cliente(db, firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise ValueError("Cliente no encontrado")

    hallazgos = await crud.get_hallazgos(db, firma_id, auditoria_id)
    cedulas_creadas = []

    # 1. Cédula Sumaria (CED-SUM-01)
    tot_contingencia = sum(h.total_contingencia for h in hallazgos if h.estado != "descartado")
    h_altos = [h for h in hallazgos if h.nivel_riesgo == "alto" and h.estado != "descartado"]
    h_medios = [h for h in hallazgos if h.nivel_riesgo == "medio" and h.estado != "descartado"]
    h_bajos = [h for h in hallazgos if h.nivel_riesgo == "bajo" and h.estado != "descartado"]

    conclusion_sumaria = (
        f"Se han identificado {len(hallazgos)} hallazgos impositivos con una contingencia total estimada de "
        f"Gs. {tot_contingencia:,}. Se recomienda la rectificativa voluntaria de los períodos observados para mitigar "
        f"recargos moratorios conforme a los Arts. 218 y 219 de la Ley 125/1991."
        if tot_contingencia > 0 else "Los procedimientos aplicados no arrojaron contingencias materiales para el período auditado."
    )

    datos_sumaria = {
        "titulo": "Cédula Sumaria: Control Global y Contingencias Fiscales",
        "norma_tecnica": "NIA 230 (Documentación de Auditoría) y NIA 300",
        "cliente": cliente.razon_social,
        "ruc": f"{cliente.ruc}-{cliente.dv}",
        "periodo_auditado": f"{auditoria.periodo_desde} a {auditoria.periodo_hasta}",
        "materialidad": auditoria.materialidad,
        "total_contingencia": tot_contingencia,
        "resumen_riesgos": {
            "alto": len(h_altos),
            "medio": len(h_medios),
            "bajo": len(h_bajos),
        },
        "conclusion": conclusion_sumaria,
    }
    cid1 = await generar_cedula(
        db, firma_id, auditoria_id,
        codigo="CED-SUM-01",
        nombre="Cédula Sumaria de Control Fiscal",
        impuesto="GENERAL",
        periodo=f"{auditoria.periodo_desde}/{auditoria.periodo_hasta}",
        tipo="resumen",
        datos=datos_sumaria,
        hallazgos_ids=[h.id for h in hallazgos],
    )
    cedulas_creadas.append({"id": cid1, "codigo": "CED-SUM-01", "nombre": "Cédula Sumaria de Control Fiscal"})

    # 2. Cédula Analítica IVA (CED-IVA-01)
    h_iva = [h for h in hallazgos if h.impuesto == "IVA" and h.estado != "descartado"]
    datos_iva = {
        "titulo": "Cédula Analítica: Cruces de Integridad IVA (RG 90 vs Form. 120)",
        "norma_tecnica": "NIA 500 (Evidencia de Auditoría) + RG 90/2021 + Art. 97 Ley 6380/2019",
        "hallazgos_asociados": len(h_iva),
        "contingencia_iva": sum(h.total_contingencia for h in h_iva),
        "procedimiento": "Comparación sistemática de compras y ventas registradas en RG90 contra débitos y créditos declarados en Formularios 120.",
        "conclusion": f"Se determinaron {len(h_iva)} discrepancias en el período auditado con contingencia estimada de Gs. {sum(h.total_contingencia for h in h_iva):,}."
        if h_iva else "Las declaraciones del Form. 120 concilian con los libros electrónicos RG90.",
    }
    cid2 = await generar_cedula(
        db, firma_id, auditoria_id,
        codigo="CED-IVA-01",
        nombre="Cédula Analítica IVA: Cruce RG90 vs Form. 120",
        impuesto="IVA",
        periodo=f"{auditoria.periodo_desde}/{auditoria.periodo_hasta}",
        tipo="cruce",
        datos=datos_iva,
        hallazgos_ids=[h.id for h in h_iva],
    )
    cedulas_creadas.append({"id": cid2, "codigo": "CED-IVA-01", "nombre": "Cédula Analítica IVA: Cruce RG90 vs Form. 120"})

    # 3. Cédula Analítica IRE (CED-IRE-01)
    from analisis.conciliacion_fiscal import ConciliacionFiscal
    ejercicio = auditoria.periodo_desde[:4]
    motor_cf = ConciliacionFiscal(db, firma_id, auditoria_id, auditoria.materialidad)
    res_cf = await motor_cf.ejecutar(cliente.id, ejercicio)
    h_ire = [h for h in hallazgos if h.impuesto == "IRE" and h.estado != "descartado"]

    datos_ire = {
        "titulo": f"Cédula Analítica: Conciliación Contable → Fiscal IRE (Ejercicio {ejercicio})",
        "norma_tecnica": "Ley 6380/2019 Art. 14-16, Decreto 3107/2019",
        "resultado_contable": res_cf.resultado_contable,
        "ajustes_suma_art16": res_cf.ajustes_suma,
        "ajustes_resta": res_cf.ajustes_resta,
        "renta_neta_imponible": res_cf.renta_neta_imponible,
        "ire_esperado": res_cf.impuesto_esperado,
        "ire_declarado": res_cf.impuesto_declarado,
        "diferencia": res_cf.diferencia,
        "ajustes_detalle": [
            {"concepto": a.concepto, "tipo": a.tipo, "monto": a.monto, "base_legal": a.articulo_legal}
            for a in res_cf.ajustes
        ],
        "conclusion": f"Diferencia determinada en base imponible de Gs. {res_cf.diferencia:,}. Requiere ajuste extracontable en Form. 500."
        if res_cf.diferencia != 0 else "La base imponible declarada concilia con el resultado contable ajustado.",
    }
    cid3 = await generar_cedula(
        db, firma_id, auditoria_id,
        codigo="CED-IRE-01",
        nombre=f"Cédula Analítica IRE: Conciliación Fiscal Art. 16 ({ejercicio})",
        impuesto="IRE",
        periodo=ejercicio,
        tipo="conciliacion",
        datos=datos_ire,
        hallazgos_ids=[h.id for h in h_ire],
    )
    cedulas_creadas.append({"id": cid3, "codigo": "CED-IRE-01", "nombre": f"Cédula Analítica IRE: Conciliación Fiscal Art. 16 ({ejercicio})"})

    # 4. Cédula Analítica NIA 520 (CED-ANA-01)
    from analisis.analiticos import ProcedimientosAnaliticos
    motor_an = ProcedimientosAnaliticos(db, firma_id, auditoria_id, auditoria.materialidad)
    res_an = await motor_an.ejecutar(cliente.id, auditoria.periodo_hasta)

    datos_ana = {
        "titulo": "Cédula Analítica: Procedimientos Analíticos Sustantivos (NIA 520)",
        "norma_tecnica": "NIA 520 — Ratios Financieros, Benchmarks y Detección de Anomalías",
        "actividad": cliente.actividad_principal,
        "periodo_analizado": auditoria.periodo_hasta,
        "ratios": [
            {"nombre": r.nombre, "valor": r.valor, "unidad": r.unidad, "dentro_rango": r.dentro_rango, "observacion": r.observacion}
            for r in res_an.ratios
        ],
        "alertas": res_an.alertas,
        "anomalias": res_an.anomalias,
        "conclusion": f"Se observaron {len(res_an.alertas)} alertas analíticas y desvíos sobre el comportamiento sectorial."
        if res_an.alertas else "Los ratios analíticos se ubican dentro de los márgenes razonables del sector.",
    }
    cid4 = await generar_cedula(
        db, firma_id, auditoria_id,
        codigo="CED-ANA-01",
        nombre="Cédula Analítica: Procedimientos Analíticos Sustantivos (NIA 520)",
        impuesto="GENERAL",
        periodo=auditoria.periodo_hasta,
        tipo="calculo",
        datos=datos_ana,
    )
    cedulas_creadas.append({"id": cid4, "codigo": "CED-ANA-01", "nombre": "Cédula Analítica: Procedimientos Analíticos Sustantivos (NIA 520)"})

    await db.commit()
    return cedulas_creadas
