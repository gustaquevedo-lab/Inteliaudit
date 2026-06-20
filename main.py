"""
Inteliaudit — CLI principal.
Orquesta ingesta, análisis y generación de informes desde la terminal.
"""
import asyncio
import json
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

console = Console()


# ============================================================
#  Helpers multi-tenant para CLI
# ============================================================

async def _get_cli_firma_id(db) -> str:
    """Obtiene o crea la firma 'CLI' para uso desde terminal."""
    from sqlalchemy import select
    from db.models import Firma
    result = await db.execute(select(Firma).where(Firma.nombre == "CLI"))
    firma = result.scalar_one_or_none()
    if firma:
        return firma.id
    from db.base import init_db
    await init_db()
    result = await db.execute(select(Firma).where(Firma.nombre == "CLI"))
    firma = result.scalar_one_or_none()
    if firma:
        return firma.id
    # Crear firma CLI manualmente
    firma = Firma(nombre="CLI", plan="enterprise")
    db.add(firma)
    await db.flush()
    return firma.id


# ============================================================
#  Entry point
# ============================================================

@click.group()
@click.version_option("0.1.0", prog_name="inteliaudit")
def cli():
    """
    Inteliaudit — Auditoría impositiva automatizada para Paraguay.
    """
    pass


# ============================================================
#  Base de datos
# ============================================================

@cli.command("db-init")
def db_init():
    """Inicializa la base de datos (desarrollo). En producción usar Alembic."""
    async def _run():
        from db.base import init_db
        await init_db()
        console.print("[green]OK[/] Base de datos inicializada.")
    asyncio.run(_run())


# ============================================================
#  Clientes
# ============================================================

@cli.group()
def cliente():
    """Gestión de contribuyentes."""
    pass


@cliente.command("crear")
@click.option("--ruc", prompt="RUC (ej: 80012345-6)", help="RUC del contribuyente")
@click.option("--razon-social", prompt="Razón social", help="Nombre legal")
@click.option("--regimen", prompt="Régimen", type=click.Choice(["general", "simplificado", "pequeno"]), default="general")
@click.option("--actividad", default=None, help="Actividad principal")
def cliente_crear(ruc: str, razon_social: str, regimen: str, actividad: Optional[str]):
    """Registra un nuevo contribuyente."""
    async def _run():
        from db.base import AsyncSessionLocal
        from db import db as crud
        async with AsyncSessionLocal() as db:
            firma_id = await _get_cli_firma_id(db)
            try:
                c = await crud.crear_cliente(
                    db,
                    firma_id=firma_id,
                    ruc=ruc,
                    razon_social=razon_social,
                    regimen=regimen,
                    actividad_principal=actividad,
                )
                await db.commit()
                console.print(f"[green]✓[/] Cliente registrado: {c.razon_social} (RUC {c.ruc})")
            except Exception as e:
                console.print(f"[red]✗[/] Error: {e}")
    asyncio.run(_run())


@cliente.command("listar")
def cliente_listar():
    """Lista todos los contribuyentes registrados."""
    async def _run():
        from db.base import AsyncSessionLocal
        from db import db as crud
        async with AsyncSessionLocal() as db:
            firma_id = await _get_cli_firma_id(db)
            clientes = await crud.listar_clientes(db, firma_id)
        if not clientes:
            console.print("[dim]Sin clientes registrados.[/]")
            return
        from rich.table import Table
        tabla = Table(title="Contribuyentes")
        tabla.add_column("RUC", style="bold")
        tabla.add_column("Razón Social")
        tabla.add_column("Régimen")
        tabla.add_column("Estado SET")
        for c in clientes:
            tabla.add_row(c.ruc, c.razon_social, c.regimen, c.estado_dnit)
        console.print(tabla)
    asyncio.run(_run())


# ============================================================
#  Auditorías
# ============================================================

@cli.group()
def auditoria():
    """Gestión de auditorías."""
    pass


