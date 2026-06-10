"""
Analizador de patrones en datos de auditoria.
Detecta anomalias y genera sugerencias priorizadas usando IA (Gemini/Claude).
"""
import json
from collections import Counter
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from analisis.ai_provider import AIProvider
from db import db as crud
from db.models import RG90


async def analizar_patrones(
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    periodos: list[str],
) -> list[dict]:
    """
    Analiza datos RG90 y genera alertas de patrones.
    Retorna lista de dicts con tipo, descripcion, severidad y datos asociados.
    """
    alertas = []

    # Obtener todas las compras del periodo
    compras = []
    for p in periodos:
        c = await crud.get_rg90(db, firma_id, cliente_id, p, "compra")
        compras.extend(c)

    if not compras:
        return alertas

    total_cf = sum(c.iva_total for c in compras)

    # a. Concentracion de proveedores
    proveedor_cf: dict[str, int] = {}
    for c in compras:
        proveedor_cf[c.ruc_contraparte] = proveedor_cf.get(c.ruc_contraparte, 0) + c.iva_total
    for ruc, cf in proveedor_cf.items():
        if total_cf > 0 and (cf / total_cf) > 0.20:
            nombre = next((c.nombre_contraparte for c in compras if c.ruc_contraparte == ruc), ruc)
            alertas.append({
                "tipo": "CONCENTRACION_PROVEEDOR",
                "severidad": "alta",
                "titulo": "Concentracion de proveedor",
                "descripcion": f"Proveedor {nombre} (RUC {ruc}) representa {cf/total_cf*100:.1f}% del credito fiscal total.",
                "monto": cf,
                "proveedor_ruc": ruc,
                "proveedor_nombre": nombre,
            })
            break

    # b. Facturas redondas
    montos_redondos = [c for c in compras if c.total_comprobante > 1000000 and c.total_comprobante % 1000000 == 0]
    if montos_redondos:
        alertas.append({
            "tipo": "FACTURAS_REDONDAS",
            "severidad": "media",
            "titulo": "Facturas con montos redondos",
            "descripcion": f"Se detectaron {len(montos_redondos)} comprobantes con montos exactos (multiplos de 1.000.000). Patron asociado a facturas simuladas.",
            "cantidad": len(montos_redondos),
            "total_monto": sum(c.total_comprobante for c in montos_redondos),
            "ejemplos": [{"nro": c.nro_comprobante, "monto": c.total_comprobante, "proveedor": c.nombre_contraparte} for c in montos_redondos[:5]],
        })

    # c. Proveedores nuevos con montos altos
    ruc_frecuencia = Counter(c.ruc_contraparte for c in compras)
    monto_por_proveedor: dict[str, list[int]] = {}
    for c in compras:
        monto_por_proveedor.setdefault(c.ruc_contraparte, []).append(c.total_comprobante)

    promedio_general = sum(c.total_comprobante for c in compras) / len(compras) if compras else 0
    nuevos_altos = []
    for ruc, montos in monto_por_proveedor.items():
        if ruc_frecuencia[ruc] <= 2 and max(montos) > promedio_general * 2:
            nombre = next((c.nombre_contraparte for c in compras if c.ruc_contraparte == ruc), ruc)
            nuevos_altos.append({"ruc": ruc, "nombre": nombre, "monto_max": max(montos), "veces": ruc_frecuencia[ruc]})
    if nuevos_altos:
        alertas.append({
            "tipo": "PROVEEDORES_NUEVOS",
            "severidad": "media",
            "titulo": "Proveedores nuevos con montos elevados",
            "descripcion": f"{len(nuevos_altos)} proveedor(es) aparecen solo 1-2 veces con montos superiores al promedio (Gs. {promedio_general:,.0f}).",
            "proveedores": nuevos_altos,
        })

    # d. Picos atipicos
    compras_por_mes: dict[str, int] = {}
    for c in compras:
        compras_por_mes[c.periodo] = compras_por_mes.get(c.periodo, 0) + c.total_comprobante
    if compras_por_mes:
        promedio_mensual = sum(compras_por_mes.values()) / len(compras_por_mes)
        for periodo, total in compras_por_mes.items():
            if total > promedio_mensual * 2:
                alertas.append({
                    "tipo": "PICO_ATIPICO",
                    "severidad": "alta",
                    "titulo": "Pico atipico en compras",
                    "descripcion": f"Periodo {periodo}: compras de Gs. {total:,} duplican el promedio mensual (Gs. {promedio_mensual:,.0f}).",
                    "periodo": periodo,
                    "monto": total,
                    "promedio": int(promedio_mensual),
                })

    # e. Comprobantes de fin de mes
    fin_mes = [c for c in compras if c.fecha_emision and int(c.fecha_emision[-2:]) >= 28]
    if fin_mes:
        total_fin_mes = sum(c.total_comprobante for c in fin_mes)
        total_gral = sum(c.total_comprobante for c in compras)
        pct = total_fin_mes / total_gral * 100 if total_gral else 0
        if pct > 30:
            alertas.append({
                "tipo": "CONCENTRACION_FIN_MES",
                "severidad": "media",
                "titulo": "Concentracion de facturas a fin de mes",
                "descripcion": f"El {pct:.0f}% del total de compras corresponde a los ultimos 3 dias del mes. Posible maquillaje de cifras.",
                "porcentaje": round(pct),
                "total_monto": total_fin_mes,
            })

    # f. Mismo monto repetido
    monto_frecuencia = Counter(c.total_comprobante for c in compras)
    montos_repetidos = {m: cnt for m, cnt in monto_frecuencia.items() if cnt >= 3 and m > 0}
    if montos_repetidos:
        alertas.append({
            "tipo": "MONTOS_REPETIDOS",
            "severidad": "media",
            "titulo": "Montos identicos repetidos",
            "descripcion": f"Se detectaron {len(montos_repetidos)} montos que aparecen 3+ veces. Montos: {', '.join(f'Gs. {m:,} ({cnt}x)' for m, cnt in list(montos_repetidos.items())[:5])}",
            "cantidad": len(montos_repetidos),
        })

    return alertas


