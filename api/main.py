"""
FastAPI — servidor web principal de Inteliaudit.
"""
import json
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from db.base import get_db
from db import db as crud

# Routers
from api.routers.auth import router as auth_router
from api.routers.archivos import router as archivos_router
from api.routers.hallazgos import router as hallazgos_router
from api.routers.informes import router as informes_router
from api.routers.clientes import router as clientes_router
from api.routers.auditorias import router as auditorias_router
from api.routers.trail import router as trail_router
from api.routers.portal import router as portal_router
from api.routers.importacion import router as importacion_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.is_sqlite:
        subprocess.run(["alembic", "upgrade", "head"], check=False)
    yield


app = FastAPI(
    title="Inteliaudit API",
    description="SaaS de auditoría impositiva para Paraguay",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
#  API router con prefijo /api
# ============================================================

api = APIRouter(prefix="/api")

# Sub-routers especializados
api.include_router(auth_router)
api.include_router(archivos_router)
api.include_router(hallazgos_router)
api.include_router(informes_router)
api.include_router(clientes_router)
api.include_router(auditorias_router)
api.include_router(trail_router)
api.include_router(portal_router)
api.include_router(importacion_router)


# ============================================================
#  Dashboard — KPIs y métricas consolidadas
# ============================================================

@api.get("/dashboard")
async def get_dashboard(
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func
    from db.models import Auditoria, Cliente, Hallazgo, AuditTrail, Firma

    firma_id = user.firma_id

    # KPIs principales
    total_contingencia = await db.execute(
        select(func.coalesce(func.sum(Hallazgo.total_contingencia), 0))
        .where(Hallazgo.firma_id == firma_id, Hallazgo.estado != "descartado")
    )
    total_cont = total_contingencia.scalar() or 0

    aud_count = await db.execute(
        select(
            func.count(Auditoria.id).filter(Auditoria.estado.in_(["en_progreso", "analizando"])).label("activas"),
            func.count(Auditoria.id).filter(Auditoria.estado == "analisis_completado").label("cerradas"),
        ).where(Auditoria.firma_id == firma_id)
    )
    aud_row = aud_count.one()

    hallazgos_count = await db.execute(
        select(
            func.count(Hallazgo.id).filter(Hallazgo.estado == "pendiente").label("pendientes"),
            func.count(Hallazgo.id).filter(Hallazgo.nivel_riesgo == "alto", Hallazgo.estado != "descartado").label("alto_riesgo"),
        ).where(Hallazgo.firma_id == firma_id)
    )
    hal_row = hallazgos_count.one()

    clientes_count = await db.execute(
        select(func.count(Cliente.id)).where(Cliente.firma_id == firma_id)
    )
    total_clientes = clientes_count.scalar() or 0

    # Hallazgos por nivel de riesgo
    riesgo_rows = await db.execute(
        select(
            Hallazgo.nivel_riesgo,
            func.count(Hallazgo.id).label("cantidad"),
            func.coalesce(func.sum(Hallazgo.total_contingencia), 0).label("monto"),
        ).where(Hallazgo.firma_id == firma_id, Hallazgo.estado != "descartado")
        .group_by(Hallazgo.nivel_riesgo)
        .order_by(Hallazgo.nivel_riesgo)
    )
    hallazgos_por_riesgo = [
        {"nivel": r.nivel_riesgo, "cantidad": r.cantidad, "monto": r.monto}
        for r in riesgo_rows
    ]

    # Hallazgos por impuesto
    impuesto_rows = await db.execute(
        select(
            Hallazgo.impuesto,
            func.count(Hallazgo.id).label("cantidad"),
        ).where(Hallazgo.firma_id == firma_id, Hallazgo.estado != "descartado")
        .group_by(Hallazgo.impuesto)
        .order_by(func.count(Hallazgo.id).desc())
    )
    hallazgos_por_impuesto = [
        {"impuesto": r.impuesto, "cantidad": r.cantidad}
        for r in impuesto_rows
    ]

    # Top 5 clientes por contingencia
    top_clientes = await db.execute(
        select(
            Cliente.razon_social,
            Cliente.ruc,
            func.coalesce(func.sum(Hallazgo.total_contingencia), 0).label("contingencia"),
        )
        .join(Hallazgo, Hallazgo.auditoria_id == Auditoria.id)
        .join(Auditoria, Auditoria.cliente_id == Cliente.id)
        .where(Hallazgo.firma_id == firma_id, Hallazgo.estado != "descartado", Auditoria.firma_id == firma_id)
        .group_by(Cliente.id, Cliente.razon_social, Cliente.ruc)
        .order_by(func.sum(Hallazgo.total_contingencia).desc())
        .limit(5)
    )
    top_clientes_list = [
        {"razon_social": r.razon_social, "ruc": r.ruc, "contingencia": r.contingencia}
        for r in top_clientes
    ]

    # Actividad reciente (últimas 10 acciones)
    trail_rows = await db.execute(
        select(AuditTrail, Usuario.nombre.label("usuario_nombre"))
        .outerjoin(Usuario, AuditTrail.usuario_id == Usuario.id)
        .where(AuditTrail.firma_id == firma_id)
        .order_by(AuditTrail.timestamp.desc())
        .limit(10)
    )
    actividad_reciente = []
    for t, nombre in trail_rows:
        actividad_reciente.append({
            "accion": t.accion,
            "usuario": nombre or "Sistema",
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "auditoria": t.auditoria_id or "",
            "modulo": t.modulo or "",
        })

    tendencia_mensual = []
    import json
    periodos_usados = set()
    meses_data = await db.execute(
        select(
            Hallazgo.periodo,
            func.count(Hallazgo.id).label("hallazgos"),
            func.coalesce(func.sum(Hallazgo.total_contingencia), 0).label("contingencia"),
        ).where(Hallazgo.firma_id == firma_id, Hallazgo.estado != "descartado")
        .group_by(Hallazgo.periodo)
        .order_by(Hallazgo.periodo)
        .limit(12)
    )
    tendencia_mensual = [
        {"mes": r.periodo, "hallazgos": r.hallazgos, "contingencia": r.contingencia}
        for r in meses_data
    ]

    return {
        "kpis": {
            "total_contingencia": total_cont,
            "auditorias_activas": aud_row.activas or 0,
            "auditorias_cerradas": aud_row.cerradas or 0,
            "hallazgos_pendientes": hal_row.pendientes or 0,
            "hallazgos_alto_riesgo": hal_row.alto_riesgo or 0,
            "clientes_total": total_clientes,
        },
        "hallazgos_por_riesgo": hallazgos_por_riesgo,
        "hallazgos_por_impuesto": hallazgos_por_impuesto,
        "top_clientes_contingencia": top_clientes_list,
        "actividad_reciente": actividad_reciente,
        "tendencia_mensual": tendencia_mensual,
    }


# ============================================================
#  Health check
# ============================================================

@api.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# ============================================================
#  Roadmap state persistence
# ============================================================

_ROADMAP_STATE = Path(__file__).parent.parent / "roadmap-state.json"


@api.get("/roadmap-state")
async def get_roadmap_state():
    if _ROADMAP_STATE.exists():
        return json.loads(_ROADMAP_STATE.read_text(encoding="utf-8"))
    return {}


@api.put("/roadmap-state")
async def save_roadmap_state(body: dict):
    _ROADMAP_STATE.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


# ============================================================
#  Registrar el router principal en la app
# ============================================================

app.include_router(api)


# ============================================================
#  Landing page + activos estáticos del landing
# ============================================================

_LANDING_DIR = Path(__file__).parent.parent / "landing"
_LANDING = _LANDING_DIR / "index.html"


_ROADMAP_HTML = Path(__file__).parent.parent / "ROADMAP.html"


@app.get("/roadmap", response_class=FileResponse, include_in_schema=False)
async def serve_roadmap():
    return FileResponse(str(_ROADMAP_HTML))


@app.get("/", response_class=FileResponse, include_in_schema=False)
async def serve_landing():
    return FileResponse(str(_LANDING))


# Activos estáticos del landing (favicon.svg, páginas legales HTML, etc.)
@app.get("/{filename}", response_class=FileResponse, include_in_schema=False)
async def serve_landing_static(filename: str):
    """Sirve archivos estáticos del landing — favicon, páginas legales, etc."""
    # Excluir rutas que pertenecen a otros handlers
    if filename.startswith(("api", "app", "portal")):
        return FileResponse(str(_LANDING))
    requested = _LANDING_DIR / filename
    if requested.exists() and requested.is_file():
        return FileResponse(str(requested))
    return FileResponse(str(_LANDING))


# ============================================================
#  SPA frontend (Vite build — ui-web-dist/) montado en /app
# ============================================================

_UI_DIST = Path(__file__).parent.parent / "ui-web-dist"

app.mount("/app/assets", StaticFiles(directory=str(_UI_DIST / "assets")), name="vite-assets")


@app.get("/app/{full_path:path}", response_class=FileResponse, include_in_schema=False)
async def serve_spa(full_path: str):
    requested = _UI_DIST / full_path
    if requested.exists() and requested.is_file():
        return FileResponse(str(requested))
    return FileResponse(str(_UI_DIST / "index.html"))