@auditoria.command("nueva")
@click.option("--ruc", prompt="RUC del cliente")
@click.option("--desde", prompt="Período desde (YYYY-MM)", help="Ej: 2024-01")
@click.option("--hasta", prompt="Período hasta (YYYY-MM)", help="Ej: 2024-12")
@click.option("--impuestos", default="IVA,IRE", help="Impuestos separados por coma")
@click.option("--materialidad", default=500000, help="Materialidad en Gs.")
@click.option("--auditor", default=None, help="Nombre del auditor")
def auditoria_nueva(ruc: str, desde: str, hasta: str, impuestos: str, materialidad: int, auditor: Optional[str]):
    """Crea una nueva auditoría."""
    async def _run():
        from db.base import AsyncSessionLocal
        from db import db as crud
        impuestos_list = [i.strip().upper() for i in impuestos.split(",")]
        async with AsyncSessionLocal() as db:
            firma_id = await _get_cli_firma_id(db)
            cliente = await crud.get_cliente(db, firma_id, ruc=ruc)
            if not cliente:
                console.print(f"[red]✗[/] Cliente {ruc} no encontrado.")
                return
            a = await crud.crear_auditoria(
                db,
                firma_id=firma_id,
                cliente_id=cliente.id,
                periodo_desde=desde,
                periodo_hasta=hasta,
                impuestos=impuestos_list,
                materialidad=materialidad,
                auditor=auditor,
            )
            console.print(Panel(
                f"[bold]Auditoría creada[/bold]\n"
                f"ID: {a.id}\n"
                f"Cliente: {cliente.razon_social}\n"
                f"Período: {desde} a {hasta}\n"
                f"Impuestos: {', '.join(impuestos_list)}\n"
                f"Materialidad: Gs. {materialidad:,}",
                title="[green]Nueva Auditoría[/green]",
            ))
    asyncio.run(_run())


@auditoria.command("listar")
@click.option("--ruc", default=None, help="Filtrar por RUC")
def auditoria_listar(ruc: Optional[str]):
    """Lista auditorías."""
    async def _run():
        from db.base import AsyncSessionLocal
        from db import db as crud
        async with AsyncSessionLocal() as db:
            firma_id = await _get_cli_firma_id(db)
            if ruc:
                cliente = await crud.get_cliente(db, firma_id, ruc=ruc)
                cliente_id = cliente.id if cliente else None
            else:
                cliente_id = None
            auditorias = await crud.listar_auditorias(db, firma_id, cliente_id)
        if not auditorias:
            console.print("[dim]Sin auditorías.[/]")
            return
        from rich.table import Table
        tabla = Table(title="Auditorías")
        tabla.add_column("ID", style="dim")
        tabla.add_column("Cliente ID")
        tabla.add_column("Período")
        tabla.add_column("Estado")
        for a in auditorias:
            tabla.add_row(a.id[:8] + "...", a.cliente_id[:8] + "...", f"{a.periodo_desde} → {a.periodo_hasta}", a.estado)
        console.print(tabla)
    asyncio.run(_run())


# ============================================================
#  Ingesta
# ============================================================

@cli.group()
def ingestar():
    """Descarga de datos desde Marangatú y otras fuentes."""
    pass


@ingestar.command("rg90")
@click.argument("archivo", type=click.Path(exists=True, path_type=Path))
@click.option("--ruc", prompt="RUC del cliente")
@click.option("--periodo", prompt="Período (YYYY-MM)")
@click.option("--auditoria-id", default=None, help="ID de auditoría activa")
def ingestar_rg90(archivo: Path, ruc: str, periodo: str, auditoria_id: Optional[str]):
    """Importa un archivo XLSX de RG90 descargado de Marangatú."""
    async def _run():
        from ingesta.parser_rg90 import parsear_rg90
        from db.base import AsyncSessionLocal
        from db import db as crud

        async with AsyncSessionLocal() as db:
            firma_id = await _get_cli_firma_id(db)
            cliente = await crud.get_cliente(db, firma_id, ruc=ruc)
            if not cliente:
                console.print(f"[red]✗[/] Cliente {ruc} no encontrado.")
                return
            registros = parsear_rg90(archivo, cliente.id, periodo, auditoria_id)
            n = await crud.guardar_rg90_batch(db, firma_id, registros)
            await db.commit()
        console.print(f"[green]✓[/] {n} comprobantes RG90 importados.")
    asyncio.run(_run())


