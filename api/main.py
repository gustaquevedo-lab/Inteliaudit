"""
FastAPI — servidor web principal de Inteliaudit.
"""
import json
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
from db.base import get_db, init_db
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
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


# ============================================================
#  Health check
# ============================================================

@api.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# ============================================================
#  Registrar el router principal en la app
# ============================================================

app.include_router(api)


# ============================================================
#  Landing page — siempre en "/"
# ============================================================

_LANDING = Path(__file__).parent.parent / "landing" / "index.html"


@app.get("/", response_class=FileResponse, include_in_schema=False)
async def serve_landing():
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
