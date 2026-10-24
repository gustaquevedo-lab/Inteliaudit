"""
Sentry-Lite — Middleware y capturador centralizado de errores de plataforma con deduplicación por fingerprint SHA-256.
"""
import hashlib
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from typing import Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select

from config.settings import settings
from db.base import AsyncSessionLocal, get_db
from db.models import ErrorPlataforma

logger = logging.getLogger("inteliaudit.errors")


def calcular_fingerprint(exc: Exception, tb_obj=None) -> str:
    """Calcula un hash determinista SHA-256 basado en el tipo de excepción y el último frame del código fuente."""
    if tb_obj is None:
        tb_obj = sys.exc_info()[2]
    frames = traceback.extract_tb(tb_obj)
    last_frame = frames[-1] if frames else None
    frame_str = f"{last_frame.filename}:{last_frame.lineno}" if last_frame else "unknown"
    raw_key = f"{type(exc).__name__}:{frame_str}"
    return hashlib.sha256(raw_key.encode()).hexdigest()


def extraer_datos_auth(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """Extrae email de usuario y firma_id desde el header Authorization si está presente."""
    user_email = None
    firma_id = None
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        try:
            from jose import jwt
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
            user_email = payload.get("sub")
            firma_id = payload.get("firma_id")
        except Exception:
            pass
    return user_email, firma_id


def extraer_contexto(request: Request) -> str:
    """Serializa contexto HTTP sanitizado a JSON."""
    try:
        headers_dict = dict(request.headers)
        for sensitive in ("authorization", "cookie", "x-api-key"):
            if sensitive in headers_dict:
                headers_dict[sensitive] = "[REDACTED]"

        ctx = {
            "client_ip": request.client.host if request.client else "unknown",
            "query_params": dict(request.query_params),
            "headers": headers_dict,
        }
        return json.dumps(ctx, ensure_ascii=False)
    except Exception:
        return "{}"


async def registrar_error_plataforma(exc: Exception, request: Request, app_instance: Optional[FastAPI] = None) -> Tuple[str, str]:
    """
    Registra o deduplica la excepción en la tabla errores_plataforma.
    Retorna (error_id, fingerprint).
    """
    tb_obj = sys.exc_info()[2]
    fingerprint = calcular_fingerprint(exc, tb_obj)
    stacktrace = "".join(traceback.format_exception(type(exc), exc, tb_obj))
    user_email, firma_id = extraer_datos_auth(request)
    contexto = extraer_contexto(request)
    tipo_error = type(exc).__name__
    mensaje = str(exc)
    path = request.url.path
    metodo = request.method

    target_app = app_instance or getattr(request, "app", None)
    is_override = False
    session = None

    if target_app and hasattr(target_app, "dependency_overrides") and get_db in target_app.dependency_overrides:
        try:
            override_fn = target_app.dependency_overrides[get_db]
            gen = override_fn()
            session = await anext(gen)
            is_override = True
        except Exception:
            session = None

    if session is None:
        session = AsyncSessionLocal()
        is_override = False

    error_id = ""
    try:
        stmt = select(ErrorPlataforma).where(ErrorPlataforma.fingerprint == fingerprint)
        result = await session.execute(stmt)
        err = result.scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if err:
            err.ocurrencias += 1
            err.ultima_vez = now
            err.mensaje = mensaje
            err.stacktrace = stacktrace
            err.path = path
            err.metodo = metodo
            if err.resuelto:
                err.resuelto = False
                err.resuelto_en = None
            error_id = err.id
        else:
            err = ErrorPlataforma(
                fingerprint=fingerprint,
                tipo_error=tipo_error,
                mensaje=mensaje,
                path=path,
                metodo=metodo,
                status_code=500,
                stacktrace=stacktrace,
                contexto_json=contexto,
                firma_id=firma_id,
                usuario_email=user_email,
                ocurrencias=1,
                primera_vez=now,
                ultima_vez=now,
                resuelto=False,
            )
            session.add(err)
            await session.flush()
            error_id = err.id

        await session.commit()
    except Exception as db_err:
        logger.error(f"Error guardando telemetría de plataforma: {db_err}", exc_info=True)
        if not is_override:
            await session.rollback()
    finally:
        if not is_override:
            await session.close()

    return error_id, fingerprint


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Manejador global FastAPI para excepciones 500 no controladas."""
    error_id, fingerprint = await registrar_error_plataforma(exc, request)
    logger.error(f"Unhandled 500 [{fingerprint}] on {request.method} {request.url.path}: {exc}", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Error interno del servidor",
            "error_id": error_id,
            "fingerprint": fingerprint,
            "tipo_error": type(exc).__name__,
        },
    )
