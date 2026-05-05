"""
Script de inicialización: crea la firma auditora y el primer usuario admin.
Ejecutar una sola vez: python seed.py
"""
import asyncio, uuid, bcrypt
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from db.base import init_db
from db.models import Firma, Usuario

DATABASE_URL = "sqlite+aiosqlite:///./inteliaudit.db"

def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

FIRMA_NOMBRE  = "Mi Firma Auditora"
FIRMA_RUC     = "80000001-1"
ADMIN_EMAIL   = "admin@firma.com"
ADMIN_NOMBRE  = "Administrador"
ADMIN_PASS    = "Inteliaudit2025!"

async def seed():
    # Crear tablas
    await init_db()

    engine = create_async_engine(DATABASE_URL)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        from sqlalchemy import select

        # Verificar si ya existe
        existing = await db.execute(select(Usuario).where(Usuario.email == ADMIN_EMAIL))
        if existing.scalar_one_or_none():
            print("El usuario ya existe, nada que hacer.")
            return

        firma = Firma(
            id=str(uuid.uuid4()),
            nombre=FIRMA_NOMBRE,
            ruc=FIRMA_RUC,
            plan="professional",
            activa=True,
        )
        db.add(firma)
        await db.flush()

        usuario = Usuario(
            id=str(uuid.uuid4()),
            firma_id=firma.id,
            email=ADMIN_EMAIL,
            nombre=ADMIN_NOMBRE,
            password_hash=_hash(ADMIN_PASS),
            rol="admin",
            activo=True,
        )
        db.add(usuario)
        await db.commit()

    print("OK - Base de datos inicializada.")
    print(f"   Firma:    {FIRMA_NOMBRE} (RUC {FIRMA_RUC})")
    print(f"   Email:    {ADMIN_EMAIL}")
    print(f"   Password: {ADMIN_PASS}")
    print()
    print("   Abri http://localhost:5173 e inicia sesion con esas credenciales.")

asyncio.run(seed())
