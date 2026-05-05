"""
Endpoints de autenticación: login, token, perfil, usuarios.
Usa JWT (HS256) + bcrypt para passwords.
Credenciales Marangatú cifradas con Fernet (AES-128-CBC).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import bcrypt as _bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from db.base import get_db
from db.models import Firma, Usuario, CredencialMarangatu

router = APIRouter(prefix="/auth", tags=["auth"])

# ============================================================
#  Seguridad
# ============================================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def _hash(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def _verify(plain: str, hashed: str) -> bool:
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


def _crear_token(data: dict, expire_minutes: int | None = None) -> str:
    payload = data.copy()
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=expire_minutes or settings.jwt_access_token_expire_minutes
    )
    payload["exp"] = exp
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def _cifrar_credencial(texto: str) -> str:
    from cryptography.fernet import Fernet
    import base64, hashlib
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.encryption_key.encode() or b"dev-key-32bytes!").digest())
    return Fernet(key).encrypt(texto.encode()).decode()


def _descifrar_credencial(cifrado: str) -> str:
    from cryptography.fernet import Fernet
    import base64, hashlib
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.encryption_key.encode() or b"dev-key-32bytes!").digest())
    return Fernet(key).decrypt(cifrado.encode()).decode()


# ============================================================
#  Dependencia: usuario autenticado actual
# ============================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Usuario:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exc
    except JWTError:
        raise credentials_exc

    result = await db.execute(select(Usuario).where(Usuario.id == user_id, Usuario.activo == True))
    user = result.scalar_one_or_none()
    if not user:
        raise credentials_exc
    return user


async def get_current_admin(user: Usuario = Depends(get_current_user)) -> Usuario:
    if user.rol not in ("super_admin", "admin"):
        raise HTTPException(403, "Se requiere rol admin")
    return user


# ============================================================
#  Schemas
# ============================================================

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    nombre: str
    email: str
    rol: str
    firma_id: str
    firma_nombre: str


class UsuarioCreate(BaseModel):
    email: EmailStr
    nombre: str
    password: str
    rol: str = "auditor"


class UsuarioUpdate(BaseModel):
    nombre: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None
    password: Optional[str] = None


class CredencialCreate(BaseModel):
    cliente_ruc: str
    usuario_dnit: str
    clave_dnit: str
    alias: Optional[str] = None


# Alias para compatibilidad con el endpoint /marangatu
CredencialesMarangatuRequest = CredencialCreate


class FirmaCreate(BaseModel):
    nombre: str
    ruc: Optional[str] = None
    email: Optional[EmailStr] = None
    eslogan: Optional[str] = None
    plan: str = "trial"
    admin_email: EmailStr
    admin_nombre: str
    admin_password: str


# ============================================================
#  Endpoints públicos
# ============================================================

@router.post("/token", response_model=TokenResponse)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """Login con email + password. Devuelve JWT."""
    result = await db.execute(select(Usuario).where(Usuario.email == form.username, Usuario.activo == True))
    user = result.scalar_one_or_none()
    if not user or not _verify(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales incorrectas")

    # Actualizar último acceso
    await db.execute(update(Usuario).where(Usuario.id == user.id).values(ultimo_acceso=datetime.now(timezone.utc)))

    firma_result = await db.execute(select(Firma).where(Firma.id == user.firma_id))
    firma = firma_result.scalar_one_or_none()

    token = _crear_token({"sub": user.id, "firma_id": user.firma_id, "rol": user.rol})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        nombre=user.nombre,
        email=user.email,
        rol=user.rol,
        firma_id=user.firma_id,
        firma_nombre=firma.nombre if firma else "",
    )


# ============================================================
#  Endpoints autenticados
# ============================================================

@router.get("/me")
async def get_me(user: Usuario = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    firma_result = await db.execute(select(Firma).where(Firma.id == user.firma_id))
    firma = firma_result.scalar_one_or_none()
    return {
        "id": user.id,
        "email": user.email,
        "nombre": user.nombre,
        "rol": user.rol,
        "firma_id": user.firma_id,
        "firma_nombre": firma.nombre if firma else "",
        "firma_plan": firma.plan if firma else "",
        "avatar_path": user.avatar_path,
        "ultimo_acceso": user.ultimo_acceso.isoformat() if user.ultimo_acceso else None,
    }


@router.get("/usuarios")
async def listar_usuarios(
    user: Usuario = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Lista usuarios de la firma del admin."""
    result = await db.execute(select(Usuario).where(Usuario.firma_id == user.firma_id).order_by(Usuario.nombre))
    usuarios = result.scalars().all()
    return [_ser_usuario(u) for u in usuarios]


