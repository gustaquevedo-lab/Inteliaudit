"""
Worker para procesamiento de jobs en background.
Ejecuta scraper, análisis, y otras tareas pesadas.
"""
import asyncio
import json
import signal
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from rich.console import Console
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import AsyncSessionLocal, engine
from db.models import Job, CredencialMarangatu
from ingesta.marangatu import MarangatuScraper

console = Console()

# Flag para graceful shutdown
_shutdown_requested = False


def signal_handler(signum, frame):
    global _shutdown_requested
    console.print("[yellow]⚠[/] Shutdown signal recibido. Terminando jobs en curso...")
    _shutdown_requested = True


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


async def procesar_job(job_id: str) -> None:
    """Procesa un job individual."""
    async with AsyncSessionLocal() as db:
        # Obtener job
        result = await db.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        
        if not job:
            console.print(f"[red]✗[/] Job {job_id} no encontrado")
            return
        
        if job.estado != "pendiente":
            console.print(f"[yellow]⚠[/] Job {job_id} no está pendiente (estado: {job.estado})")
            return
        
        # Marcar como ejecutando
        await db.execute(
            update(Job).where(Job.id == job_id).values(
                estado="ejecutando",
                iniciado_en=datetime.now(),
            )
        )
        await db.commit()
        
        # Parsear params
        params = json.loads(job.params_json) if job.params_json else {}
        
        try:
            console.print(f"[blue]▶[/] Ejecutando job {job_id}: {job.tipo}")
            
            # Obtener credenciales
            cred_result = await db.execute(
                select(CredencialMarangatu).where(
                    CredencialMarangatu.id == params.get("credencial_id")
                )
            )
            cred = cred_result.scalar_one_or_none()
            
            if not cred:
                raise Exception("Credenciales no encontradas")
            
            # Descifrar credenciales
            from api.routers.auth import _descifrar_credencial
            ruc = _descifrar_credencial(cred.usuario_dnit_enc)
            clave = _descifrar_credencial(cred.clave_dnit_enc)
            
            # Ejecutar según tipo de job
            if job.tipo == "scraper_rg90":
                resultado = await ejecutar_scraper_rg90(db, job, ruc, clave, params)
            elif job.tipo == "scraper_hechauka":
                resultado = await ejecutar_scraper_hechauka(db, job, ruc, clave, params)
            elif job.tipo == "scraper_dj":
                resultado = await ejecutar_scraper_dj(db, job, ruc, clave, params)
            else:
                raise Exception(f"Tipo de job no soportado: {job.tipo}")
            
            # Marcar como completado
            await db.execute(
                update(Job).where(Job.id == job_id).values(
                    estado="completado",
                    progreso=100,
                    completado_en=datetime.now(),
                    resultado_json=json.dumps(resultado, ensure_ascii=False),
                )
            )
            await db.commit()
            
            console.print(f"[green]✓[/] Job {job_id} completado: {job.tipo}")
            
        except Exception as e:
            console.print(f"[red]✗[/] Job {job_id} falló: {e}")
            
            # Incrementar reintentos
            job_result = await db.execute(select(Job).where(Job.id == job_id))
            job = job_result.scalar_one()
            
            if job.reintentos < job.max_reintentos:
                # Re-encolar
                await db.execute(
                    update(Job).where(Job.id == job_id).values(
                        estado="pendiente",
                        reintentos=job.reintentos + 1,
                        error_msg=str(e),
                    )
                )
                console.print(f"[yellow]⚠[/] Job {job_id} re-encolado (intento {job.reintentos + 1}/{job.max_reintentos})")
            else:
                # Marcar como error definitivo
                await db.execute(
                    update(Job).where(Job.id == job_id).values(
                        estado="error",
                        error_msg=str(e),
                        completado_en=datetime.now(),
                    )
                )
                console.print(f"[red]✗[/] Job {job_id} falló definitivamente")
            
            await db.commit()


