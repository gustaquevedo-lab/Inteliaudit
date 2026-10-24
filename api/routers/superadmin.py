import json
import secrets
import string
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from db.models import Firma, Usuario, Cliente
from api.routers.auth import get_current_user, _hash

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


def generar_password_temporal(longitud: int = 12) -> str:
    """Genera una contraseña temporal segura y legible."""
    alfabeto = string.ascii_letters + string.digits + "!@#$%"
    return "".join(secrets.choice(alfabeto) for _ in range(longitud))

# ============================================================
#  Dependencia: verificar super_admin
# ============================================================

async def get_current_super_admin(user: Usuario = Depends(get_current_user)) -> Usuario:
    if user.rol != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren privilegios de Super Administrador"
        )
    return user

# ============================================================
#  Schemas
# ============================================================

class FirmaResponse(BaseModel):
    id: str
    nombre: str
    ruc: Optional[str]
    email: Optional[str]
    plan: str
    features_override_json: Optional[str] = None
    activa: bool
    trial_hasta: Optional[datetime]
    creado_en: datetime
    num_clientes: int

class FirmaUpdateBody(BaseModel):
    plan: Optional[str] = None
    features_override_json: Optional[str] = None
    activa: Optional[bool] = None
    trial_hasta: Optional[datetime] = None

class FirmaCreateBody(BaseModel):
    nombre: str
    ruc: Optional[str] = None
    email: Optional[str] = None
    plan: str = "starter"
    admin_email: EmailStr
    admin_nombre: str
    admin_password: Optional[str] = None
    features_override_json: Optional[str] = None
    trial_hasta: Optional[datetime] = None

class UsuarioResponse(BaseModel):
    id: str
    firma_id: str
    firma_nombre: Optional[str]
    email: str
    nombre: str
    rol: str
    activo: bool
    debe_cambiar_password: bool = False
    creado_en: datetime
    ultimo_acceso: Optional[datetime]

class FirmaCreateResponse(BaseModel):
    firma: FirmaResponse
    admin_usuario: UsuarioResponse
    password_temporal: str

class UsuarioCreateBody(BaseModel):
    firma_id: str
    email: EmailStr
    nombre: str
    rol: str = "auditor"
    password: Optional[str] = None

class UsuarioCreateResponse(BaseModel):
    usuario: UsuarioResponse
    password_temporal: str

class UsuarioUpdateBody(BaseModel):
    nombre: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None

class PasswordResetBody(BaseModel):
    password: str
    debe_cambiar_password: bool = True

# ============================================================
#  Endpoints de Firmas (Tenants)
# ============================================================

