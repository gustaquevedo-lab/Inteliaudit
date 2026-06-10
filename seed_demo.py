"""
Seed de datos de demostración completos y realistas para Inteliaudit.
Genera una auditoría completa con datos paraguayos sintéticos.

Uso: python seed_demo.py
"""
import asyncio
import json
import uuid
import random
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import bcrypt

from db.base import AsyncSessionLocal, init_db
from db.models import (
    Firma, Usuario, Cliente, Auditoria, RG90, SifenComprobante,
    Hechauka, Hallazgo, Tarea, Declaracion,
)


def _uuid() -> str:
    return str(uuid.uuid4())


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _generar_cdc() -> str:
    """Genera un CDC válido de 44 dígitos."""
    return "".join([str(random.randint(0, 9)) for _ in range(44)])


def _generar_ruc() -> str:
    """Genera un RUC paraguayo válido (formato XXXXXXXX-D)."""
    base = random.randint(10000000, 99999999)
    digito = random.randint(0, 9)
    return f"{base}-{digito}"


def _generar_monto_iva(base: int, tasa: int = 10) -> int:
    """Calcula IVA sobre una base."""
    return int(base * tasa / 100)


# Datos de proveedores y clientes paraguayos sintéticos
PROVEEDORES = [
    ("80011111-1", "Distribuidora Asunción SA"),
    ("80022222-2", "Comercial Paraguaya SRL"),
    ("80033333-3", "Importadora del Este SA"),
    ("80044444-4", "Servicios Técnicos PY"),
    ("80055555-5", "Proveedor Activo SA"),
    ("80066666-6", "Proveedor Inactivo SA"),  # RUC inactivo para hallazgos
    ("80077777-7", "Suministros Generales SRL"),
    ("80088888-8", "Tecnología Paraguay SA"),
    ("80099999-9", "Logística Express SRL"),
    ("80100000-0", "Consultora Fiscal SA"),
]

CLIENTES_VENTAS = [
    ("80088888-4", "Cliente A SA"),
    ("80099999-5", "Cliente B SA"),
    ("80111111-6", "Cliente C SA"),
    ("80122222-7", "Cliente D SA"),
    ("80133333-8", "Cliente E SA"),
    ("80144444-9", "Cliente F SA"),
    ("80155555-0", "Cliente G SA"),
    ("80166666-1", "Cliente H SA"),
    ("80177777-2", "Cliente I SA"),
    ("80188888-3", "Cliente J SA"),
]


