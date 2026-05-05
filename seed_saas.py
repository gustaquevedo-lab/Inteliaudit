import asyncio
import json
import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from db.base import AsyncSessionLocal, engine, Base, init_db
from db.models import Firma, Usuario, Cliente, Auditoria, Hallazgo, RG90, Tarea, DeclaracionJurada
import bcrypt

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

async def seed():
    await init_db()
    async with AsyncSessionLocal() as db:
        print("Iniciando Seed Real de Inteliaudit SaaS...")
        
        # 0. Limpiar datos previos (Opcional, pero recomendado para un seed limpio)
        # for table in reversed(Base.metadata.sorted_tables):
        #     await db.execute(table.delete())

        # 1. Crear Firmas (Tenants)
        firma1 = Firma(
            nombre="Soluciones Contables & Asociados",
            ruc="80012345-0",
            plan="professional",
            eslogan="Excelencia en Auditoría Impositiva"
        )
        firma2 = Firma(
            nombre="TaxForce Paraguay",
            ruc="80198765-4",
            plan="starter",
            eslogan="Tecnología al servicio del contribuyente"
        )
        db.add_all([firma1, firma2])
        await db.flush()

        # 2. Crear Usuarios
        usuarios = [
            Usuario(firma_id=firma1.id, email="juan.perez@soluciones.com.py", nombre="Juan Pérez", password_hash=hash_pw("admin123"), rol="admin"),
            Usuario(firma_id=firma1.id, email="maria.gomez@soluciones.com.py", nombre="María Gómez", password_hash=hash_pw("admin123"), rol="auditor"),
            Usuario(firma_id=firma2.id, email="admin@taxforce.com.py", nombre="Carlos Tax", password_hash=hash_pw("admin123"), rol="admin"),
            # Super Admin (Global)
            Usuario(firma_id=firma1.id, email="admin@inteliaudit.com", nombre="Super Admin Inteli", password_hash=hash_pw("admin123"), rol="super_admin")
        ]
        db.add_all(usuarios)
        await db.flush()

        # 3. Crear Clientes para Firma 1 (5 clientes)
        clientes_f1 = [
            Cliente(firma_id=firma1.id, ruc="80005544-1", razon_social="Frigorífico Guaraní S.A.", regimen="GENERAL", actividad_principal="Producción cárnica"),
            Cliente(firma_id=firma1.id, ruc="80011223-0", razon_social="Supermercados Stock S.A.", regimen="GENERAL", actividad_principal="Retail / Consumo"),
            Cliente(firma_id=firma1.id, ruc="4455667-2", razon_social="TechParaguay S.R.L.", regimen="GENERAL", actividad_principal="Servicios Tecnológicos"),
            Cliente(firma_id=firma1.id, ruc="80099887-5", razon_social="AgroExport S.A.", regimen="GENERAL", actividad_principal="Exportación de granos"),
            Cliente(firma_id=firma1.id, ruc="1122334-9", razon_social="Inmobiliaria del Este S.A.", regimen="GENERAL", actividad_principal="Bienes Raíces")
        ]
        db.add_all(clientes_f1)
        
        # Clientes para Firma 2 (5 clientes)
        clientes_f2 = [
            Cliente(firma_id=firma2.id, ruc="80033221-8", razon_social="Logística Express S.A.", regimen="GENERAL"),
            Cliente(firma_id=firma2.id, ruc="2233445-5", razon_social="Farmacia San Roque", regimen="RESIMPLE"),
            Cliente(firma_id=firma2.id, ruc="80077665-2", razon_social="Constructora Delta S.A.", regimen="GENERAL"),
            Cliente(firma_id=firma2.id, ruc="5566778-1", razon_social="Consultora ABC", regimen="SIMPLE"),
            Cliente(firma_id=firma2.id, ruc="80044556-3", razon_social="Textil Asunción S.A.", regimen="GENERAL")
        ]
        db.add_all(clientes_f2)
        await db.flush()

        # 4. Crear Proyectos (3 por cliente)
        for cli in clientes_f1 + clientes_f2:
            tipos = ["auditoria_anual", "devolucion_iva", "fiscalizacion"]
            for i, tipo in enumerate(tipos):
                auditoria = Auditoria(
                    firma_id=cli.firma_id,
                    cliente_id=cli.id,
                    periodo_desde="2023-01",
                    periodo_hasta="2023-12",
                    tipo_encargo=tipo,
                    impuestos=json.dumps(["IVA", "IRE"]),
                    materialidad=10000000 if i == 0 else 0,
                    estado="en_progreso" if i == 0 else "finalizada",
                    auditor="Auditor Asignado"
                )
                db.add(auditoria)
                await db.flush()

                # Añadir un par de hallazgos por auditoría
                h1 = Hallazgo(
                    firma_id=cli.firma_id,
                    auditoria_id=auditoria.id,
                    impuesto="IVA",
                    periodo="2023-06",
                    tipo_hallazgo="DIFERENCIA_DEBITO",
                    descripcion="Diferencia entre RG90 y Form 120 detectada por IA.",
                    articulo_legal="Art. 85 Ley 6380/19",
                    base_ajuste=5000000,
                    total_contingencia=500000,
                    nivel_riesgo="alto",
                    estado="pendiente",
                    sugerencia_ai=True
                )
                db.add(h1)

                # Datos RG90 (Simulados)
                for _ in range(5):
                    rg = RG90(
                        firma_id=cli.firma_id,
                        auditoria_id=auditoria.id,
                        cliente_id=cli.id,
                        periodo="2023-06",
                        tipo="venta" if _ % 2 == 0 else "compra",
                        ruc_contraparte="80000000-1",
                        nombre_contraparte="Contraparte de Prueba",
                        nro_comprobante=f"001-001-{100+_}",
                        fecha_emision="2023-06-15",
                        total_comprobante=1000000 * (_ + 1),
                        iva_10=100000 * (_ + 1),
                        cdc_valido=True
                    )
                    db.add(rg)

        await db.commit()
        print("Seed completado con éxito. 2 Firmas, 10 Clientes, 30 Auditorías generadas.")

if __name__ == "__main__":
    asyncio.run(seed())
