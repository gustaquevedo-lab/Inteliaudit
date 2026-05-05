"""
Capa de acceso a datos — operaciones CRUD sobre los modelos principales.
Todas las funciones reciben una AsyncSession y un firma_id para aislamiento.
"""
import json
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    AuditTrail,
    Auditoria,
    Cedula,
    Cliente,
    Declaracion,
    DeclaracionJurada,
    Hallazgo,
    Hechauka,
    Informe,
    RG90,
    SifenComprobante,
    Tarea,
)


# ============================================================
#  CLIENTES
# ============================================================

async def get_cliente(db: AsyncSession, firma_id: str, ruc: Optional[str] = None, id: Optional[str] = None) -> Optional[Cliente]:
    q = select(Cliente).where(Cliente.firma_id == firma_id)
    if ruc:
        q = q.where(Cliente.ruc == ruc)
    if id:
        q = q.where(Cliente.id == id)
    result = await db.execute(q)
    return result.scalar_one_or_none()


async def crear_cliente(db: AsyncSession, firma_id: str, **datos) -> Cliente:
    cliente = Cliente(firma_id=firma_id, **datos)
    db.add(cliente)
    await db.flush()
    return cliente


async def listar_clientes(db: AsyncSession, firma_id: str) -> list[Cliente]:
    result = await db.execute(
        select(Cliente)
        .where(Cliente.firma_id == firma_id)
        .order_by(Cliente.razon_social)
    )
    return list(result.scalars().all())


# ============================================================
#  AUDITORÍAS
# ============================================================

PLANES_DE_TRABAJO = {
    "auditoria_anual": [
        {"titulo": "Carta de Compromiso", "descripcion": "Firma de la carta de compromiso según NIA 210.", "categoria": "legal", "orden": 1},
        {"titulo": "Obtención de Balances", "descripcion": "Solicitar Balance General y Estado de Resultados del ejercicio.", "categoria": "administrativo", "orden": 2},
        {"titulo": "Circularización de Bancos", "descripcion": "Enviar pedidos de confirmación a entidades financieras.", "categoria": "impositivo", "orden": 3},
        {"titulo": "Cruce de Inventarios", "descripcion": "Validar existencias físicas contra registros contables.", "categoria": "impositivo", "orden": 4},
    ],
    "devolucion_iva": [
        {"titulo": "Certificados de Exportación", "descripcion": "Compilar todos los certificados de exportación del periodo.", "categoria": "legal", "orden": 1},
        {"titulo": "Validación de CDCs", "descripcion": "Ejecutar validación masiva SIFEN sobre facturas de compra.", "categoria": "impositivo", "orden": 2},
        {"titulo": "Informe de Auditoría Especial", "descripcion": "Redactar borrador del informe especial para DNIT.", "categoria": "legal", "orden": 3},
    ],
    "fiscalizacion": [
        {"titulo": "Orden de Fiscalización", "descripcion": "Cargar copia digital de la orden de la DNIT.", "categoria": "legal", "orden": 1},
        {"titulo": "Requerimiento de Información", "descripcion": "Mapear cada punto del requerimiento con la evidencia.", "categoria": "administrativo", "orden": 2},
        {"titulo": "Contestación de Observaciones", "descripcion": "Preparar descargo técnico para la DNIT.", "categoria": "impositivo", "orden": 3},
    ],
}

async def crear_auditoria(
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    periodo_desde: str,
    periodo_hasta: str,
    impuestos: list[str],
    materialidad: int = 0,
    auditor: Optional[str] = None,
    tipo_encargo: str = "auditoria_anual"
) -> Auditoria:
    auditoria = Auditoria(
        firma_id=firma_id,
        cliente_id=cliente_id,
        periodo_desde=periodo_desde,
        periodo_hasta=periodo_hasta,
        tipo_encargo=tipo_encargo,
        impuestos=json.dumps(impuestos),
        materialidad=materialidad,
        auditor=auditor,
    )
    db.add(auditoria)
    await db.flush()

    # Generar Checklist automático
    plan = PLANES_DE_TRABAJO.get(tipo_encargo, PLANES_DE_TRABAJO["auditoria_anual"])
    for t in plan:
        tarea = Tarea(
            firma_id=firma_id,
            auditoria_id=auditoria.id,
            **t
        )
        db.add(tarea)
    
    await db.commit()
    return auditoria


async def get_auditoria(db: AsyncSession, firma_id: str, auditoria_id: str) -> Optional[Auditoria]:
    result = await db.execute(
        select(Auditoria).where(Auditoria.id == auditoria_id, Auditoria.firma_id == firma_id)
    )
    return result.scalar_one_or_none()


async def listar_auditorias(db: AsyncSession, firma_id: str, cliente_id: Optional[str] = None) -> list[Auditoria]:
    q = select(Auditoria).where(Auditoria.firma_id == firma_id).order_by(Auditoria.fecha_inicio.desc())
    if cliente_id:
        q = q.where(Auditoria.cliente_id == cliente_id)
    result = await db.execute(q)
    return list(result.scalars().all())


# ============================================================
#  DECLARACIONES
# ============================================================

async def guardar_declaracion(
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    formulario: str,
    periodo: str,
    fecha_presentacion: str,
    estado_declaracion: str,
    datos_json: dict,
    auditoria_id: Optional[str] = None,
    nro_rectificativa: int = 0,
    archivo_pdf: Optional[str] = None,
) -> Declaracion:
    decl = Declaracion(
        firma_id=firma_id,
        cliente_id=cliente_id,
        auditoria_id=auditoria_id,
        formulario=formulario,
        periodo=periodo,
        fecha_presentacion=fecha_presentacion,
        estado_declaracion=estado_declaracion,
        datos_json=json.dumps(datos_json, ensure_ascii=False),
        nro_rectificativa=nro_rectificativa,
        archivo_pdf=archivo_pdf,
    )
    db.add(decl)
    await db.flush()
    return decl