async def seed_demo():
    """Crea datos de demostración completos."""
    await init_db()

    async with AsyncSessionLocal() as db:
        print("Iniciando seed de demostracion...")

        # Verificar si ya existe la firma demo
        existing = await db.execute(
            select(Firma).where(Firma.nombre == "Auditores Asociados SRL")
        )
        if existing.scalar_one_or_none():
            print("⚠️  La firma demo ya existe. Abortando para evitar duplicados.")
            return

        # ============================================================
        # 1. FIRMA DEMO
        # ============================================================
        print("Creando firma demo...")
        firma = Firma(
            id=_uuid(),
            nombre="Auditores Asociados SRL",
            ruc="80099999-1",
            email="admin@auditores.com.py",
            plan="trial",
            activa=True,
            trial_hasta=datetime.now(timezone.utc) + timedelta(days=7),
        )
        db.add(firma)
        await db.flush()

        # ============================================================
        # 2. USUARIOS
        # ============================================================
        print("Creando usuarios...")
        usuarios = [
            Usuario(
                id=_uuid(),
                firma_id=firma.id,
                email="admin@demo.com",
                nombre="Admin Demo",
                password_hash=_hash("demo123"),
                rol="admin",
                activo=True,
            ),
            Usuario(
                id=_uuid(),
                firma_id=firma.id,
                email="senior@demo.com",
                nombre="Auditor Senior",
                password_hash=_hash("demo123"),
                rol="auditor_senior",
                activo=True,
            ),
            Usuario(
                id=_uuid(),
                firma_id=firma.id,
                email="auditor@demo.com",
                nombre="Auditor Junior",
                password_hash=_hash("demo123"),
                rol="auditor",
                activo=True,
            ),
        ]
        db.add_all(usuarios)
        await db.flush()

        # ============================================================
        # 3. CLIENTES
        # ============================================================
        print("Creando clientes...")
        clientes = [
            Cliente(
                id=_uuid(),
                firma_id=firma.id,
                ruc="80012345-6",
                razon_social="Comercial Guaraní SA",
                nombre_fantasia="Comercial Guaraní",
                actividad_principal="Comercio general",
                regimen="general",
                estado_dnit="activo",
            ),
            Cliente(
                id=_uuid(),
                firma_id=firma.id,
                ruc="80098765-4",
                razon_social="Servicios Delta SRL",
                nombre_fantasia="Servicios Delta",
                actividad_principal="Servicios profesionales",
                regimen="general",
                estado_dnit="activo",
            ),
            Cliente(
                id=_uuid(),
                firma_id=firma.id,
                ruc="80054321-0",
                razon_social="Importadora Sur SA",
                nombre_fantasia="Importadora Sur",
                actividad_principal="Importación de bienes",
                regimen="general",
                estado_dnit="activo",
            ),
        ]
        db.add_all(clientes)
        await db.flush()

        # ============================================================
        # 4. AUDITORÍA COMPLETA (primer cliente, período 2024-01 a 2024-12)
        # ============================================================
        print("Creando auditoria completa...")
        cliente_principal = clientes[0]
        auditoria = Auditoria(
            id=_uuid(),
            firma_id=firma.id,
            cliente_id=cliente_principal.id,
            periodo_desde="2024-01",
            periodo_hasta="2024-12",
            tipo_encargo="auditoria_anual",
            impuestos=json.dumps(["IVA", "IRE"]),
            materialidad=500000,
            estado="en_progreso",
            auditor="Auditor Senior",
        )
        db.add(auditoria)
        await db.flush()

        # ============================================================
        # 5. DATOS RG90 (12 meses × 30 compras + 20 ventas)
        # ============================================================
        print("Generando registros RG90 (compras y ventas)...")
        rg90_compras = []
        rg90_ventas = []
        sifen_comprobantes = []

        for mes in range(1, 13):
            periodo = f"2024-{mes:02d}"

            # 30 compras por mes
            for i in range(30):
                ruc_prov, nombre_prov = random.choice(PROVEEDORES)
                base_10 = random.randint(5000000, 50000000)
                iva_10 = _generar_monto_iva(base_10, 10)
                total = base_10 + iva_10

                # 80% con CDC válido, 20% sin CDC o con CDC cancelado
                tiene_cdc = random.random() < 0.8
                cdc = _generar_cdc() if tiene_cdc else None

                # RUC inactivo para algunos (generar hallazgos)
                ruc_activo = ruc_prov != "80066666-6"

                compra = RG90(
                    id=_uuid(),
                    firma_id=firma.id,
                    cliente_id=cliente_principal.id,
                    auditoria_id=auditoria.id,
                    periodo=periodo,
                    tipo="compra",
                    ruc_contraparte=ruc_prov,
                    nombre_contraparte=nombre_prov,
                    nro_comprobante=f"001-001-{mes:02d}{i:04d}",
                    cdc=cdc,
                    fecha_emision=f"2024-{mes:02d}-{random.randint(1, 28):02d}",
                    base_gravada_10=base_10,
                    base_gravada_5=0,
                    monto_exento=0,
                    iva_10=iva_10,
                    iva_5=0,
                    iva_total=iva_10,
                    total_comprobante=total,
                    cdc_valido=tiene_cdc,
                    ruc_activo=ruc_activo,
                    en_sifen=tiene_cdc,
                )
                rg90_compras.append(compra)

                # Si tiene CDC válido, crear comprobante SIFEN
                if tiene_cdc and ruc_activo:
                    sifen = SifenComprobante(
                        id=_uuid(),
                        firma_id=firma.id,
                        auditoria_id=auditoria.id,
                        cdc=cdc,
                        tipo_de="1",
                        ruc_emisor=ruc_prov,
                        nombre_emisor=nombre_prov,
                        ruc_receptor=cliente_principal.ruc,
                        nombre_receptor=cliente_principal.razon_social,
                        fecha_emision=f"2024-{mes:02d}-{random.randint(1, 28):02d}T{random.randint(8, 18):02d}:30:00",
                        base_gravada_10=base_10,
                        base_gravada_5=0,
                        monto_exento=0,
                        iva_total=iva_10,
                        total_comprobante=total,
                        estado_sifen="aprobado",
                    )
                    sifen_comprobantes.append(sifen)

            # 20 ventas por mes
            for i in range(20):
                ruc_cli, nombre_cli = random.choice(CLIENTES_VENTAS)
                base_10 = random.randint(10000000, 80000000)
                iva_10 = _generar_monto_iva(base_10, 10)
                total = base_10 + iva_10

                venta = RG90(
                    id=_uuid(),
                    firma_id=firma.id,
                    cliente_id=cliente_principal.id,
                    auditoria_id=auditoria.id,
                    periodo=periodo,
                    tipo="venta",
                    ruc_contraparte=ruc_cli,
                    nombre_contraparte=nombre_cli,
                    nro_comprobante=f"001-002-{mes:02d}{i:04d}",
                    cdc=_generar_cdc(),
                    fecha_emision=f"2024-{mes:02d}-{random.randint(1, 28):02d}",
                    base_gravada_10=base_10,
                    base_gravada_5=0,
                    monto_exento=0,
                    iva_10=iva_10,
                    iva_5=0,
                    iva_total=iva_10,
                    total_comprobante=total,
                )
                rg90_ventas.append(venta)

        db.add_all(rg90_compras)
        db.add_all(rg90_ventas)
        db.add_all(sifen_comprobantes)
        await db.flush()

        # ============================================================
        # 6. REGISTROS HECHAUKA
        # ============================================================
        print("Generando registros HECHAUKA...")
        hechauka_registros = []

        for mes in range(1, 13):
            periodo = f"2024-{mes:02d}"
            # Crear HECHAUKA para cada venta (compradores declaran)
            for venta in rg90_ventas:
                if venta.periodo == periodo:
                    hech = Hechauka(
                        id=_uuid(),
                        firma_id=firma.id,
                        cliente_id=cliente_principal.id,
                        auditoria_id=auditoria.id,
                        periodo=periodo,
                        ruc_informante=venta.ruc_contraparte,
                        nombre_informante=venta.nombre_contraparte,
                        tipo_operacion="compra",
                        nro_comprobante=venta.nro_comprobante,
                        fecha_comprobante=venta.fecha_emision,
                        monto_operacion=venta.total_comprobante,
                        iva_operacion=venta.iva_total,
                        retencion_iva=int(venta.iva_total * 0.3),  # 30% retención
                        retencion_ire=0,
                    )
                    hechauka_registros.append(hech)

        db.add_all(hechauka_registros)
        await db.flush()

        # ============================================================
        # 7. DECLARACIONES FORM. 120 (con diferencias para generar hallazgos)
        # ============================================================
        print("Generando declaraciones Form. 120...")

        for mes in range(1, 13):
            periodo = f"2024-{mes:02d}"

            # Calcular totales reales de RG90
            compras_mes = [c for c in rg90_compras if c.periodo == periodo]
            ventas_mes = [v for v in rg90_ventas if v.periodo == periodo]

            total_cf_rg90 = sum(c.iva_total for c in compras_mes)
            total_df_rg90 = sum(v.iva_total for v in ventas_mes)

            # Introducir diferencias en algunos meses (para generar hallazgos)
            if mes in [3, 6, 9]:
                # Diferencia del 10% en crédito fiscal
                cf_declarado = int(total_cf_rg90 * 0.9)
            else:
                cf_declarado = total_cf_rg90

            if mes in [4, 8]:
                # Diferencia del 5% en débito fiscal
                df_declarado = int(total_df_rg90 * 0.95)
            else:
                df_declarado = total_df_rg90

            decl = Declaracion(
                id=_uuid(),
                firma_id=firma.id,
                cliente_id=cliente_principal.id,
                auditoria_id=auditoria.id,
                formulario="120",
                periodo=periodo,
                fecha_presentacion=f"2024-{mes+1:02d}-20",
                estado_declaracion="original",
                nro_rectificativa=0,
                datos_json=json.dumps({
                    "credito_fiscal": cf_declarado,
                    "debito_fiscal": df_declarado,
                    "saldo_a_favor": 0,
                }),
            )
            db.add(decl)

        await db.flush()

        # ============================================================
        # 8. HALLAZGOS PRE-GENERADOS
        # ============================================================
        print("Generando hallazgos de auditoria...")

        hallazgos = [
            Hallazgo(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                impuesto="IVA",
                periodo="2024-03",
                tipo_hallazgo="IVA_CREDITO_RUC_INACTIVO",
                descripcion="Crédito fiscal de Gs. 15.000.000 de proveedor RUC 80066666-6 (Proveedor Inactivo SA) con estado inactivo/cancelado en SET.",
                articulo_legal="Art. 95 Ley 6380/2019 — Requisitos crédito fiscal",
                base_ajuste=150000000,
                impuesto_omitido=15000000,
                multa_estimada=7500000,
                intereses_estimados=1500000,
                total_contingencia=24000000,
                nivel_riesgo="alto",
                estado="pendiente",
                creado_por="sistema",
            ),
            Hallazgo(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                impuesto="IVA",
                periodo="2024-03",
                tipo_hallazgo="IVA_DIFERENCIA_RG90_DJ",
                descripcion="Diferencia entre crédito fiscal RG90 (Gs. 150.000.000) y Form.120 (Gs. 135.000.000). Diferencia: Gs. 15.000.000",
                articulo_legal="Art. 97 Ley 6380/2019 — Consistencia DJ",
                base_ajuste=15000000,
                impuesto_omitido=15000000,
                multa_estimada=7500000,
                intereses_estimados=1500000,
                total_contingencia=24000000,
                nivel_riesgo="alto",
                estado="pendiente",
                creado_por="sistema",
            ),
            Hallazgo(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                impuesto="IVA",
                periodo="2024-06",
                tipo_hallazgo="IVA_CREDITO_SIN_CDC",
                descripcion="Comprobante 001-001-060015 de Sin CDC SA (RUC 80077777-7) sin CDC siendo posterior a obligatoriedad e-Kuatia. Crédito fiscal en riesgo: Gs. 3.000.000",
                articulo_legal="Art. 95 Ley 6380/2019 + RG 80/2021 — CDC obligatorio",
                base_ajuste=30000000,
                impuesto_omitido=3000000,
                multa_estimada=1500000,
                intereses_estimados=300000,
                total_contingencia=4800000,
                nivel_riesgo="medio",
                estado="pendiente",
                creado_por="sistema",
            ),
            Hallazgo(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                impuesto="IVA",
                periodo="2024-04",
                tipo_hallazgo="IVA_DIFERENCIA_RG90_DJ",
                descripcion="Diferencia entre débito fiscal RG90 (Gs. 200.000.000) y Form.120 (Gs. 190.000.000). Diferencia: Gs. 10.000.000",
                articulo_legal="Art. 97 Ley 6380/2019 — Consistencia DJ",
                base_ajuste=10000000,
                impuesto_omitido=10000000,
                multa_estimada=5000000,
                intereses_estimados=1000000,
                total_contingencia=16000000,
                nivel_riesgo="medio",
                estado="pendiente",
                creado_por="sistema",
            ),
            Hallazgo(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                impuesto="IVA",
                periodo="2024-08",
                tipo_hallazgo="IVA_DEBITO_OMITIDO_HECHAUKA",
                descripcion="HECHAUKA reporta 5 comprobante(s) de venta no declarados en RG90. Débito fiscal omitido estimado: Gs. 8.000.000",
                articulo_legal="Art. 93 Ley 6380/2019 — Débito fiscal omitido",
                base_ajuste=80000000,
                impuesto_omitido=8000000,
                multa_estimada=4000000,
                intereses_estimados=800000,
                total_contingencia=12800000,
                nivel_riesgo="medio",
                estado="pendiente",
                creado_por="sistema",
            ),
            Hallazgo(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                impuesto="IRE",
                periodo="2024",
                tipo_hallazgo="IRE_GASTO_SIN_COMPROBANTE",
                descripcion="Gastos declarados en Form. 500 (Gs. 500.000.000) superan compras RG90 (Gs. 450.000.000). Diferencia sin respaldo documental: Gs. 50.000.000",
                articulo_legal="Art. 16 Ley 6380/2019 — Gastos deducibles",
                base_ajuste=50000000,
                impuesto_omitido=5000000,
                multa_estimada=2500000,
                intereses_estimados=500000,
                total_contingencia=8000000,
                nivel_riesgo="medio",
                estado="pendiente",
                creado_por="sistema",
            ),
            Hallazgo(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                impuesto="IVA",
                periodo="2024-09",
                tipo_hallazgo="IVA_CREDITO_SIN_CDC",
                descripcion="CDC 99999999999999999999999999999999999999999999 con estado cancelado en SIFEN. Crédito fiscal inválido: Gs. 5.000.000",
                articulo_legal="Art. 95 Ley 6380/2019 + RG 80/2021 — CDC obligatorio",
                base_ajuste=50000000,
                impuesto_omitido=5000000,
                multa_estimada=2500000,
                intereses_estimados=500000,
                total_contingencia=8000000,
                nivel_riesgo="alto",
                estado="pendiente",
                creado_por="sistema",
            ),
            Hallazgo(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                impuesto="RETENCIONES",
                periodo="2024-05",
                tipo_hallazgo="RET_NO_PRACTICADA",
                descripcion="Pago a proveedor de servicios personales (RUC 4455667-2) sin practicar retención IVA 30%. Retención omitida: Gs. 900.000",
                articulo_legal="Art. 93 Ley 6380/2019 — Agentes de retención",
                base_ajuste=3000000,
                impuesto_omitido=900000,
                multa_estimada=450000,
                intereses_estimados=90000,
                total_contingencia=1440000,
                nivel_riesgo="bajo",
                estado="pendiente",
                creado_por="sistema",
            ),
        ]
        db.add_all(hallazgos)
        await db.flush()

        # ============================================================
        # 9. TAREAS DE PLAN DE TRABAJO
        # ============================================================
        print("Creando tareas de plan de trabajo...")
        tareas = [
            Tarea(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                titulo="Carta de Compromiso",
                descripcion="Firma de la carta de compromiso según NIA 210.",
                categoria="legal",
                completada=True,
                orden=1,
            ),
            Tarea(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                titulo="Obtención de Balances",
                descripcion="Solicitar Balance General y Estado de Resultados del ejercicio 2024.",
                categoria="administrativo",
                completada=True,
                orden=2,
            ),
            Tarea(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                titulo="Cruce de Inventarios",
                descripcion="Validar existencias físicas contra registros contables.",
                categoria="impositivo",
                completada=False,
                orden=3,
            ),
            Tarea(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                titulo="Validación de CDCs",
                descripcion="Ejecutar validación masiva SIFEN sobre facturas de compra.",
                categoria="impositivo",
                completada=False,
                orden=4,
            ),
            Tarea(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                titulo="Revisión de Hallazgos",
                descripcion="Revisar y confirmar hallazgos generados automáticamente.",
                categoria="auditoria",
                completada=False,
                orden=5,
            ),
            Tarea(
                id=_uuid(),
                firma_id=firma.id,
                auditoria_id=auditoria.id,
                titulo="Informe Final",
                descripcion="Redactar informe final de auditoría con hallazgos confirmados.",
                categoria="legal",
                completada=False,
                orden=6,
            ),
        ]
        db.add_all(tareas)

        await db.commit()

        # ============================================================
        # RESUMEN
        # ============================================================
        print("\n" + "=" * 60)
        print("SEED COMPLETADO EXITOSAMENTE")
        print("=" * 60)
        print(f"\nResumen de datos creados:")
        print(f"   • 1 Firma: {firma.nombre} (plan {firma.plan})")
        print(f"   • 3 Usuarios: admin@demo.com, senior@demo.com, auditor@demo.com")
        print(f"   • 3 Clientes: {', '.join([c.razon_social for c in clientes])}")
        print(f"   • 1 Auditoría: {auditoria.periodo_desde} a {auditoria.periodo_hasta}")
        print(f"   • {len(rg90_compras)} registros RG90 compras")
        print(f"   • {len(rg90_ventas)} registros RG90 ventas")
        print(f"   • {len(sifen_comprobantes)} comprobantes SIFEN")
        print(f"   • {len(hechauka_registros)} registros HECHAUKA")
        print(f"   • 12 declaraciones Form. 120")
        print(f"   • {len(hallazgos)} hallazgos pre-generados")
        print(f"   • {len(tareas)} tareas de plan de trabajo")
        print(f"\nCredenciales de acceso:")
        print(f"   Email: admin@demo.com")
        print(f"   Password: demo123")
        print(f"\nURL de acceso:")
        print(f"   http://localhost:8000/app/login")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(seed_demo())
