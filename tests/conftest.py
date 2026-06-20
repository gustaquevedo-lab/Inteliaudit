"""
Fixtures para la suite de tests de Inteliaudit.
DB SQLite in-memory async con datos sinteticos paraguayos.
"""
import json
import uuid
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from db.base import Base
from db.models import (
    Auditoria, Cliente, Declaracion, Firma, Hallazgo,
    Hechauka, RG90, SifenComprobante, Usuario,
)


def _uuid() -> str:
    return str(uuid.uuid4())


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def firma(db_session: AsyncSession) -> Firma:
    f = Firma(
        id=_uuid(),
        nombre="Auditores Asociados SRL",
        ruc="80099999-1",
        email="admin@auditores.com.py",
        plan="trial",
        activa=True,
        trial_hasta=datetime(2027, 12, 31, tzinfo=timezone.utc),
    )
    db_session.add(f)
    await db_session.flush()
    return f


@pytest_asyncio.fixture
async def usuario_admin(db_session: AsyncSession, firma: Firma) -> Usuario:
    import bcrypt
    pw = bcrypt.hashpw("demo123".encode(), bcrypt.gensalt()).decode()
    u = Usuario(
        id=_uuid(),
        firma_id=firma.id,
        email="admin@demo.com",
        nombre="Admin Demo",
        password_hash=pw,
        rol="admin",
        activo=True,
    )
    db_session.add(u)
    await db_session.flush()
    return u


@pytest_asyncio.fixture
async def usuario_auditor(db_session: AsyncSession, firma: Firma) -> Usuario:
    import bcrypt
    pw = bcrypt.hashpw("demo123".encode(), bcrypt.gensalt()).decode()
    u = Usuario(
        id=_uuid(),
        firma_id=firma.id,
        email="auditor@demo.com",
        nombre="Auditor Demo",
        password_hash=pw,
        rol="auditor",
        activo=True,
    )
    db_session.add(u)
    await db_session.flush()
    return u


@pytest_asyncio.fixture
async def cliente(db_session: AsyncSession, firma: Firma) -> Cliente:
    c = Cliente(
        id=_uuid(),
        firma_id=firma.id,
        ruc="80012345-6",
        razon_social="Comercial Guarani SA",
        nombre_fantasia="Comercial Guarani",
        actividad_principal="Comercio general",
        regimen="general",
        estado_dnit="activo",
    )
    db_session.add(c)
    await db_session.flush()
    return c


@pytest_asyncio.fixture
async def auditoria(db_session: AsyncSession, firma: Firma, cliente: Cliente) -> Auditoria:
    a = Auditoria(
        id=_uuid(),
        firma_id=firma.id,
        cliente_id=cliente.id,
        periodo_desde="2024-01",
        periodo_hasta="2024-12",
        tipo_encargo="auditoria_anual",
        impuestos=json.dumps(["IVA", "IRE"]),
        materialidad=500000,
        estado="en_progreso",
        auditor="Auditor Demo",
    )
    db_session.add(a)
    await db_session.flush()
    return a


@pytest_asyncio.fixture
async def rg90_compras(db_session: AsyncSession, firma: Firma, cliente: Cliente, auditoria: Auditoria):
    registros = []
    cdc_valido = "12345678901234567890123456789012345678901234"
    cdc_cancelado = "99999999999999999999999999999999999999999999"

    registros.append(RG90(
        id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
        auditoria_id=auditoria.id, periodo="2024-03", tipo="compra",
        ruc_contraparte="80055555-1", nombre_contraparte="Proveedor Activo SA",
        nro_comprobante="001-001-0000001", cdc=cdc_valido,
        fecha_emision="2024-03-15",
        base_gravada_10=10000000, base_gravada_5=0, monto_exento=0,
        iva_10=1000000, iva_5=0, iva_total=1000000,
        total_comprobante=11000000, ruc_activo=True,
    ))
    registros.append(RG90(
        id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
        auditoria_id=auditoria.id, periodo="2024-03", tipo="compra",
        ruc_contraparte="80066666-2", nombre_contraparte="Proveedor Inactivo SA",
        nro_comprobante="001-001-0000002", cdc=cdc_cancelado,
        fecha_emision="2024-03-20",
        base_gravada_10=5000000, base_gravada_5=0, monto_exento=0,
        iva_10=500000, iva_5=0, iva_total=500000,
        total_comprobante=5500000, ruc_activo=False,
    ))
    registros.append(RG90(
        id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
        auditoria_id=auditoria.id, periodo="2024-03", tipo="compra",
        ruc_contraparte="80077777-3", nombre_contraparte="Sin CDC SA",
        nro_comprobante="001-001-0000003", cdc=None,
        fecha_emision="2024-03-25",
        base_gravada_10=3000000, base_gravada_5=0, monto_exento=0,
        iva_10=300000, iva_5=0, iva_total=300000,
        total_comprobante=3300000, ruc_activo=True,
    ))

    for r in registros:
        db_session.add(r)
    await db_session.flush()
    return registros


