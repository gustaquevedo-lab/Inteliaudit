"""
WebSocket manager para progreso de scraping en tiempo real.
Permite al frontend recibir updates de jobs sin polling.
"""
import asyncio
import json
from datetime import datetime
from typing import Optional

from fastapi import WebSocket


class ConnectionManager:
    """Maneja conexiones WebSocket activas por firma_id."""

    def __init__(self):
        self._connections: dict[str, list[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, firma_id: str):
        await websocket.accept()
        async with self._lock:
            if firma_id not in self._connections:
                self._connections[firma_id] = []
            self._connections[firma_id].append(websocket)

    async def disconnect(self, websocket: WebSocket, firma_id: str):
        async with self._lock:
            if firma_id in self._connections:
                self._connections[firma_id] = [
                    ws for ws in self._connections[firma_id] if ws != websocket
                ]
                if not self._connections[firma_id]:
                    del self._connections[firma_id]

    async def broadcast(self, firma_id: str, event: dict):
        """Envía un evento a todas las conexiones de una firma."""
        message = json.dumps(event, default=str)
        async with self._lock:
            conns = list(self._connections.get(firma_id, []))
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                await self.disconnect(ws, firma_id)

    async def send_job_progress(
        self,
        firma_id: str,
        job_id: str,
        estado: str,
        progreso: int,
        mensaje: Optional[str] = None,
    ):
        """Envía update de progreso de un job."""
        await self.broadcast(firma_id, {
            "type": "job_progress",
            "job_id": job_id,
            "estado": estado,
            "progreso": progreso,
            "mensaje": mensaje,
            "timestamp": datetime.now().isoformat(),
        })

    async def send_job_completed(self, firma_id: str, job_id: str, resultado: dict):
        """Notifica completación de un job."""
        await self.broadcast(firma_id, {
            "type": "job_completed",
            "job_id": job_id,
            "resultado": resultado,
            "timestamp": datetime.now().isoformat(),
        })

    async def send_job_error(self, firma_id: str, job_id: str, error: str):
        """Notifica error en un job."""
        await self.broadcast(firma_id, {
            "type": "job_error",
            "job_id": job_id,
            "error": error,
            "timestamp": datetime.now().isoformat(),
        })

    async def send_hallazgo_nuevo(self, firma_id: str, auditoria_id: str, hallazgo: dict):
        """Notifica un nuevo hallazgo generado durante análisis."""
        await self.broadcast(firma_id, {
            "type": "hallazgo_nuevo",
            "auditoria_id": auditoria_id,
            "hallazgo": hallazgo,
            "timestamp": datetime.now().isoformat(),
        })


# Singleton
ws_manager = ConnectionManager()
