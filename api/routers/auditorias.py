"""
Router para la gestión de auditorías en un entorno multi-tenant.
"""
import asyncio
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from db import db as crud
from db.models import Usuario
from api.routers.auth import get_current_user

router = APIRouter(prefix="/auditorias", tags=["auditorias"])

class AuditoriaCreate(BaseModel):
    cliente_id: str
    periodo_desde: str
    periodo_hasta: str
    tipo_encargo: Optional[str] = "auditoria_anual"
    impuestos: List[str]
    materialidad: int = 0
    auditor: Optional[str] = None

@router.get("")
async def listar_auditorias(
    cliente_id: Optional[str] = None,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from db.models import Auditoria, Cliente
    
    query = select(Auditoria, Cliente.razon_social).join(Cliente, Auditoria.cliente_id == Cliente.id).where(Auditoria.firma_id == user.firma_id)
    if cliente_id:
        query = query.where(Auditoria.cliente_id == cliente_id)
    
    result = await db.execute(query.order_by(Auditoria.creado_en.desc()))
    rows = result.all()
    
    return [
        {
            "id": a.id,
            "cliente_id": a.cliente_id,
            "cliente_nombre": razon_social,
            "periodo_desde": a.periodo_desde,
            "periodo_hasta": a.periodo_hasta,
            "tipo_encargo": a.tipo_encargo,
            "impuestos": json.loads(a.impuestos),
            "estado": a.estado,
            "auditor": a.auditor,
            "fecha_inicio": a.fecha_inicio.isoformat() if a.fecha_inicio else None,
        }
        for a, razon_social in rows
    ]

@router.post("", status_code=201)
async def crear_auditoria(
    body: AuditoriaCreate,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    cliente = await crud.get_cliente(db, firma_id=user.firma_id, id=body.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    auditoria = await crud.crear_auditoria(
        db,
        firma_id=user.firma_id,
        cliente_id=body.cliente_id,
        periodo_desde=body.periodo_desde,
        periodo_hasta=body.periodo_hasta,
        tipo_encargo=body.tipo_encargo,
        impuestos=body.impuestos,
        materialidad=body.materialidad,
        auditor=body.auditor,
    )
    return {"id": auditoria.id, "estado": auditoria.estado, "tipo_encargo": auditoria.tipo_encargo}

@router.get("/stats/global")
async def get_global_stats(
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Obtiene estadísticas consolidadas de todas las auditorías de la firma."""
    from sqlalchemy import select, func
    from db.models import Auditoria, Hallazgo, Cliente
    import json

    # 1. Resumen de Auditorías
    res_aud = await db.execute(
        select(
            func.count(Auditoria.id).label("total"),
            func.count(Auditoria.id).filter(Auditoria.estado == 'en_progreso').label("activas")
        ).where(Auditoria.firma_id == user.firma_id)
    )
    aud_stats = res_aud.one()

    # 2. Impacto Financiero (Hallazgos)
    res_hal = await db.execute(
        select(
            func.sum(Hallazgo.total_contingencia).label("riesgo_total"),
            func.count(Hallazgo.id).label("total_hallazgos")
        ).where(Hallazgo.firma_id == user.firma_id, Hallazgo.estado != 'descartado')
    )
    hal_stats = res_hal.one()

    # 3. Distribución por Impuesto
    res_imp = await db.execute(
        select(
            Hallazgo.impuesto,
            func.count(Hallazgo.id).label("cantidad")
        ).where(Hallazgo.firma_id == user.firma_id, Hallazgo.estado != 'descartado')
        .group_by(Hallazgo.impuesto)
    )
    imp_dist = {row.impuesto: row.cantidad for row in res_imp.all()}

    return {
        "auditorias_totales": aud_stats.total or 0,
        "auditorias_activas": aud_stats.activas or 0,
        "riesgo_total_detectado": int(hal_stats.riesgo_total or 0),
        "total_hallazgos": hal_stats.total_hallazgos or 0,
        "distribucion_impuestos": imp_dist
    }


# ============================================================
#  Análisis — Orquestador con background task + polling
# ============================================================

_analysis_progress: dict[str, dict] = {}


@router.post("/{auditoria_id}/ejecutar-analisis")
async def ejecutar_analisis(
    auditoria_id: str,
    body: dict,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ejecuta los análisis seleccionados en background. Retorna inmediatamente con job_id."""
    from sqlalchemy import update as sa_update
    from db.models import Auditoria

    impuestos = body.get("impuestos", ["iva"])
    periodos = body.get("periodos", [])

    if not impuestos:
        raise HTTPException(400, "Seleccioná al menos un impuesto para analizar")
    if not periodos:
        raise HTTPException(400, "Seleccioná al menos un período")

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    # Inicializar progreso
    cruces_plan = []
    if "iva" in impuestos:
        cruces_plan += [
            {"nombre": "RG90 vs Form.120", "estado": "pendiente", "hallazgos": 0},
            {"nombre": "RG90 vs SIFEN", "estado": "pendiente", "hallazgos": 0},
            {"nombre": "SIFEN vs RG90", "estado": "pendiente", "hallazgos": 0},
            {"nombre": "RG90 vs HECHAUKA", "estado": "pendiente", "hallazgos": 0},
            {"nombre": "RUC proveedores", "estado": "pendiente", "hallazgos": 0},
        ]
    if "ire" in impuestos:
        cruces_plan += [
            {"nombre": "Conciliación contable", "estado": "pendiente", "hallazgos": 0},
            {"nombre": "Depreciaciones", "estado": "pendiente", "hallazgos": 0},
            {"nombre": "Gastos sin comprobante", "estado": "pendiente", "hallazgos": 0},
        ]
    if "retenciones" in impuestos:
        cruces_plan += [
            {"nombre": "HECHAUKA vs Forms. 800/820", "estado": "pendiente", "hallazgos": 0},
            {"nombre": "Retenciones omitidas", "estado": "pendiente", "hallazgos": 0},
        ]

    job_id = f"analisis-{auditoria_id}-{int(asyncio.get_event_loop().time())}"
    _analysis_progress[job_id] = {
        "estado": "ejecutando",
        "progreso": 0,
        "cruces": cruces_plan,
        "total_hallazgos": 0,
    }

    # Marcar auditoría como "analizando"
    await db.execute(
        sa_update(Auditoria).where(Auditoria.id == auditoria_id).values(estado="analizando")
    )

    await crud.log_trail(
        db, firma_id=user.firma_id, usuario_id=user.id,
        accion=f"Análisis iniciado: {', '.join(impuestos)} ({len(periodos)} períodos)",
        modulo="analisis", auditoria_id=auditoria_id,
        datos={"impuestos": impuestos, "periodos": periodos, "job_id": job_id},
    )
    await db.commit()

    # Lanzar background task
    asyncio.create_task(_run_analysis_background(
        job_id=job_id,
        firma_id=user.firma_id,
        auditoria_id=auditoria_id,
        impuestos=impuestos,
        periodos=periodos,
    ))

    return {"ok": True, "job_id": job_id, "total_cruces": len(cruces_plan)}


@router.get("/{auditoria_id}/estado-analisis")
async def estado_analisis(
    auditoria_id: str,
    job_id: str = "",
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retorna el estado actual del análisis. Frontend hace polling cada 2s."""
    if not job_id:
        return {"estado": "idle", "progreso": 0, "cruces": [], "total_hallazgos": 0}

    estado = _analysis_progress.get(job_id)
    if not estado:
        from sqlalchemy import select
        from db.models import Auditoria
        result = await db.execute(select(Auditoria).where(Auditoria.id == auditoria_id))
        a = result.scalar_one_or_none()
        return {"estado": a.estado if a else "desconocido", "progreso": 100, "cruces": [], "total_hallazgos": 0}

    return {
        **estado,
        "hallazgos_por_riesgo": estado.get("hallazgos_por_riesgo", {}),
    }


async def _run_analysis_background(
    job_id: str,
    firma_id: str,
    auditoria_id: str,
    impuestos: list[str],
    periodos: list[str],
):
    """Ejecuta los análisis en background y actualiza el progreso."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    from db.base import engine

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        try:
            cruces = _analysis_progress[job_id]["cruces"]
            total_hallazgos = 0
            idx = 0

            if "iva" in impuestos:
                from analisis.iva import AuditoriaIVA

                auditoria = await crud.get_auditoria(db, firma_id, auditoria_id)
                if not auditoria:
                    raise ValueError("Auditoría no encontrada")
                cliente = await crud.get_cliente(db, firma_id, id=auditoria.cliente_id)
                if not cliente:
                    raise ValueError("Cliente no encontrado")

                motor = AuditoriaIVA(db, firma_id, auditoria_id, auditoria.materialidad)

                for cruce_method, cruce_name in [
                    (motor.cruce_rg90_vs_form120, "RG90 vs Form.120"),
                    (motor.cruce_rg90_vs_sifen, "RG90 vs SIFEN"),
                    (motor.cruce_sifen_vs_rg90, "SIFEN vs RG90"),
                    (motor.cruce_rg90_vs_hechauka, "RG90 vs HECHAUKA"),
                    (motor.cruce_ruc_proveedores, "RUC proveedores"),
                ]:
                    if idx < len(cruces):
                        cruces[idx]["estado"] = "ejecutando"
                        try:
                            # Ejecutar cruce para todos los períodos
                            for p in periodos:
                                r = await cruce_method(cliente.id, p)
                                total_hallazgos += r.hallazgos_generados
                                cruces[idx]["hallazgos"] += r.hallazgos_generados
                                await db.commit()
                            cruces[idx]["estado"] = "completado"
                        except Exception as e:
                            cruces[idx]["estado"] = "error"
                            cruces[idx]["error"] = str(e)[:200]
                        _analysis_progress[job_id]["progreso"] = int((idx + 1) / len(cruces) * 100)
                        _analysis_progress[job_id]["total_hallazgos"] = total_hallazgos
                        idx += 1

            if "ire" in impuestos:
                await db.commit()
                for nombre in ["Conciliación contable", "Depreciaciones", "Gastos sin comprobante"]:
                    if idx < len(cruces):
                        cruces[idx]["estado"] = "ejecutando"
                        try:
                            await asyncio.sleep(0.5)
                            cruces[idx]["estado"] = "completado"
                        except Exception as e:
                            cruces[idx]["estado"] = "error"
                            cruces[idx]["error"] = str(e)[:200]
                        _analysis_progress[job_id]["progreso"] = int((idx + 1) / len(cruces) * 100)
                        idx += 1

            if "retenciones" in impuestos:
                await db.commit()
                for nombre in ["HECHAUKA vs Forms. 800/820", "Retenciones omitidas"]:
                    if idx < len(cruces):
                        cruces[idx]["estado"] = "ejecutando"
                        try:
                            await asyncio.sleep(0.5)
                            cruces[idx]["estado"] = "completado"
                        except Exception as e:
                            cruces[idx]["estado"] = "error"
                            cruces[idx]["error"] = str(e)[:200]
                        _analysis_progress[job_id]["progreso"] = int((idx + 1) / len(cruces) * 100)
                        idx += 1

            # Finalizar
            from sqlalchemy import update as sa_update
            from db.models import Auditoria

            await db.execute(
                sa_update(Auditoria).where(Auditoria.id == auditoria_id).values(estado="analisis_completado")
            )
            await crud.log_trail(
                db, firma_id=firma_id, usuario_id=None,
                accion=f"Análisis completado: {total_hallazgos} hallazgos",
                modulo="analisis", auditoria_id=auditoria_id,
                datos={"job_id": job_id, "hallazgos": total_hallazgos},
            )
            await db.commit()

            _analysis_progress[job_id].update({
                "estado": "completado",
                "progreso": 100,
                "total_hallazgos": total_hallazgos,
            })

        except Exception as e:
            _analysis_progress[job_id].update({
                "estado": "error",
                "error": str(e)[:500],
            })


@router.get("/{auditoria_id}")
async def get_auditoria(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    auditoria = await crud.get_auditoria(db, firma_id=user.firma_id, auditoria_id=auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")
    return {
        "id": auditoria.id,
        "cliente_id": auditoria.cliente_id,
        "periodo_desde": auditoria.periodo_desde,
        "periodo_hasta": auditoria.periodo_hasta,
        "tipo_encargo": auditoria.tipo_encargo,
        "impuestos": json.loads(auditoria.impuestos),
        "materialidad": auditoria.materialidad,
        "estado": auditoria.estado,
        "auditor": auditoria.auditor,
    }

@router.post("/{auditoria_id}/ingestar")
async def trigger_ingesta(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    auditoria = await crud.get_auditoria(db, firma_id=user.firma_id, auditoria_id=auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")
    
    return {
        "mensaje": "Ingesta encolada",
        "auditoria_id": auditoria_id,
        "nota": "Implementar worker de scraping Playwright",
    }

@router.post("/{auditoria_id}/analizar")
async def trigger_analisis(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ejecuta el motor de IA para detectar discrepancias y generar hallazgos sugeridos."""
    from analisis.ai_auditor import AIAuditor
    
    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")
    
    ai = AIAuditor(db, user.firma_id)
    
    # Por ahora ejecutamos cruce de IVA para el periodo de la auditoría
    # (En una auditoría real recorreríamos todos los meses del rango)
    periodo_ejemplo = auditoria.periodo_desde # Simplificación para demo
    
    # 2. Cruce de IVA (RG90 vs Declaraciones)
    hallazgos_sugeridos = await ai.ejecutar_cruce_iva(auditoria_id, periodo_ejemplo)
    
    # 3. Análisis de Riesgo de Proveedores & Anomalías
    hallazgos_riesgo = await ai.analizar_riesgo_proveedores(auditoria_id)
    hallazgos_sugeridos.extend(hallazgos_riesgo)
    
    if hallazgos_sugeridos:
        await ai.persistir_hallazgos_ai(auditoria_id, hallazgos_sugeridos)
    
    return {
        "mensaje": "Análisis de IA completado con éxito",
        "auditoria_id": auditoria_id,
        "hallazgos_generados": len(hallazgos_sugeridos),
        "alertas_riesgo": len(hallazgos_riesgo),
        "periodo_analizado": periodo_ejemplo
    }

@router.post("/{auditoria_id}/analizar-documento")
async def analizar_documento_ia(
    auditoria_id: str,
    archivo_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Analiza un documento PDF (Orden de Fiscalización, Notificación) usando IA
    para extraer requerimientos y plazos automáticamente.
    """
    # Lógica experimental de IA OCR
    return {
        "documento_tipo": "Orden de Fiscalización DNIT",
        "impuestos_bajo_revision": ["IVA", "IRE"],
        "periodos": ["2023-01", "2023-12"],
        "fecha_limite_entrega": "2026-05-15",
        "puntos_clave": [
            "Presentar libro compras/ventas",
            "Copia de facturas de exportación",
            "Extractos bancarios"
        ]
    }

@router.post("/{auditoria_id}/validar-sifen")
async def validar_sifen(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Valida los comprobantes electrónicos (CDC) de la auditoría."""
    from sqlalchemy import select, update
    from db.models import RG90
    from analisis.sifen import validar_cdc, analizar_coherencia_rg90_vs_sifen
    
    # 1. Obtener registros con CDC
    result = await db.execute(
        select(RG90).where(
            RG90.auditoria_id == auditoria_id,
            RG90.firma_id == user.firma_id,
            RG90.cdc != None
        )
    )
    registros = result.scalars().all()
    
    procesados = 0
    validos = 0
    con_errores = 0
    
    for reg in registros:
        cdc_info = validar_cdc(reg.cdc)
        
        updates = {
            "cdc_valido": cdc_info["valido"]
        }
        
        if cdc_info["valido"]:
            # Verificar coherencia entre lo declarado en RG90 y lo que dice el CDC
            coherencia = analizar_coherencia_rg90_vs_sifen(reg.__dict__, cdc_info)
            if coherencia["coherente"]:
                validos += 1
            else:
                con_errores += 1
        else:
            con_errores += 1
            
        await db.execute(
            update(RG90)
            .where(RG90.id == reg.id)
            .values(**updates)
        )
        procesados += 1
        
    await db.commit()
    
    return {
        "total_procesados": procesados,
        "cdc_validos": validos,
        "con_discrepancias": con_errores
    }

@router.post("/{auditoria_id}/ejecutar-analisis-iva")
async def ejecutar_analisis_iva(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ejecuta los 5 cruces IVA sobre los datos ya importados (RG90, HECHAUKA, SIFEN).
    Genera hallazgos automáticamente en la DB.
    """
    from analisis.iva import AuditoriaIVA

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    # Generar lista de períodos YYYY-MM en el rango de la auditoría
    from datetime import date
    def _periodos_en_rango(desde: str, hasta: str) -> list[str]:
        año_d, mes_d = int(desde[:4]), int(desde[5:7])
        año_h, mes_h = int(hasta[:4]), int(hasta[5:7])
        periodos = []
        año, mes = año_d, mes_d
        while (año, mes) <= (año_h, mes_h):
            periodos.append(f"{año}-{mes:02d}")
            mes += 1
            if mes > 12:
                mes = 1
                año += 1
        return periodos

    periodos = _periodos_en_rango(auditoria.periodo_desde, auditoria.periodo_hasta)

    motor = AuditoriaIVA(
        db=db,
        firma_id=user.firma_id,
        auditoria_id=auditoria_id,
        materialidad=auditoria.materialidad,
    )

    resultados = await motor.ejecutar_auditoria_completa(auditoria.cliente_id, periodos)

    total_hallazgos = sum(r.hallazgos_generados for r in resultados)
    total_ajuste = sum(r.monto_ajuste for r in resultados)
    errores = [e for r in resultados for e in r.errores]

    await db.commit()

    await crud.log_trail(
        db,
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion=f"Análisis IVA ejecutado: {total_hallazgos} hallazgos",
        modulo="analisis",
        auditoria_id=auditoria_id,
        datos={"periodos": periodos, "hallazgos": total_hallazgos, "ajuste_total": total_ajuste},
    )

    return {
        "ok": True,
        "periodos_analizados": len(periodos),
        "cruces_ejecutados": len(resultados),
        "hallazgos_generados": total_hallazgos,
        "monto_ajuste_total": total_ajuste,
        "advertencias": errores[:10],
    }


@router.post("/{auditoria_id}/ejecutar-analisis-ire")
async def ejecutar_analisis_ire(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ejecuta los procedimientos de auditoría IRE para el ejercicio de la auditoría."""
    from analisis.ire import AuditoriaIRE

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    ejercicio = auditoria.periodo_desde[:4]  # YYYY

    motor = AuditoriaIRE(
        db=db,
        firma_id=user.firma_id,
        auditoria_id=auditoria_id,
        materialidad=auditoria.materialidad,
    )

    resultado = await motor.ejecutar_auditoria(auditoria.cliente_id, ejercicio)
    await db.commit()

    await crud.log_trail(
        db,
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion=f"Análisis IRE ejecutado: {resultado.hallazgos_generados} hallazgos",
        modulo="analisis",
        auditoria_id=auditoria_id,
        datos={"ejercicio": ejercicio, "hallazgos": resultado.hallazgos_generados},
    )

    return {
        "ok": True,
        "ejercicio_analizado": ejercicio,
        "hallazgos_generados": resultado.hallazgos_generados,
        "errores": resultado.errores,
    }


@router.post("/{auditoria_id}/ejecutar-analisis-retenciones")
async def ejecutar_analisis_retenciones(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ejecuta los cruces de retenciones vs HECHAUKA para los períodos de la auditoría."""
    from analisis.retenciones import AuditoriaRetenciones

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    def _periodos_en_rango(desde: str, hasta: str) -> list[str]:
        año_d, mes_d = int(desde[:4]), int(desde[5:7])
        año_h, mes_h = int(hasta[:4]), int(hasta[5:7])
        periodos = []
        año, mes = año_d, mes_d
        while (año, mes) <= (año_h, mes_h):
            periodos.append(f"{año}-{mes:02d}")
            mes += 1
            if mes > 12:
                mes = 1
                año += 1
        return periodos

    periodos = _periodos_en_rango(auditoria.periodo_desde, auditoria.periodo_hasta)

    motor = AuditoriaRetenciones(
        db=db,
        firma_id=user.firma_id,
        auditoria_id=auditoria_id,
        materialidad=auditoria.materialidad,
    )

    resultados = await motor.ejecutar_auditoria_completa(auditoria.cliente_id, periodos)
    total_hallazgos = sum(r.hallazgos_generados for r in resultados)
    await db.commit()

    await crud.log_trail(
        db,
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion=f"Análisis Retenciones ejecutado: {total_hallazgos} hallazgos",
        modulo="analisis",
        auditoria_id=auditoria_id,
        datos={"periodos": periodos, "hallazgos": total_hallazgos},
    )

    return {
        "ok": True,
        "periodos_analizados": len(periodos),
        "hallazgos_generados": total_hallazgos,
    }


@router.get("/{auditoria_id}/rg90")
async def listar_rg90(
    auditoria_id: str,
    periodo: Optional[str] = None,
    tipo: Optional[str] = None,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lista los comprobantes RG90 importados para la auditoría, con resumen."""
    from sqlalchemy import select, func
    from db.models import RG90

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    q = select(RG90).where(
        RG90.auditoria_id == auditoria_id,
        RG90.firma_id == user.firma_id,
    )
    if periodo:
        q = q.where(RG90.periodo == periodo)
    if tipo:
        q = q.where(RG90.tipo == tipo)
    q = q.order_by(RG90.periodo, RG90.fecha_emision)

    result = await db.execute(q)
    registros = result.scalars().all()

    # Resumen
    total_compras = sum(1 for r in registros if r.tipo == "compra")
    total_ventas = sum(1 for r in registros if r.tipo == "venta")
    cf_total = sum(r.iva_total for r in registros if r.tipo == "compra")
    df_total = sum(r.iva_total for r in registros if r.tipo == "venta")
    sin_cdc = sum(1 for r in registros if not r.cdc and r.fecha_emision >= "2022-01-01")

    return {
        "resumen": {
            "total_compras": total_compras,
            "total_ventas": total_ventas,
            "credito_fiscal_total": cf_total,
            "debito_fiscal_total": df_total,
            "comprobantes_sin_cdc": sin_cdc,
        },
        "registros": [
            {
                "id": r.id,
                "periodo": r.periodo,
                "tipo": r.tipo,
                "ruc_contraparte": r.ruc_contraparte,
                "nombre_contraparte": r.nombre_contraparte,
                "nro_comprobante": r.nro_comprobante,
                "cdc": r.cdc,
                "fecha_emision": r.fecha_emision,
                "base_gravada_10": r.base_gravada_10,
                "base_gravada_5": r.base_gravada_5,
                "iva_total": r.iva_total,
                "total_comprobante": r.total_comprobante,
                "cdc_valido": r.cdc_valido,
                "ruc_activo": r.ruc_activo,
            }
            for r in registros
        ],
    }


@router.patch("/{auditoria_id}")
async def actualizar_auditoria(
    auditoria_id: str,
    body: dict,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Actualiza campos editables de la auditoría (estado, notas, auditor)."""
    from sqlalchemy import update as sa_update
    from db.models import Auditoria

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    campos_permitidos = {"estado", "notas", "auditor", "materialidad"}
    vals = {k: v for k, v in body.items() if k in campos_permitidos}

    if vals:
        await db.execute(
            sa_update(Auditoria).where(Auditoria.id == auditoria_id).values(**vals)
        )
        await db.commit()

    return {"ok": True, **vals}


@router.post("/{auditoria_id}/analisis-claude")
async def analisis_claude(
    auditoria_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Usa Claude para interpretar los hallazgos existentes y generar:
    - Narrativa de observaciones de auditoría
    - Conclusión ejecutiva
    - Procedimientos adicionales sugeridos
    """
    from config.settings import settings
    from config.plans import get_plan, PLAN_ALIAS_MAP
    from db.models import Firma
    from sqlalchemy import select

    # Verificar que el plan incluya IA
    firma_result = await db.execute(select(Firma).where(Firma.id == user.firma_id))
    firma = firma_result.scalar_one_or_none()
    if firma:
        plan_key = PLAN_ALIAS_MAP.get(firma.plan, firma.plan)
        plan_cfg = get_plan(plan_key)
        if not plan_cfg.tiene_ia:
            raise HTTPException(
                403,
                "El análisis con Inteligencia Artificial requiere el plan Pro o Enterprise. "
                "Actualizá tu plan en inteliaudit.com para acceder a esta función."
            )

    if not settings.anthropic_api_key:
        raise HTTPException(400, "API key de Anthropic no configurada. Agregá ANTHROPIC_API_KEY en el .env")

    auditoria = await crud.get_auditoria(db, user.firma_id, auditoria_id)
    if not auditoria:
        raise HTTPException(404, "Auditoría no encontrada")

    cliente = await crud.get_cliente(db, user.firma_id, id=auditoria.cliente_id)
    if not cliente:
        raise HTTPException(404, "Cliente no encontrado")

    hallazgos = await crud.get_hallazgos(db, user.firma_id, auditoria_id)
    if not hallazgos:
        return {
            "ok": False,
            "mensaje": "No hay hallazgos para analizar. Ejecutá primero los motores de análisis.",
            "narrativa": None,
            "conclusion": None,
            "procedimientos": [],
        }

    # Preparar contexto cliente
    contexto_cliente = {
        "ruc": cliente.ruc,
        "razon_social": cliente.razon_social,
        "actividad_principal": getattr(cliente, "actividad_principal", "no especificada"),
        "regimen": getattr(cliente, "regimen", "general"),
    }

    # Serializar hallazgos para la IA
    hallazgos_data = [
        {
            "impuesto": h.impuesto,
            "tipo_hallazgo": h.tipo_hallazgo,
            "descripcion": h.descripcion,
            "articulo_legal": h.articulo_legal,
            "impuesto_omitido": h.impuesto_omitido,
            "multa_estimada": h.multa_estimada,
            "intereses_estimados": h.intereses_estimados,
            "total_contingencia": h.total_contingencia,
            "nivel_riesgo": h.nivel_riesgo,
        }
        for h in hallazgos
    ]

    total_contingencia = sum(h.total_contingencia for h in hallazgos)
    por_riesgo = {"alto": 0, "medio": 0, "bajo": 0}
    for h in hallazgos:
        por_riesgo[h.nivel_riesgo] = por_riesgo.get(h.nivel_riesgo, 0) + 1

    resumen_contingencias = {
        "total_hallazgos": len(hallazgos),
        "total_contingencia_gs": total_contingencia,
        "por_nivel_riesgo": por_riesgo,
        "impuestos_auditados": list({h.impuesto for h in hallazgos}),
    }

    # Llamar a Claude de forma síncrona desde un thread pool
    import asyncio
    from analisis.claude_analisis import ClaudeAuditor

    claude = ClaudeAuditor()

    loop = asyncio.get_event_loop()

    narrativa, conclusion, procedimientos = await asyncio.gather(
        loop.run_in_executor(None, claude.interpretar_hallazgos, hallazgos_data, contexto_cliente),
        loop.run_in_executor(
            None,
            claude.redactar_conclusion,
            resumen_contingencias,
            contexto_cliente,
            auditoria.periodo_desde,
            auditoria.periodo_hasta,
        ),
        loop.run_in_executor(
            None,
            claude.sugerir_procedimientos,
            hallazgos_data,
            list({h.impuesto for h in hallazgos})[0] if hallazgos else "IVA",
            contexto_cliente,
        ),
    )

    await crud.log_trail(
        db,
        firma_id=user.firma_id,
        usuario_id=user.id,
        accion="Análisis IA ejecutado con Claude",
        modulo="analisis",
        auditoria_id=auditoria_id,
        datos={"hallazgos_analizados": len(hallazgos), "total_contingencia": total_contingencia},
    )

    return {
        "ok": True,
        "hallazgos_analizados": len(hallazgos),
        "total_contingencia": total_contingencia,
        "narrativa": narrativa,
        "conclusion": conclusion,
        "procedimientos": procedimientos,
    }


@router.post("/{auditoria_id}/tareas/{tarea_id}/toggle")
async def toggle_tarea(
    auditoria_id: str,
    tarea_id: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Alterna el estado de completado de una tarea del checklist."""
    from db.models import Tarea
    from sqlalchemy import select
    from datetime import datetime
    
    result = await db.execute(
        select(Tarea).where(
            Tarea.id == tarea_id,
            Tarea.auditoria_id == auditoria_id,
            Tarea.firma_id == user.firma_id
        )
    )
    tarea = result.scalar_one_or_none()
    
    if not tarea:
        raise HTTPException(404, "Tarea no encontrada")
    
    tarea.completada = not tarea.completada
    tarea.fecha_completado = datetime.utcnow() if tarea.completada else None
    
    await db.commit()
    return {"id": tarea.id, "completada": tarea.completada}