@router.get("/firmas", response_model=List[FirmaResponse])
async def list_firmas(
    super_admin: Usuario = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Retorna todas las firmas registradas con su conteo de clientes."""
    query = (
        select(Firma, func.count(Cliente.id).label("num_clientes"))
        .outerjoin(Cliente, Cliente.firma_id == Firma.id)
        .group_by(Firma.id)
        .order_by(Firma.creado_en.desc())
    )
    result = await db.execute(query)
    rows = result.all()
    
    response = []
    for firma, num_clientes in rows:
        response.append(FirmaResponse(
            id=firma.id,
            nombre=firma.nombre,
            ruc=firma.ruc,
            email=firma.email,
            plan=firma.plan,
            features_override_json=firma.features_override_json,
            activa=firma.activa,
            trial_hasta=firma.trial_hasta,
            creado_en=firma.creado_en,
            num_clientes=num_clientes
        ))
    return response

@router.post("/firmas", response_model=FirmaCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_firma(
    body: FirmaCreateBody,
    super_admin: Usuario = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Crea atómicamente una nueva Firma y su Usuario Administrador inicial con contraseña temporal."""
    # Verificar email único
    user_exists = (await db.execute(select(Usuario).where(Usuario.email == body.admin_email))).scalar_one_or_none()
    if user_exists:
        raise HTTPException(status_code=400, detail="El correo electrónico del administrador ya se encuentra registrado")

    if body.ruc:
        firma_exists = (await db.execute(select(Firma).where(Firma.ruc == body.ruc))).scalar_one_or_none()
        if firma_exists:
            raise HTTPException(status_code=400, detail="Ya existe una firma registrada con este RUC")

    from config.plans import PLANES, PLAN_ALIAS_MAP
    resolved = PLAN_ALIAS_MAP.get(body.plan, body.plan)
    if resolved not in PLANES and body.plan != "trial":
        raise HTTPException(status_code=400, detail=f"Plan inválido: {body.plan}")

    nueva_firma = Firma(
        nombre=body.nombre,
        ruc=body.ruc,
        email=body.email or body.admin_email,
        plan=body.plan,
        features_override_json=body.features_override_json,
        activa=True,
        trial_hasta=body.trial_hasta,
    )
    db.add(nueva_firma)
    await db.flush()

    pw_temporal = body.admin_password or generar_password_temporal()
    admin_user = Usuario(
        firma_id=nueva_firma.id,
        email=body.admin_email,
        nombre=body.admin_nombre,
        password_hash=_hash(pw_temporal),
        rol="admin",
        activo=True,
        debe_cambiar_password=True,
    )
    db.add(admin_user)
    await db.commit()

    return FirmaCreateResponse(
        firma=FirmaResponse(
            id=nueva_firma.id,
            nombre=nueva_firma.nombre,
            ruc=nueva_firma.ruc,
            email=nueva_firma.email,
            plan=nueva_firma.plan,
            features_override_json=nueva_firma.features_override_json,
            activa=nueva_firma.activa,
            trial_hasta=nueva_firma.trial_hasta,
            creado_en=nueva_firma.creado_en,
            num_clientes=0,
        ),
        admin_usuario=UsuarioResponse(
            id=admin_user.id,
            firma_id=admin_user.firma_id,
            firma_nombre=nueva_firma.nombre,
            email=admin_user.email,
            nombre=admin_user.nombre,
            rol=admin_user.rol,
            activo=admin_user.activo,
            debe_cambiar_password=admin_user.debe_cambiar_password,
            creado_en=admin_user.creado_en,
            ultimo_acceso=None,
        ),
        password_temporal=pw_temporal,
    )

@router.patch("/firmas/{firma_id}", response_model=FirmaResponse)
async def update_firma(
    firma_id: str,
    body: FirmaUpdateBody,
    super_admin: Usuario = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Actualiza el plan, overrides, vigencia de trial o estado de una firma."""
    result = await db.execute(select(Firma).where(Firma.id == firma_id))
    firma = result.scalar_one_or_none()
    if not firma:
        raise HTTPException(status_code=404, detail="Firma no encontrada")

    if body.plan is not None:
        from config.plans import PLANES, PLAN_ALIAS_MAP
        resolved = PLAN_ALIAS_MAP.get(body.plan, body.plan)
        if resolved not in PLANES and body.plan != "trial":
            raise HTTPException(status_code=400, detail=f"Plan inválido: {body.plan}")
        firma.plan = body.plan
    if body.features_override_json is not None:
        firma.features_override_json = body.features_override_json
    if body.activa is not None:
        firma.activa = body.activa
    if body.trial_hasta is not None:
        firma.trial_hasta = body.trial_hasta

    await db.commit()
    
    count_res = await db.execute(select(func.count(Cliente.id)).where(Cliente.firma_id == firma_id))
    num_clientes = count_res.scalar() or 0

    return FirmaResponse(
        id=firma.id,
        nombre=firma.nombre,
        ruc=firma.ruc,
        email=firma.email,
        plan=firma.plan,
        features_override_json=firma.features_override_json,
        activa=firma.activa,
        trial_hasta=firma.trial_hasta,
        creado_en=firma.creado_en,
        num_clientes=num_clientes
    )

# ============================================================
#  Endpoints de Usuarios
# ============================================================

@router.get("/usuarios", response_model=List[UsuarioResponse])
async def list_usuarios(
    super_admin: Usuario = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Retorna todos los usuarios del sistema, indicando su firma."""
    query = (
        select(Usuario, Firma.nombre.label("firma_nombre"))
        .join(Firma, Usuario.firma_id == Firma.id)
        .order_by(Usuario.creado_en.desc())
    )
    result = await db.execute(query)
    rows = result.all()
    
    response = []
    for user, firma_nombre in rows:
        response.append(UsuarioResponse(
            id=user.id,
            firma_id=user.firma_id,
            firma_nombre=firma_nombre,
            email=user.email,
            nombre=user.nombre,
            rol=user.rol,
            activo=user.activo,
            debe_cambiar_password=user.debe_cambiar_password,
            creado_en=user.creado_en,
            ultimo_acceso=user.ultimo_acceso
        ))
    return response

@router.post("/usuarios", response_model=UsuarioCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_usuario(
    body: UsuarioCreateBody,
    super_admin: Usuario = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Crea un usuario directamente en una firma cliente, verificando límites del plan."""
    firma = (await db.execute(select(Firma).where(Firma.id == body.firma_id))).scalar_one_or_none()
    if not firma:
        raise HTTPException(status_code=404, detail="La firma especificada no existe")

    user_exists = (await db.execute(select(Usuario).where(Usuario.email == body.email))).scalar_one_or_none()
    if user_exists:
        raise HTTPException(status_code=400, detail="El correo electrónico ya se encuentra registrado")

    if body.rol not in ("super_admin", "admin", "auditor_senior", "auditor"):
        raise HTTPException(status_code=400, detail="Rol inválido")

    # Verificar límites de plan
    from config.plans import PLANES, PLAN_ALIAS_MAP
    resolved = PLAN_ALIAS_MAP.get(firma.plan, firma.plan)
    plan_config = PLANES.get(resolved, PLANES["starter"])
    max_usuarios = plan_config.max_usuarios

    if firma.features_override_json:
        try:
            overrides = json.loads(firma.features_override_json)
            if "max_usuarios" in overrides and overrides["max_usuarios"] is not None:
                max_usuarios = int(overrides["max_usuarios"])
        except Exception:
            pass

    if max_usuarios is not None:
        count_users = (await db.execute(
            select(func.count(Usuario.id)).where(Usuario.firma_id == firma.id, Usuario.activo == True)
        )).scalar() or 0
        if count_users >= max_usuarios:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Límite de usuarios ({max_usuarios}) alcanzado para el plan '{firma.plan}' de la firma."
            )

    pw_temporal = body.password or generar_password_temporal()
    nuevo_usuario = Usuario(
        firma_id=firma.id,
        email=body.email,
        nombre=body.nombre,
        password_hash=_hash(pw_temporal),
        rol=body.rol,
        activo=True,
        debe_cambiar_password=True,
    )
    db.add(nuevo_usuario)
    await db.commit()

    return UsuarioCreateResponse(
        usuario=UsuarioResponse(
            id=nuevo_usuario.id,
            firma_id=nuevo_usuario.firma_id,
            firma_nombre=firma.nombre,
            email=nuevo_usuario.email,
            nombre=nuevo_usuario.nombre,
            rol=nuevo_usuario.rol,
            activo=nuevo_usuario.activo,
            debe_cambiar_password=nuevo_usuario.debe_cambiar_password,
            creado_en=nuevo_usuario.creado_en,
            ultimo_acceso=None,
        ),
        password_temporal=pw_temporal,
    )

@router.patch("/usuarios/{usuario_id}", response_model=UsuarioResponse)
async def update_usuario(
    usuario_id: str,
    body: UsuarioUpdateBody,
    super_admin: Usuario = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Permite cambiar datos básicos, rol o estado activo/desactivado de un usuario."""
    result = await db.execute(
        select(Usuario, Firma.nombre.label("firma_nombre"))
        .join(Firma, Usuario.firma_id == Firma.id)
        .where(Usuario.id == usuario_id)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    user, firma_nombre = row
    
    if body.nombre is not None:
        user.nombre = body.nombre
    if body.rol is not None:
        if body.rol not in ("super_admin", "admin", "auditor_senior", "auditor"):
            raise HTTPException(status_code=400, detail="Rol inválido")
        user.rol = body.rol
    if body.activo is not None:
        user.activo = body.activo
        
    await db.commit()
    
    return UsuarioResponse(
        id=user.id,
        firma_id=user.firma_id,
        firma_nombre=firma_nombre,
        email=user.email,
        nombre=user.nombre,
        rol=user.rol,
        activo=user.activo,
        debe_cambiar_password=user.debe_cambiar_password,
        creado_en=user.creado_en,
        ultimo_acceso=user.ultimo_acceso
    )

@router.patch("/usuarios/{usuario_id}/password")
async def reset_usuario_password(
    usuario_id: str,
    body: PasswordResetBody,
    super_admin: Usuario = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Restablece la contraseña de cualquier usuario del sistema y exige cambio en primer login."""
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")
        
    user.password_hash = _hash(body.password)
    user.debe_cambiar_password = body.debe_cambiar_password
    await db.commit()
    return {"ok": True, "message": "Contraseña restablecida con éxito"}