async def sugerir_procedimientos(
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    auditoria_id: str,
    periodos: list[str],
) -> list[dict]:
    """
    Detecta patrones y genera sugerencias de procedimientos usando IA.
    Retorna lista de sugerencias priorizadas.
    """
    from db.models import Auditoria, Cliente

    patrones = await analizar_patrones(db, firma_id, cliente_id, periodos)

    aud_result = await db.execute(select(Auditoria).where(Auditoria.id == auditoria_id))
    auditoria = aud_result.scalar_one_or_none()
    cli_result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    cliente = cli_result.scalar_one_or_none()

    sugerencias = _generar_sugerencias_base(patrones)

    # Usar IA para priorizar si hay patrones detectados
    if patrones and cliente:
        try:
            ai = AIProvider()
            system = "Sos un auditor impositivo senior en Paraguay especializado en Ley 6380/2019."
            user = f"""
Dado estos patrones detectados en los datos de auditoria de {cliente.razon_social} (RUC {cliente.ruc}, actividad: {cliente.actividad_principal or 'N/A'}, periodo: {auditoria.periodo_desde} a {auditoria.periodo_hasta}), sugiere los 5 procedimientos de auditoria mas relevantes a ejecutar, ordenados por prioridad y riesgo.

Patrones detectados:
{json.dumps(patrones, ensure_ascii=False, indent=2)}

Contexto: legislacion paraguaya, Ley 6380/2019.

Responde SOLO con un JSON array, cada elemento con:
- prioridad: "alta" | "media" | "baja"
- titulo: nombre del procedimiento
- descripcion: que implica ejecutarlo
- patron_relacionado: que patron lo disparo
- riesgo: "alto" | "medio" | "bajo"
"""
            ia_response = ai.generar(system, user, max_tokens=1500)
            ia_json = json.loads(ia_response)
            if isinstance(ia_json, list):
                return ia_json
        except Exception:
            pass

    return sugerencias


def _generar_sugerencias_base(patrones: list[dict]) -> list[dict]:
    """Genera sugerencias base a partir de patrones detectados sin IA."""
    sugerencias = []
    for p in patrones:
        sugerencia = None
        if p["tipo"] == "CONCENTRACION_PROVEEDOR":
            sugerencia = {
                "prioridad": "alta",
                "titulo": "Verificar concentracion de proveedor",
                "descripcion": f"Revisar documentacion respaldatoria del proveedor {p.get('proveedor_nombre', '')}. Solicitar contratos, ordenes de compra y comprobantes de pago.",
                "patron_relacionado": p["titulo"],
                "riesgo": "alto",
            }
        elif p["tipo"] == "FACTURAS_REDONDAS":
            sugerencia = {
                "prioridad": "alta",
                "titulo": "Validar facturas con montos redondos",
                "descripcion": f"Revisar {p.get('cantidad', 0)} comprobantes con montos exactos. Verificar existencia real de las operaciones y validar CDCs en SIFEN.",
                "patron_relacionado": p["titulo"],
                "riesgo": "alto",
            }
        elif p["tipo"] == "PROVEEDORES_NUEVOS":
            sugerencia = {
                "prioridad": "media",
                "titulo": "Verificar proveedores nuevos",
                "descripcion": "Validar RUC, domicilio fiscal y referencias de proveedores con aparicion reciente y montos elevados.",
                "patron_relacionado": p["titulo"],
                "riesgo": "medio",
            }
        elif p["tipo"] == "PICO_ATIPICO":
            sugerencia = {
                "prioridad": "alta",
                "titulo": "Investigar pico atipico de compras",
                "descripcion": f"Revisar {p.get('periodo', 'el periodo')}: las compras duplican el promedio mensual. Solicitar justificacion del incremento.",
                "patron_relacionado": p["titulo"],
                "riesgo": "alto",
            }
        elif p["tipo"] == "CONCENTRACION_FIN_MES":
            sugerencia = {
                "prioridad": "media",
                "titulo": "Revisar facturas de fin de mes",
                "descripcion": f"El {p.get('porcentaje', 0)}% de las compras se concentran en los ultimos 3 dias. Verificar autenticidad de las operaciones.",
                "patron_relacionado": p["titulo"],
                "riesgo": "medio",
            }
        elif p["tipo"] == "MONTOS_REPETIDOS":
            sugerencia = {
                "prioridad": "media",
                "titulo": "Analizar montos identicos repetidos",
                "descripcion": "Identificar y verificar comprobantes con montos exactos repetidos. Posible indicio de facturacion simulada.",
                "patron_relacionado": p["titulo"],
                "riesgo": "medio",
            }
        if sugerencia:
            sugerencias.append(sugerencia)
    return sugerencias