@pytest_asyncio.fixture
async def rg90_ventas(db_session: AsyncSession, firma: Firma, cliente: Cliente, auditoria: Auditoria):
    registros = []
    registros.append(RG90(
        id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
        auditoria_id=auditoria.id, periodo="2024-03", tipo="venta",
        ruc_contraparte="80088888-4", nombre_contraparte="Cliente A SA",
        nro_comprobante="001-001-0000100", cdc="44444444444444444444444444444444444444444444",
        fecha_emision="2024-03-10",
        base_gravada_10=20000000, base_gravada_5=0, monto_exento=0,
        iva_10=2000000, iva_5=0, iva_total=2000000,
        total_comprobante=22000000,
    ))
    registros.append(RG90(
        id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
        auditoria_id=auditoria.id, periodo="2024-03", tipo="venta",
        ruc_contraparte="80099999-5", nombre_contraparte="Cliente B SA",
        nro_comprobante="001-001-0000101", cdc="55555555555555555555555555555555555555555555",
        fecha_emision="2024-03-18",
        base_gravada_10=15000000, base_gravada_5=0, monto_exento=0,
        iva_10=1500000, iva_5=0, iva_total=1500000,
        total_comprobante=16500000,
    ))

    for r in registros:
        db_session.add(r)
    await db_session.flush()
    return registros


@pytest_asyncio.fixture
async def sifen_comprobantes(db_session: AsyncSession, firma: Firma, auditoria: Auditoria):
    cdc_valido = "12345678901234567890123456789012345678901234"
    cdc_cancelado = "99999999999999999999999999999999999999999999"

    s1 = SifenComprobante(
        id=_uuid(), firma_id=firma.id, auditoria_id=auditoria.id,
        cdc=cdc_valido, tipo_de="1",
        ruc_emisor="80055555-1", nombre_emisor="Proveedor Activo SA",
        ruc_receptor="80012345-6", nombre_receptor="Comercial Guarani SA",
        fecha_emision="2024-03-15T10:30:00",
        base_gravada_10=10000000, base_gravada_5=0, monto_exento=0,
        iva_total=1000000, total_comprobante=11000000,
        estado_sifen="aprobado",
    )
    s2 = SifenComprobante(
        id=_uuid(), firma_id=firma.id, auditoria_id=auditoria.id,
        cdc=cdc_cancelado, tipo_de="1",
        ruc_emisor="80066666-2", nombre_emisor="Proveedor Inactivo SA",
        ruc_receptor="80012345-6", nombre_receptor="Comercial Guarani SA",
        fecha_emision="2024-03-20T14:00:00",
        base_gravada_10=5000000, base_gravada_5=0, monto_exento=0,
        iva_total=500000, total_comprobante=5500000,
        estado_sifen="cancelado",
    )
    db_session.add_all([s1, s2])
    await db_session.flush()
    return [s1, s2]


@pytest_asyncio.fixture
async def sifen_recibida_omitida(db_session: AsyncSession, firma: Firma, auditoria: Auditoria, cliente: Cliente):
    """SIFEN recibida que NO tiene correspondiente en RG90 compras — crédito omitido."""
    s3 = SifenComprobante(
        id=_uuid(), firma_id=firma.id, auditoria_id=auditoria.id,
        cdc="77777777777777777777777777777777777777777777", tipo_de="1",
        ruc_emisor="80022222-8", nombre_emisor="Proveedor No Declarado SA",
        ruc_receptor=cliente.ruc, nombre_receptor=cliente.razon_social,
        fecha_emision="2024-03-22T09:00:00",
        base_gravada_10=8000000, base_gravada_5=0, monto_exento=0,
        iva_total=800000, total_comprobante=8800000,
        estado_sifen="aprobado",
    )
    db_session.add(s3)
    await db_session.flush()
    return s3


@pytest_asyncio.fixture
async def hechauka_registros(db_session: AsyncSession, firma: Firma, cliente: Cliente, auditoria: Auditoria):
    registros = []
    registros.append(Hechauka(
        id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
        auditoria_id=auditoria.id, periodo="2024-03",
        ruc_informante="80088888-4", nombre_informante="Cliente A SA",
        tipo_operacion="compra", nro_comprobante="001-001-0000100",
        fecha_comprobante="2024-03-10",
        monto_operacion=22000000, iva_operacion=2000000,
        retencion_iva=600000, retencion_ire=0,
    ))
    registros.append(Hechauka(
        id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
        auditoria_id=auditoria.id, periodo="2024-03",
        ruc_informante="80099999-5", nombre_informante="Cliente B SA",
        tipo_operacion="compra", nro_comprobante="001-001-0000101",
        fecha_comprobante="2024-03-18",
        monto_operacion=16500000, iva_operacion=1500000,
        retencion_iva=450000, retencion_ire=0,
    ))
    registros.append(Hechauka(
        id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
        auditoria_id=auditoria.id, periodo="2024-03",
        ruc_informante="80011111-7", nombre_informante="Cliente Omitido SA",
        tipo_operacion="compra", nro_comprobante="001-001-0000999",
        fecha_comprobante="2024-03-28",
        monto_operacion=8000000, iva_operacion=800000,
        retencion_iva=240000, retencion_ire=0,
    ))

    for r in registros:
        db_session.add(r)
    await db_session.flush()
    return registros


@pytest_asyncio.fixture
async def declaracion_form120(db_session: AsyncSession, firma: Firma, cliente: Cliente, auditoria: Auditoria):
    decl = Declaracion(
        id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
        auditoria_id=auditoria.id, formulario="120", periodo="2024-03",
        fecha_presentacion="2024-04-20", estado_declaracion="original",
        nro_rectificativa=0,
        datos_json=json.dumps({
            "credito_fiscal": 1500000,
            "debito_fiscal": 3500000,
            "saldo_a_favor": 0,
        }),
    )
    db_session.add(decl)
    await db_session.flush()
    return decl