async def ejecutar_scraper_rg90(
    db: AsyncSession,
    job: Job,
    ruc: str,
    clave: str,
    params: dict,
) -> dict:
    """Ejecuta scraper de RG90."""
    from db import db as crud
    
    periodo_desde = params.get("periodo_desde")
    periodo_hasta = params.get("periodo_hasta")
    cliente_ruc = params.get("cliente_ruc")
    
    archivos_descargados = []
    
    async with MarangatuScraper(ruc, clave) as scraper:
        # Actualizar progreso
        await db.execute(update(Job).where(Job.id == job.id).values(progreso=10))
        await db.commit()
        
        # Descargar RG90
        archivos = await scraper.descargar_rg90_rango(periodo_desde, periodo_hasta)
        
        # Actualizar progreso
        await db.execute(update(Job).where(Job.id == job.id).values(progreso=70))
        await db.commit()
        
        # Parsear e importar archivos
        from ingesta.parser_rg90 import parsear_rg90
        
        for archivo in archivos:
            periodo = archivo.stem.replace("rg90_", "")
            registros = parsear_rg90(archivo, cliente_ruc, periodo)
            n = await crud.guardar_rg90_batch(db, job.firma_id, registros)
            archivos_descargados.append({
                "archivo": archivo.name,
                "periodo": periodo,
                "registros": n,
            })
            
            # Actualizar progreso incremental
            progreso_actual = 70 + int(30 * len(archivos_descargados) / len(archivos))
            await db.execute(update(Job).where(Job.id == job.id).values(progreso=progreso_actual))
            await db.commit()
    
    return {
        "archivos": archivos_descargados,
        "total_registros": sum(a["registros"] for a in archivos_descargados),
    }


async def ejecutar_scraper_hechauka(
    db: AsyncSession,
    job: Job,
    ruc: str,
    clave: str,
    params: dict,
) -> dict:
    """Ejecuta scraper de HECHAUKA."""
    from db import db as crud
    
    periodo_desde = params.get("periodo_desde")
    periodo_hasta = params.get("periodo_hasta")
    cliente_ruc = params.get("cliente_ruc")
    
    archivos_descargados = []
    
    async with MarangatuScraper(ruc, clave) as scraper:
        await db.execute(update(Job).where(Job.id == job.id).values(progreso=10))
        await db.commit()
        
        # Generar lista de períodos
        from ingesta.marangatu import _generar_periodos
        periodos = _generar_periodos(periodo_desde, periodo_hasta)
        
        for i, periodo in enumerate(periodos):
            try:
                archivo = await scraper.descargar_hechauka(periodo)
                archivos_descargados.append(archivo.name)
                
                # Actualizar progreso
                progreso = 10 + int(90 * (i + 1) / len(periodos))
                await db.execute(update(Job).where(Job.id == job.id).values(progreso=progreso))
                await db.commit()
                
                await asyncio.sleep(2)
            except Exception as e:
                console.print(f"[yellow]⚠[/] Error descargando HECHAUKA {periodo}: {e}")
    
    return {
        "archivos": archivos_descargados,
        "total_archivos": len(archivos_descargados),
    }


async def ejecutar_scraper_dj(
    db: AsyncSession,
    job: Job,
    ruc: str,
    clave: str,
    params: dict,
) -> dict:
    """Ejecuta scraper de declaraciones juradas."""
    async with MarangatuScraper(ruc, clave) as scraper:
        await db.execute(update(Job).where(Job.id == job.id).values(progreso=20))
        await db.commit()
        
        # Listar declaraciones
        declaraciones = await scraper.listar_declaraciones(
            formulario=params.get("formulario"),
            periodo_desde=params.get("periodo_desde"),
            periodo_hasta=params.get("periodo_hasta"),
        )
        
        await db.execute(update(Job).where(Job.id == job.id).values(progreso=50))
        await db.commit()
        
        # Descargar PDFs
        archivos_descargados = []
        for i, decl in enumerate(declaraciones):
            if decl.get("url_pdf"):
                nombre = f"dj_{decl['formulario']}_{decl['periodo']}.pdf"
                archivo = await scraper.descargar_declaracion_pdf(decl["url_pdf"], nombre)
                archivos_descargados.append(archivo.name)
                
                progreso = 50 + int(50 * (i + 1) / len(declaraciones))
                await db.execute(update(Job).where(Job.id == job.id).values(progreso=progreso))
                await db.commit()
                
                await asyncio.sleep(1)
    
    return {
        "declaraciones": len(declaraciones),
        "archivos": archivos_descargados,
    }


async def worker_loop() -> None:
    """Loop principal del worker."""
    console.print("[green]✓[/] Worker iniciado. Esperando jobs...")
    
    while not _shutdown_requested:
        async with AsyncSessionLocal() as db:
            # Buscar job pendiente más antiguo
            result = await db.execute(
                select(Job)
                .where(Job.estado == "pendiente")
                .order_by(Job.creado_en.asc())
                .limit(1)
            )
            job = result.scalar_one_or_none()
            
            if job:
                await procesar_job(job.id)
            else:
                # No hay jobs, esperar antes de volver a buscar
                await asyncio.sleep(5)


async def main():
    """Entry point del worker."""
    try:
        await worker_loop()
    except Exception as e:
        console.print(f"[red]✗[/] Worker falló: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