@router.post("/usuarios", status_code=201)
async def crear_usuario(
    body: UsuarioCreate,
    admin: Usuario = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Usuario).where(Usuario.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "El email ya está registrado")
    user = Usuario(
        firma_id=admin.firma_id,
        email=body.email,
        nombre=body.nombre,
        password_hash=_hash(body.password),
        rol=body.rol,
    )
    db.add(user)
    await db.flush()
    return _ser_usuario(user)


@router.patch("/usuarios/{usuario_id}")
async def actualizar_usuario(
    usuario_id: str,
    body: UsuarioUpdate,
    admin: Usuario = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Usuario).where(Usuario.id == usuario_id, Usuario.firma_id == admin.firma_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "Usuario no encontrado")

    vals = {}
    if body.nombre is not None:
        vals["nombre"] = body.nombre
    if body.rol is not None:
        vals["rol"] = body.rol
    if body.activo is not None:
        vals["activo"] = body.activo
    if body.password is not None:
        vals["password_hash"] = _hash(body.password)

    if vals:
        await db.execute(update(Usuario).where(Usuario.id == usuario_id).values(**vals))

    result2 = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    return _ser_usuario(result2.scalar_one())


# ============================================================
#  Credenciales Marangatú
# ============================================================

@router.post("/credenciales", status_code=201)
@router.post("/marangatu", status_code=201)
async def registrar_credenciales_marangatu(
    body: CredencialCreate,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Guarda o actualiza credenciales de Marangatú para un cliente (cifradas)."""
    enc_usuario = _cifrar_credencial(body.usuario_dnit)
    enc_clave = _cifrar_credencial(body.clave_dnit)

    existing = await db.execute(
        select(CredencialMarangatu).where(
            CredencialMarangatu.firma_id == user.firma_id,
            CredencialMarangatu.cliente_ruc == body.cliente_ruc,
        )
    )
    cred = existing.scalar_one_or_none()

    if cred:
        cred.usuario_dnit_enc = enc_usuario
        cred.clave_dnit_enc = enc_clave
        if body.alias:
            cred.alias = body.alias
        return {"ok": True, "action": "updated"}
    else:
        nueva = CredencialMarangatu(
            firma_id=user.firma_id,
            cliente_ruc=body.cliente_ruc,
            usuario_dnit_enc=enc_usuario,
            clave_dnit_enc=enc_clave,
            alias=body.alias,
        )
        db.add(nueva)
        return {"ok": True, "action": "created"}


@router.get("/credenciales/{cliente_ruc}")
async def get_credencial(
    cliente_ruc: str,
    user: Usuario = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(CredencialMarangatu).where(
            CredencialMarangatu.firma_id == user.firma_id,
            CredencialMarangatu.cliente_ruc == cliente_ruc,
            CredencialMarangatu.activa == True,
        )
    )
    cred = result.scalar_one_or_none()
    if not cred:
        return {"tiene_credencial": False}
    return {
        "tiene_credencial": True,
        "alias": cred.alias,
        "actualizado_en": cred.actualizado_en.isoformat() if cred.actualizado_en else None,
    }


# ============================================================
#  Super-admin: crear firmas
# ============================================================

@router.post("/firmas", status_code=201)
async def crear_firma(body: FirmaCreate, db: AsyncSession = Depends(get_db)):
    """
    Endpoint de onboarding: crea firma + primer usuario admin.
    En producción debe estar protegido con una API key de super-admin o solo accesible internamente.
    """
    from datetime import timedelta
    firma = Firma(
        nombre=body.nombre,
        ruc=body.ruc,
        email=body.email,
        eslogan=body.eslogan,
        plan=body.plan,
        trial_hasta=datetime.now(timezone.utc) + timedelta(days=30) if body.plan == "trial" else None,
    )
    db.add(firma)
    await db.flush()

    admin = Usuario(
        firma_id=firma.id,
        email=body.admin_email,
        nombre=body.admin_nombre,
        password_hash=_hash(body.admin_password),
        rol="admin",
    )
    db.add(admin)
    await db.flush()

    return {"firma_id": firma.id, "admin_id": admin.id}


# ============================================================
#  Helpers
# ============================================================

def _ser_usuario(u: Usuario) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "nombre": u.nombre,
        "rol": u.rol,
        "activo": u.activo,
        "creado_en": u.creado_en.isoformat() if u.creado_en else None,
        "ultimo_acceso": u.ultimo_acceso.isoformat() if u.ultimo_acceso else None,
    }
