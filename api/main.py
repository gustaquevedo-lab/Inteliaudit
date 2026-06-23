"""
FastAPI — servidor web principal de Inteliaudit.
Seguridad: rate limiting, headers, CORS, logging estructurado.
"""
import json
import logging
import re
import subprocess
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from db.base import get_db
from db import db as crud
from api.routers.auth import get_current_user
from db.models import Usuario
from analytics import init_posthog, identify, capture, capture_exception


# ============================================================
#  Logging estructurado
# ============================================================

def _setup_logging():
    """Configura logging en formato JSON para produccion."""
    log_handler = logging.StreamHandler()
    log_handler.setLevel(logging.INFO)

    class JSONFormatter(logging.Formatter):
        def format(self, record):
            log_entry = {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if hasattr(record, "request_id"):
                log_entry["request_id"] = record.request_id
            if hasattr(record, "user_id"):
                log_entry["user_id"] = record.user_id
            return json.dumps(log_entry, ensure_ascii=False)

    if not settings.debug:
        log_handler.setFormatter(JSONFormatter())
        for logger_name in ("uvicorn", "uvicorn.access", "fastapi"):
            logger = logging.getLogger(logger_name)
            logger.handlers = []
            logger.addHandler(log_handler)
            logger.setLevel(logging.INFO)


_setup_logging()
logger = logging.getLogger("inteliaudit")


# ============================================================
#  Rate limiter
# ============================================================

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


# ============================================================
#  Security headers middleware (ASGI)
# ============================================================

class SecurityHeadersMiddleware:
    """Agrega headers de seguridad a todas las respuestas."""
    SECURITY_HEADERS = {
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' https://inteliaudit-production.up.railway.app https://inteliaudit.vercel.app wss://inteliaudit-production.up.railway.app; font-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Extraer origin de las cabeceras de la petición
        origin = None
        for k, v in scope.get("headers", []):
            if k == b"origin":
                try:
                    origin = v.decode("utf-8")
                except Exception:
                    pass
                break

        original_send = send

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                for header_name, header_value in self.SECURITY_HEADERS.items():
                    headers.append((header_name.lower().encode(), header_value.encode()))
                
                # Inyección manual de CORS como respaldo ante errores/excepciones
                if origin and origin in settings.allowed_origins:
                    has_cors = any(h[0] == b"access-control-allow-origin" for h in headers)
                    if not has_cors:
                        headers.append((b"access-control-allow-origin", origin.encode()))
                        headers.append((b"access-control-allow-credentials", b"true"))
                        headers.append((b"access-control-allow-methods", b"*".encode()))
                        headers.append((b"access-control-allow-headers", b"*".encode()))
                
                message["headers"] = headers
            await original_send(message)

        await self.app(scope, receive, send_with_headers)


# ============================================================
#  Request ID + timing middleware
# ============================================================

async def request_logging_middleware(request: Request, call_next):
    """Agrega request_id, logea duracion y status. Captura errores en PostHog."""
    request_id = str(uuid.uuid4())[:8]
    start = time.time()
    request.state.request_id = request_id

    # Identificar usuario en PostHog si hay token
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        try:
            from jose import jwt
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
            user_id = payload.get("sub", "")
            firma_id = payload.get("firma_id", "")
            if user_id:
                identify(user_id, {"firma_id": firma_id})
                request.state.ph_user_id = user_id
        except Exception:
            pass

    try:
        response = await call_next(request)
        elapsed = time.time() - start
        logger.info("request", extra={"request_id": request_id, "method": request.method, "path": request.url.path, "status": response.status_code, "duration_ms": int(elapsed * 1000)})
        response.headers["X-Request-ID"] = request_id

        # Capturar errores 500 en PostHog
        if response.status_code >= 500 and hasattr(request.state, "ph_user_id"):
            capture(request.state.ph_user_id, "server_error", {"path": request.url.path, "status": response.status_code})

        return response
    except Exception as e:
        elapsed = time.time() - start
        user_id = getattr(request.state, "ph_user_id", "anonymous")
        capture_exception(user_id, e, {"path": request.url.path, "method": request.method})
        raise


# ============================================================
#  Config validation
# ============================================================

def _validate_config():
    """Valida configuracion critica en startup. Logea warnings y errors."""
    warnings = []
    errors = []

    if not settings.debug:
        if settings.secret_key == "dev-secret-change-in-production":
            warnings.append("SECRET_KEY debe cambiarse para produccion (actualmente usa valor por defecto)")
        if not settings.encryption_key:
            warnings.append("ENCRYPTION_KEY vacio — credenciales Marangatu no podran cifrarse")
        if settings.is_sqlite:
            warnings.append("DATABASE_URL es SQLite — usar PostgreSQL en produccion")
        if not settings.anthropic_api_key:
            warnings.append("ANTHROPIC_API_KEY vacio — funciones IA deshabilitadas")
        if not settings.gemini_api_key and settings.ai_provider == "gemini":
            warnings.append("GEMINI_API_KEY vacio — IA con Gemini deshabilitada")
        allowed = settings.allowed_origins
        if any("localhost" in o or "127.0.0.1" in o for o in allowed):
            warnings.append("allowed_origins contiene localhost — revisar para produccion")

    for err in errors:
        logger.error(err)
    for warn in warnings:
        logger.warning(warn)



# ============================================================
#  Lifespan
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_posthog()
    _validate_config()
    # OpenTelemetry
    try:
        from telemetry import setup_telemetry
        setup_telemetry(app)
    except Exception:
        pass
    if not settings.is_sqlite:
        subprocess.run(["alembic", "upgrade", "head"], check=False)
    yield


# ============================================================
#  App
# ============================================================

app = FastAPI(
    title="Inteliaudit API",
    description="SaaS de auditoria impositiva para Paraguay",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Seguridad: headers
app.add_middleware(SecurityHeadersMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request ID + timing
app.middleware("http")(request_logging_middleware)


# ============================================================
#  Trial middleware
# ============================================================

@app.middleware("http")
async def trial_middleware(request: Request, call_next):
    if request.method == "GET" or any(p in request.url.path for p in ("/api/portal", "/api/auth", "/api/health")):
        return await call_next(request)

    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token:
        from jose import JWTError, jwt
        from db.models import Firma
        from sqlalchemy import select
        from db.base import AsyncSessionLocal
        try:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
            firma_id = payload.get("firma_id")
            if firma_id:
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(Firma).where(Firma.id == firma_id))
                    firma = result.scalar_one_or_none()
                    if firma and firma.plan == "trial" and firma.trial_hasta:
                        from datetime import datetime, timezone
                        if datetime.now(timezone.utc) > firma.trial_hasta:
                            response = JSONResponse(status_code=403, content={"detail": "Trial expirado. Elegi un plan para continuar."})
                            origin = request.headers.get("origin")
                            if origin and origin in settings.allowed_origins:
                                response.headers["Access-Control-Allow-Origin"] = origin
                                response.headers["Access-Control-Allow-Credentials"] = "true"
                            return response
        except Exception:
            pass
    return await call_next(request)


# ============================================================
#  Rate limiting por endpoint
# ============================================================

# Rate limiting por endpoint — usar el limiter global
# Los limites especificos se aplican via decorador @limiter.limit()



# ============================================================
#  API routers
# ============================================================

from api.routers.auth import router as auth_router
from api.routers.archivos import router as archivos_router
from api.routers.hallazgos import router as hallazgos_router
from api.routers.hallazgos import global_router as global_hallazgos_router
from api.routers.informes import router as informes_router
from api.routers.informes import _informes_router_v2 as informes_v2_router
from api.routers.clientes import router as clientes_router
from api.routers.auditorias import router as auditorias_router
from api.routers.trail import router as trail_router
from api.routers.portal import router as portal_router
from api.routers.importacion import router as importacion_router
from api.routers.suscripciones import router as suscripciones_router
from api.routers.jobs import router as jobs_router
from api.routers.superadmin import router as superadmin_router

api = APIRouter(prefix="/api")

api.include_router(auth_router)
api.include_router(archivos_router)
api.include_router(hallazgos_router)
api.include_router(global_hallazgos_router)
api.include_router(informes_router)
api.include_router(clientes_router)
api.include_router(auditorias_router)
api.include_router(trail_router)
api.include_router(portal_router)
api.include_router(importacion_router)
api.include_router(informes_v2_router)
api.include_router(suscripciones_router)
api.include_router(jobs_router)
api.include_router(superadmin_router)


# ============================================================
#  Dashboard
# ============================================================

@api.get("/dashboard")
async def get_dashboard(
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func
    from db.models import Auditoria, Cliente, Hallazgo, AuditTrail, Firma
    import traceback

    firma_id = user.firma_id

    try:
        return await _get_dashboard_data(db, firma_id)
    except Exception as e:
        logger.error(f"Dashboard error: {e}\n{traceback.format_exc()}")
        raise HTTPException(500, detail=str(e))


async def _get_dashboard_data(db: AsyncSession, firma_id: str):
    from sqlalchemy import select, func, case
    from db.models import Auditoria, Cliente, Hallazgo, AuditTrail, Firma

    total_contingencia = await db.execute(
        select(func.coalesce(func.sum(Hallazgo.total_contingencia), 0))
        .where(Hallazgo.firma_id == firma_id, Hallazgo.estado != "descartado")
    )
    total_cont = int(total_contingencia.scalar() or 0)

    aud_activas = (await db.execute(
        select(func.count(Auditoria.id))
        .where(Auditoria.firma_id == firma_id, Auditoria.estado.in_(["en_progreso", "analizando"]))
    )).scalar() or 0

    aud_cerradas = (await db.execute(
        select(func.count(Auditoria.id))
        .where(Auditoria.firma_id == firma_id, Auditoria.estado == "analisis_completado")
    )).scalar() or 0

    hal_pendientes = (await db.execute(
        select(func.count(Hallazgo.id))
        .where(Hallazgo.firma_id == firma_id, Hallazgo.estado == "pendiente")
    )).scalar() or 0

    hal_alto = (await db.execute(
        select(func.count(Hallazgo.id))
        .where(Hallazgo.firma_id == firma_id, Hallazgo.nivel_riesgo == "alto", Hallazgo.estado != "descartado")
    )).scalar() or 0

    total_clientes = (await db.execute(
        select(func.count(Cliente.id)).where(Cliente.firma_id == firma_id)
    )).scalar() or 0

    riesgo_rows = (await db.execute(
        select(Hallazgo.nivel_riesgo, func.count(Hallazgo.id).label("cantidad"), func.coalesce(func.sum(Hallazgo.total_contingencia), 0).label("monto"))
        .where(Hallazgo.firma_id == firma_id, Hallazgo.estado != "descartado")
        .group_by(Hallazgo.nivel_riesgo).order_by(Hallazgo.nivel_riesgo)
    )).all()

    impuesto_rows = (await db.execute(
        select(Hallazgo.impuesto, func.count(Hallazgo.id).label("cantidad"))
        .where(Hallazgo.firma_id == firma_id, Hallazgo.estado != "descartado")
        .group_by(Hallazgo.impuesto).order_by(func.count(Hallazgo.id).desc())
    )).all()

    top_clientes = (await db.execute(
        select(Cliente.razon_social, Cliente.ruc, func.coalesce(func.sum(Hallazgo.total_contingencia), 0).label("contingencia"))
        .select_from(Cliente)
        .join(Auditoria, Auditoria.cliente_id == Cliente.id)
        .join(Hallazgo, Hallazgo.auditoria_id == Auditoria.id)
        .where(Hallazgo.firma_id == firma_id, Hallazgo.estado != "descartado")
        .group_by(Cliente.id, Cliente.razon_social, Cliente.ruc)
        .order_by(func.sum(Hallazgo.total_contingencia).desc()).limit(5)
    )).all()

    trail_rows = (await db.execute(
        select(AuditTrail.accion, AuditTrail.timestamp, AuditTrail.auditoria_id, AuditTrail.modulo, Usuario.nombre)
        .outerjoin(Usuario, AuditTrail.usuario_id == Usuario.id)
        .where(AuditTrail.firma_id == firma_id)
        .order_by(AuditTrail.timestamp.desc()).limit(10)
    )).all()

    tendencia = (await db.execute(
        select(Hallazgo.periodo, func.count(Hallazgo.id).label("hallazgos"), func.coalesce(func.sum(Hallazgo.total_contingencia), 0).label("contingencia"))
        .where(Hallazgo.firma_id == firma_id, Hallazgo.estado != "descartado")
        .group_by(Hallazgo.periodo).order_by(Hallazgo.periodo).limit(12)
    )).all()

    return {
        "kpis": {
            "total_contingencia": total_cont,
            "auditorias_activas": int(aud_activas),
            "auditorias_cerradas": int(aud_cerradas),
            "hallazgos_pendientes": int(hal_pendientes),
            "hallazgos_alto_riesgo": int(hal_alto),
            "clientes_total": int(total_clientes),
        },
        "hallazgos_por_riesgo": [{"nivel": r.nivel_riesgo, "cantidad": int(r.cantidad), "monto": int(r.monto)} for r in riesgo_rows],
        "hallazgos_por_impuesto": [{"impuesto": r.impuesto, "cantidad": int(r.cantidad)} for r in impuesto_rows],
        "top_clientes_contingencia": [{"razon_social": r.razon_social, "ruc": r.ruc, "contingencia": int(r.contingencia)} for r in top_clientes],
        "actividad_reciente": [{"accion": r.accion, "usuario": r.nombre or "Sistema", "timestamp": r.timestamp.isoformat() if r.timestamp else None, "auditoria": r.auditoria_id or "", "modulo": r.modulo or ""} for r in trail_rows],
        "tendencia_mensual": [{"mes": r.periodo, "hallazgos": int(r.hallazgos), "contingencia": int(r.contingencia)} for r in tendencia],
    }


# ============================================================
#  Health check
# ============================================================

@api.get("/health")
async def health():
    storage_ok = False
    try:
        from storage.adapter import get_storage
        s = get_storage()
        key = "_health_check.txt"
        await s.upload(key, b"ok", "text/plain")
        data = await s.download(key)
        storage_ok = data == b"ok"
        await s.delete(key)
    except Exception:
        pass
    return {"status": "ok", "version": "0.1.0", "storage": "r2" if storage_ok and hasattr(s, "_bucket") else "local" if storage_ok else "error"}


# ============================================================
#  Roadmap state
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


app.include_router(api)


# ============================================================
#  WebSocket — progreso en tiempo real
# ============================================================

@app.websocket("/ws/{firma_id}")
async def websocket_endpoint(websocket, firma_id: str):
    from websocket_manager import ws_manager
    await ws_manager.connect(websocket, firma_id)
    try:
        while True:
            data = await websocket.receive_text()
            # Keepalive / commands from client
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(websocket, firma_id)


@app.get("/", include_in_schema=False)
async def root():
    return {"status": "ok", "service": "inteliaudit-api"}
