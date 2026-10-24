"""
Herramientas operativas (Tool Calling) para el Agente Auditor Forense.
Cada herramienta aplica forzosamente el aislamiento por (firma_id, cliente_id, auditoria_id).
"""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import RG90, SifenComprobante, Hallazgo, Cedula
from analisis.rag_service import buscar_normativas
from analisis.grafo_service import consultar_entidad_grafo
from analisis.riesgo import calcular_contingencia

ESQUEMA_HERRAMIENTAS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_normativa_legal",
            "description": "Busca artículos y disposiciones de leyes (Ley 6380), decretos y resoluciones de Paraguay (DNIT).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Concepto o término a buscar (ej: 'gastos no deducibles Art. 16', 'crédito fiscal IVA comprobante anulado')"
                    },
                    "impuesto": {
                        "type": "string",
                        "description": "Opcional: 'IVA', 'IRE', 'IDU', 'IRP', 'RETENCIONES'"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_comprobantes_cliente",
            "description": "Consulta facturas y comprobantes declarados en RG90 del cliente en auditoría.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "enum": ["compra", "venta"],
                        "description": "Tipo de operación"
                    },
                    "ruc_contraparte": {
                        "type": "string",
                        "description": "Opcional: RUC del proveedor o cliente a filtrar"
                    },
                    "min_monto": {
                        "type": "integer",
                        "description": "Opcional: Filtrar comprobantes con monto mayor o igual a este valor en Guaraníes"
                    }
                },
                "required": ["tipo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_relaciones_proveedor",
            "description": "Consulta el grafo de relaciones, volumen histórico y alertas asociadas a un proveedor del cliente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ruc": {
                        "type": "string",
                        "description": "RUC del proveedor con o sin dígito verificador"
                    }
                },
                "required": ["ruc"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "recalcular_contingencia_fiscal",
            "description": "Calcula el impuesto omitido, multas (50% omisión, 100% contumacia) e intereses moratorios según Art. 175 Ley 125/91.",
            "parameters": {
                "type": "object",
                "properties": {
                    "monto": {
                        "type": "integer",
                        "description": "Monto de impuesto omitido en Guaraníes"
                    },
                    "periodo": {
                        "type": "string",
                        "description": "Período fiscal omitido en formato YYYY-MM (ej: '2024-03')"
                    },
                    "reincidente": {
                        "type": "boolean",
                        "description": "True si aplica multa del 100% por contumacia/reincidencia"
                    }
                },
                "required": ["monto", "periodo"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "crear_borrador_cedula_trabajo",
            "description": "Registra una Cédula de Auditoría preliminar (NIA 230) con los hallazgos y conclusiones generadas.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tipo": {
                        "type": "string",
                        "description": "Tipo de cédula (ej: 'analitica', 'sumaria', 'control_interno')"
                    },
                    "titulo": {
                        "type": "string",
                        "description": "Título formal de la cédula"
                    },
                    "conclusiones": {
                        "type": "string",
                        "description": "Texto del dictamen o conclusión técnica alcanzada"
                    }
                },
                "required": ["tipo", "titulo", "conclusiones"]
            }
        }
    }
]


async def ejecutar_herramienta(
    nombre: str,
    args: Dict[str, Any],
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    auditoria_id: str
) -> Any:
    """
    Ejecuta de forma segura una herramienta validando el perímetro de firma y cliente.
    """
    if nombre == "consultar_normativa_legal":
        query = args.get("query", "")
        impuesto = args.get("impuesto")
        if impuesto:
            query = f"{impuesto} {query}"
        resultados = await buscar_normativas(db, query=query, limit=3, firma_id=firma_id)
        return [
            {
                "normativa": r.normativa_numero,
                "titulo": r.normativa_titulo,
                "jerarquia": r.jerarquia,
                "articulo": r.articulo,
                "texto": r.texto,
                "coincidencia": round(r.score, 3)
            }
            for r in resultados
        ]

    elif nombre == "buscar_comprobantes_cliente":
        tipo = args.get("tipo", "compra")
        ruc_contra = args.get("ruc_contraparte")
        min_monto = args.get("min_monto", 0)

        stmt = select(RG90).where(
            RG90.firma_id == firma_id,
            RG90.cliente_id == cliente_id,
            RG90.tipo == tipo
        )
        if ruc_contra:
            stmt = stmt.where(RG90.ruc_contraparte.like(f"%{ruc_contra.strip()}%"))
        if min_monto and min_monto > 0:
            stmt = stmt.where(RG90.total_comprobante >= min_monto)

        stmt = stmt.limit(20)
        res = await db.execute(stmt)
        comprobantes = res.scalars().all()
        return [
            {
                "nro_comprobante": c.nro_comprobante,
                "ruc_contraparte": c.ruc_contraparte,
                "nombre_contraparte": c.nombre_contraparte or "",
                "periodo": c.periodo,
                "fecha": c.fecha_emision,
                "total": c.total_comprobante,
                "iva": c.iva_total,
                "cdc": c.cdc or "SIN_CDC"
            }
            for c in comprobantes
        ]

    elif nombre == "consultar_relaciones_proveedor":
        ruc = args.get("ruc", "").strip()
        info = await consultar_entidad_grafo(db, firma_id, cliente_id, auditoria_id, ruc)
        if not info:
            return {"resultado": f"No se encontró el RUC {ruc} registrado en el grafo de operaciones del cliente."}
        return info

    elif nombre == "recalcular_contingencia_fiscal":
        monto = int(args.get("monto", 0))
        periodo = args.get("periodo", "2024-01")
        reincidente = bool(args.get("reincidente", False))
        calc = calcular_contingencia(
            impuesto_omitido=monto,
            fecha_omision=periodo,
            reincidente=reincidente
        )
        return calc

    elif nombre == "crear_borrador_cedula_trabajo":
        tipo = args.get("tipo", "analitica")
        titulo = args.get("titulo", "Cédula Forense")
        conclusiones = args.get("conclusiones", "")

        from db.db import crear_cedula
        ced = await crear_cedula(
            db,
            firma_id=firma_id,
            auditoria_id=auditoria_id,
            tipo=tipo,
            codigo=f"CED-AI-{datetime.now(timezone.utc).strftime('%H%M%S')}",
            titulo=titulo,
            datos={
                "origen": "Agente Forense IA",
                "procedimientos": ["Generado interactivamente por Copilot Forense"],
                "conclusiones": conclusiones,
                "fecha": datetime.now(timezone.utc).isoformat()
            }
        )
        return {"status": "ok", "cedula_id": ced.id, "codigo": ced.codigo, "titulo": ced.titulo}

    else:
        return {"error": f"Herramienta desconocida: {nombre}"}