@ingestar.command("marangatu")
@click.option("--ruc", prompt="RUC del contribuyente")
@click.option("--clave", prompt="Clave Marangatú", hide_input=True)
@click.option("--desde", prompt="Período desde (YYYY-MM)")
@click.option("--hasta", prompt="Período hasta (YYYY-MM)")
def ingestar_marangatu(ruc: str, clave: str, desde: str, hasta: str):
    """Descarga datos de Marangatú via Playwright (scraper automático)."""
    async def _run():
        from ingesta.marangatu import MarangatuScraper
        console.print(f"[blue]Iniciando scraping Marangatú para RUC {ruc}...[/]")
        async with MarangatuScraper(ruc, clave) as scraper:
            archivos = await scraper.descargar_rg90_rango(desde, hasta)
            console.print(f"[green]✓[/] {len(archivos)} archivos RG90 descargados.")
    asyncio.run(_run())


# ============================================================
#  Análisis
# ============================================================

@cli.group()
def analizar():
    """Ejecución de procedimientos de auditoría."""
    pass


@analizar.command("iva")
@click.option("--auditoria-id", prompt="ID de auditoría")
def analizar_iva(auditoria_id: str):
    """Ejecuta todos los procedimientos de auditoría IVA."""
    async def _run():
        from db.base import AsyncSessionLocal
        from db import db as crud
        from analisis.iva import AuditoriaIVA
        from ingesta.marangatu import _generar_periodos

        async with AsyncSessionLocal() as db:
            firma_id = await _get_cli_firma_id(db)
            auditoria = await crud.get_auditoria(db, firma_id, auditoria_id)
            if not auditoria:
                console.print(f"[red]✗[/] Auditoría {auditoria_id} no encontrada.")
                return

            periodos = _generar_periodos(auditoria.periodo_desde, auditoria.periodo_hasta)
            auditor = AuditoriaIVA(db, firma_id, auditoria_id, auditoria.materialidad)
            resultados = await auditor.ejecutar_auditoria_completa(auditoria.cliente_id, periodos)
            await db.commit()

        total_hallazgos = sum(r.hallazgos_generados for r in resultados)
        console.print(f"[green]✓[/] Análisis IVA completado. {total_hallazgos} hallazgos generados.")
    asyncio.run(_run())


# ============================================================
#  Informes
# ============================================================

@cli.group()
def informe():
    """Generación de informes de auditoría."""
    pass


@informe.command("generar")
@click.option("--auditoria-id", prompt="ID de auditoría")
@click.option("--output", default=None, help="Directorio de salida")
def informe_generar(auditoria_id: str, output: Optional[str]):
    """Genera informe de auditoría en Word y PDF."""
    async def _run():
        from db.base import AsyncSessionLocal
        from informes.render import RenderInforme

        async with AsyncSessionLocal() as db:
            render = RenderInforme(db)
            paths = await render.generar_informe_auditoria(
                auditoria_id,
                output_dir=Path(output) if output else None,
            )
            await db.commit()

        console.print("[green]✓[/] Informe generado:")
        for tipo, path in paths.items():
            console.print(f"  {tipo}: {path}")
    asyncio.run(_run())


# ============================================================
#  Servidor web
# ============================================================

@cli.command("serve")
@click.option("--host", default="0.0.0.0", help="Host")
@click.option("--port", default=8000, help="Puerto")
@click.option("--reload", is_flag=True, help="Auto-reload (desarrollo)")
def serve(host: str, port: int, reload: bool):
    """Inicia el servidor web FastAPI."""
    import uvicorn
    uvicorn.run("api.main:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    cli()
