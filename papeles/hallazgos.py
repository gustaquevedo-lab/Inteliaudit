"""
Registro y gestión de hallazgos de auditoría.
Interfaz de alto nivel sobre la tabla hallazgos.
"""
import json
from typing import Optional

from rich.console import Console
from rich.table import Table
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.riesgo import formatear_pyg, resumir_contingencias
from db import db as crud

console = Console()

# Colores Rich por nivel de riesgo
COLORES_RIESGO = {"alto": "red", "medio": "yellow", "bajo": "green"}


class RegistroHallazgos:
    """
    Gestiona el ciclo de vida de hallazgos en una auditoría.
    Provee métodos para crear, actualizar, confirmar y reportar hallazgos.
    """

    def __init__(self, db: AsyncSession, auditoria_id: str):
        self.db = db
        self.auditoria_id = auditoria_id

    async def listar(
        self,
        impuesto: Optional[str] = None,
        estado: Optional[str] = None,
    ) -> list:
        return await crud.get_hallazgos(self.db, self.auditoria_id, impuesto, estado)

    async def confirmar(self, hallazgo_id: str, notas: Optional[str] = None) -> None:
        """Marca un hallazgo como confirmado por el auditor."""
        from sqlalchemy import update
        from db.models import Hallazgo
        vals: dict = {"estado": "confirmado"}
        if notas:
            vals["notas_auditor"] = notas
        await self.db.execute(update(Hallazgo).where(Hallazgo.id == hallazgo_id).values(**vals))

    async def descartar(self, hallazgo_id: str, notas: str) -> None:
        """Descarta un hallazgo con justificación."""
        from sqlalchemy import update
        from db.models import Hallazgo
        await self.db.execute(
            update(Hallazgo)
            .where(Hallazgo.id == hallazgo_id)
            .values(estado="descartado", notas_auditor=notas)
        )

    async def imprimir_resumen(self) -> None:
        """Imprime tabla de hallazgos en terminal con Rich."""
        hallazgos = await self.listar()
        if not hallazgos:
            console.print("[dim]Sin hallazgos registrados.[/]")
            return

        tabla = Table(title=f"Hallazgos — Auditoría {self.auditoria_id[:8]}...", show_lines=True)
        tabla.add_column("Impuesto", style="bold")
        tabla.add_column("Período")
        tabla.add_column("Tipo")
        tabla.add_column("Impuesto omitido", justify="right")
        tabla.add_column("Contingencia total", justify="right")
        tabla.add_column("Riesgo")
        tabla.add_column("Estado")

        for h in hallazgos:
            color = COLORES_RIESGO.get(h.nivel_riesgo, "white")
            tabla.add_row(
                h.impuesto,
                h.periodo,
                h.tipo_hallazgo,
                formatear_pyg(h.impuesto_omitido),
                formatear_pyg(h.total_contingencia),
                f"[{color}]{h.nivel_riesgo.upper()}[/{color}]",
                h.estado,
            )

        console.print(tabla)

        # Totales
        datos = [
            {
                "impuesto": h.impuesto,
                "impuesto_omitido": h.impuesto_omitido,
                "multa_estimada": h.multa_estimada,
                "intereses_estimados": h.intereses_estimados,
                "total_contingencia": h.total_contingencia,
                "nivel_riesgo": h.nivel_riesgo,
                "estado": h.estado,
            }
            for h in hallazgos
        ]
        resumen = resumir_contingencias(datos)
        console.print(f"\n[bold]Total contingencia estimada: Gs. {formatear_pyg(resumen['total_contingencia'])}[/bold]")
        console.print(f"  Impuesto omitido: Gs. {formatear_pyg(resumen['total_impuesto'])}")
        console.print(f"  Multas:           Gs. {formatear_pyg(resumen['total_multa'])}")
        console.print(f"  Intereses:        Gs. {formatear_pyg(resumen['total_intereses'])}")

    async def exportar_json(self) -> list[dict]:
        """Exporta todos los hallazgos como lista de dicts serializables."""
        hallazgos = await self.listar()
        return [
            {
                "id": h.id,
                "impuesto": h.impuesto,
                "periodo": h.periodo,
                "tipo_hallazgo": h.tipo_hallazgo,
                "descripcion": h.descripcion,
                "articulo_legal": h.articulo_legal,
                "base_ajuste": h.base_ajuste,
                "impuesto_omitido": h.impuesto_omitido,
                "multa_estimada": h.multa_estimada,
                "intereses_estimados": h.intereses_estimados,
                "total_contingencia": h.total_contingencia,
                "nivel_riesgo": h.nivel_riesgo,
                "estado": h.estado,
                "evidencias": json.loads(h.evidencias or "[]"),
                "notas_auditor": h.notas_auditor,
            }
            for h in hallazgos
        ]