# ============================================================
#  RG 90
# ============================================================

async def guardar_rg90_batch(db: AsyncSession, firma_id: str, registros: list[dict]) -> int:
    objetos = [RG90(firma_id=firma_id, **r) for r in registros]
    db.add_all(objetos)
    await db.flush()
    return len(objetos)


async def get_rg90(
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    periodo: str,
    tipo: Optional[str] = None,
) -> list[RG90]:
    q = select(RG90).where(
        RG90.firma_id == firma_id, 
        RG90.cliente_id == cliente_id, 
        RG90.periodo == periodo
    )
    if tipo:
        q = q.where(RG90.tipo == tipo)
    result = await db.execute(q)
    return list(result.scalars().all())


# ============================================================
#  HALLAZGOS
# ============================================================

async def crear_hallazgo(
    db: AsyncSession,
    firma_id: str,
    auditoria_id: str,
    impuesto: str,
    periodo: str,
    tipo_hallazgo: str,
    descripcion: str,
    articulo_legal: str,
    impuesto_omitido: int = 0,
    base_ajuste: int = 0,
    multa_estimada: int = 0,
    intereses_estimados: int = 0,
    nivel_riesgo: str = "medio",
    descripcion_tecnica: Optional[str] = None,
    evidencias: Optional[list] = None,
    creado_por: str = "sistema",
) -> Hallazgo:
    hallazgo = Hallazgo(
        firma_id=firma_id,
        auditoria_id=auditoria_id,
        impuesto=impuesto,
        periodo=periodo,
        tipo_hallazgo=tipo_hallazgo,
        descripcion=descripcion,
        articulo_legal=articulo_legal,
        impuesto_omitido=impuesto_omitido,
        base_ajuste=base_ajuste,
        multa_estimada=multa_estimada,
        intereses_estimados=intereses_estimados,
        nivel_riesgo=nivel_riesgo,
        descripcion_tecnica=descripcion_tecnica,
        evidencias=json.dumps(evidencias or [], ensure_ascii=False),
        creado_por=creado_por,
    )
    db.add(hallazgo)
    await db.flush()
    return hallazgo


async def get_declaraciones(
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    formulario: str,
    periodo: str,
) -> list[Declaracion]:
    result = await db.execute(
        select(Declaracion).where(
            Declaracion.firma_id == firma_id,
            Declaracion.cliente_id == cliente_id,
            Declaracion.formulario == formulario,
            Declaracion.periodo == periodo,
        )
    )
    return list(result.scalars().all())


async def get_sifen_por_cdc(
    db: AsyncSession,
    firma_id: str,
    cdc: str,
) -> Optional[SifenComprobante]:
    result = await db.execute(
        select(SifenComprobante).where(
            SifenComprobante.firma_id == firma_id,
            SifenComprobante.cdc == cdc,
        )
    )
    return result.scalar_one_or_none()


async def marcar_validacion_rg90(
    db: AsyncSession,
    rg90_id: str,
    en_sifen: Optional[bool],
) -> None:
    from sqlalchemy import update as sa_update
    await db.execute(
        sa_update(RG90).where(RG90.id == rg90_id).values(en_sifen=en_sifen)
    )


async def get_hechauka(
    db: AsyncSession,
    firma_id: str,
    cliente_id: str,
    periodo: str,
) -> list[Hechauka]:
    result = await db.execute(
        select(Hechauka).where(
            Hechauka.firma_id == firma_id,
            Hechauka.cliente_id == cliente_id,
            Hechauka.periodo == periodo,
        )
    )
    return list(result.scalars().all())


async def guardar_hechauka_batch(db: AsyncSession, firma_id: str, registros: list[dict]) -> int:
    objetos = [Hechauka(firma_id=firma_id, **r) for r in registros]
    db.add_all(objetos)
    await db.flush()
    return len(objetos)


async def listar_trail(
    db: AsyncSession,
    firma_id: str,
    auditoria_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditTrail]:
    q = select(AuditTrail).where(AuditTrail.firma_id == firma_id)
    if auditoria_id:
        q = q.where(AuditTrail.auditoria_id == auditoria_id)
    q = q.order_by(AuditTrail.timestamp.desc()).limit(limit).offset(offset)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_hallazgos(
    db: AsyncSession,
    firma_id: str,
    auditoria_id: str,
    impuesto: Optional[str] = None,
    estado: Optional[str] = None,
) -> list[Hallazgo]:
    q = select(Hallazgo).where(Hallazgo.auditoria_id == auditoria_id, Hallazgo.firma_id == firma_id)
    if impuesto:
        q = q.where(Hallazgo.impuesto == impuesto)
    if estado:
        q = q.where(Hallazgo.estado == estado)
    q = q.order_by(Hallazgo.nivel_riesgo, Hallazgo.impuesto_omitido.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


# ============================================================
#  AUDIT TRAIL
# ============================================================

async def log_trail(
    db: AsyncSession,
    firma_id: str,
    accion: str,
    modulo: str,
    usuario_id: Optional[str] = None,
    auditoria_id: Optional[str] = None,
    detalle: Optional[str] = None,
    datos: Optional[dict] = None,
    resultado: str = "ok",
) -> None:
    trail = AuditTrail(
        firma_id=firma_id,
        usuario_id=usuario_id,
        auditoria_id=auditoria_id,
        accion=accion,
        modulo=modulo,
        detalle=detalle,
        datos_json=json.dumps(datos, ensure_ascii=False) if datos else None,
        resultado=resultado,
    )
    db.add(trail)
    await db.flush()
