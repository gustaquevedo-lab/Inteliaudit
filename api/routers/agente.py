"""
Router para el Agente Auditor Forense con Tool Calling y Memoria de Conversaciones.
"""
import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import requests

from config.settings import settings
from db.base import get_db, AsyncSessionLocal
from api.routers.auth import get_current_user
from db.models import Usuario, Auditoria, Cliente, AgenteConversacion, AgenteMensaje
from analisis.agente_tools import ESQUEMA_HERRAMIENTAS, ejecutar_herramienta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auditorias/{auditoria_id}/agente", tags=["agente-forense"])


class ConversacionCreate(BaseModel):
    titulo: str = "Nueva consulta forense"


class ChatMessageRequest(BaseModel):
    pregunta: str
    conversacion_id: Optional[str] = None


@router.get("/conversaciones")
async def listar_conversaciones(
    auditoria_id: str,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    stmt = (
        select(AgenteConversacion)
        .where(
            AgenteConversacion.firma_id == user.firma_id,
            AgenteConversacion.auditoria_id == auditoria_id
        )
        .order_by(AgenteConversacion.actualizado_en.desc())
    )
    res = await db.execute(stmt)
    convs = res.scalars().all()
    return [
        {
            "id": c.id,
            "titulo": c.titulo,
            "creado_en": c.creado_en.isoformat() if c.creado_en else None,
            "actualizado_en": c.actualizado_en.isoformat() if c.actualizado_en else None
        }
        for c in convs
    ]


@router.post("/conversaciones")
async def crear_conversacion(
    auditoria_id: str,
    body: ConversacionCreate,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    conv = AgenteConversacion(
        firma_id=user.firma_id,
        auditoria_id=auditoria_id,
        usuario_id=user.id,
        titulo=body.titulo
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return {"id": conv.id, "titulo": conv.titulo}


@router.get("/conversaciones/{conv_id}/mensajes")
async def obtener_mensajes_conversacion(
    auditoria_id: str,
    conv_id: str,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    # Verificar pertenencia de la conversación
    res_c = await db.execute(
        select(AgenteConversacion).where(
            AgenteConversacion.id == conv_id,
            AgenteConversacion.firma_id == user.firma_id,
            AgenteConversacion.auditoria_id == auditoria_id
        )
    )
    if not res_c.scalar_one_or_none():
        raise HTTPException(404, "Conversación no encontrada")

    res_m = await db.execute(
        select(AgenteMensaje)
        .where(AgenteMensaje.conversacion_id == conv_id)
        .order_by(AgenteMensaje.creado_en.asc())
    )
    mensajes = res_m.scalars().all()
    return [
        {
            "id": m.id,
            "rol": m.rol,
            "contenido": m.contenido,
            "herramientas_usadas": m.herramientas_usadas,
            "creado_en": m.creado_en.isoformat() if m.creado_en else None
        }
        for m in mensajes
    ]


@router.post("/chat")
async def chat_agente_forense(
    auditoria_id: str,
    body: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    """
    Endpoint de chat en streaming con ejecución recursiva de herramientas (Tool Calling).
    """
    res_aud = await db.execute(
        select(Auditoria, Cliente)
        .join(Cliente, Auditoria.cliente_id == Cliente.id)
        .where(
            Auditoria.id == auditoria_id,
            Auditoria.firma_id == user.firma_id
        )
    )
    row = res_aud.first()
    if not row:
        raise HTTPException(404, "Auditoría no encontrada")
    auditoria, cliente = row

    # Obtener o crear conversación persistente
    conv_id = body.conversacion_id
    if not conv_id:
        conv = AgenteConversacion(
            firma_id=user.firma_id,
            auditoria_id=auditoria_id,
            usuario_id=user.id,
            titulo=body.pregunta[:50]
        )
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        conv_id = conv.id
    else:
        # Verificar pertenencia
        c_check = await db.execute(
            select(AgenteConversacion).where(
                AgenteConversacion.id == conv_id,
                AgenteConversacion.firma_id == user.firma_id
            )
        )
        if not c_check.scalar_one_or_none():
            raise HTTPException(403, "Conversación no autorizada")

    # Guardar mensaje del usuario
    msg_user = AgenteMensaje(
        conversacion_id=conv_id,
        rol="user",
        contenido=body.pregunta
    )
    db.add(msg_user)
    await db.commit()

    # Cargar historial reciente de la conversación
    res_hist = await db.execute(
        select(AgenteMensaje)
        .where(AgenteMensaje.conversacion_id == conv_id)
        .order_by(AgenteMensaje.creado_en.asc())
        .limit(10)
    )
    historial = res_hist.scalars().all()

    system_prompt = f"""Sos el AGENTE AUDITOR FORENSE experto de Inteliaudit para la República del Paraguay.
Tenés dominio pleno de la Ley 6380/2019, Decretos 3107/19 y 3181/19, RG 90/2021, Ley 125/1991 y NIAs (230, 500, 520).

LÍMITES DUROS DE SEGURIDAD (PERÍMETRO DEL CLIENTE):
- Solo podés analizar datos del CLIENTE EN SESIÓN: {cliente.razon_social} (RUC {cliente.ruc}).
- Período auditado: {auditoria.periodo_desde} a {auditoria.periodo_hasta}.
- Jamás inventes datos ni menciones otras empresas o RUCs no relacionados.
- Siempre que cites leyes, indicá el Artículo e Inciso exacto.
- Si necesitás verificar compras, normativas o relaciones, USÁ LAS HERRAMIENTAS provistas (consultar_normativa_legal, buscar_comprobantes_cliente, consultar_relaciones_proveedor, recalcular_contingencia_fiscal).
"""

    messages_payload: list[dict] = [{"role": "system", "content": system_prompt}]
    for m in historial:
        messages_payload.append({"role": m.rol, "content": m.contenido})

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": messages_payload,
        "tools": ESQUEMA_HERRAMIENTAS,
        "stream": True,
        "options": {
            "temperature": 0.1,
            "num_thread": 8
        }
    }

    async def event_generator():
        yield f"data: {json.dumps({'type': 'init', 'conversacion_id': conv_id})}\n\n"
        full_content = []
        tools_executed = []

        try:
            with requests.post(url, json=payload, stream=True, timeout=120) as r:
                tool_calls_pending = []
                for line in r.iter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    msg = chunk.get("message", {})
                    content_piece = msg.get("content", "")
                    if content_piece:
                        full_content.append(content_piece)
                        yield f"data: {json.dumps({'type': 'content', 'delta': content_piece})}\n\n"

                    # Capturar llamadas de herramienta
                    t_calls = msg.get("tool_calls")
                    if t_calls:
                        tool_calls_pending.extend(t_calls)

                    if chunk.get("done", False):
                        break

                # Si el modelo solicitó herramientas, ejecutarlas
                if tool_calls_pending:
                    for tc in tool_calls_pending:
                        fn = tc.get("function", {})
                        fn_name = fn.get("name")
                        fn_args = fn.get("arguments", {})
                        if isinstance(fn_args, str):
                            try:
                                fn_args = json.loads(fn_args)
                            except Exception:
                                fn_args = {}

                        yield f"data: {json.dumps({'type': 'tool_call', 'name': fn_name, 'args': fn_args})}\n\n"
                        tools_executed.append({"name": fn_name, "args": fn_args})

                        # Ejecutar herramienta en base de datos
                        async with AsyncSessionLocal() as session_tool:
                            tool_result = await ejecutar_herramienta(
                                fn_name,
                                fn_args,
                                session_tool,
                                user.firma_id,
                                cliente.id,
                                auditoria.id
                            )

                        yield f"data: {json.dumps({'type': 'tool_result', 'name': fn_name, 'result': tool_result})}\n\n"

                        # Re-consultar al modelo con el resultado para obtener la conclusión final
                        follow_up_payload = {
                            "model": settings.ollama_model,
                            "messages": messages_payload + [
                                {"role": "assistant", "content": "".join(full_content), "tool_calls": [tc]},
                                {"role": "tool", "content": json.dumps(tool_result, ensure_ascii=False)}
                            ],
                            "stream": True,
                            "options": {"temperature": 0.1}
                        }
                        with requests.post(url, json=follow_up_payload, stream=True, timeout=120) as r2:
                            for l2 in r2.iter_lines():
                                if not l2:
                                    continue
                                c2 = json.loads(l2.decode("utf-8"))
                                d2 = c2.get("message", {}).get("content", "")
                                if d2:
                                    full_content.append(d2)
                                    yield f"data: {json.dumps({'type': 'content', 'delta': d2})}\n\n"
                                if c2.get("done", False):
                                    break

            # Persistir respuesta del asistente en BD
            async with AsyncSessionLocal() as session_save:
                msg_assistant = AgenteMensaje(
                    conversacion_id=conv_id,
                    rol="assistant",
                    contenido="".join(full_content),
                    herramientas_usadas=tools_executed
                )
                session_save.add(msg_assistant)
                await session_save.commit()

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Error en chat agente: {e}")
            yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )
