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
    activa: bool
    trial_hasta: Optional[datetime]
    creado_en: datetime
    num_clientes: int

class FirmaUpdateBody(BaseModel):
    plan: Optional[str] = None
    activa: Optional[bool] = None
    trial_hasta: Optional[datetime] = None

class UsuarioResponse(BaseModel):
    id: str
    firma_id: str
    firma_nombre: Optional[str]
    email: str
    nombre: str
    rol: str
    activo: bool
    creado_en: datetime
    ultimo_acceso: Optional[datetime]

class UsuarioUpdateBody(BaseModel):
    nombre: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None

class PasswordResetBody(BaseModel):
    password: str

# ============================================================
#  Endpoints de Firmas (Tenants)
# ============================================================

@router.get("/firmas", response_model=List[FirmaResponse])
async def list_firmas(
    super_admin: Usuario = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Retorna todas las firmas registradas con su conteo de clientes."""
    # Consultamos las firmas y hacemos un count de clientes
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
            activa=firma.activa,
            trial_hasta=firma.trial_hasta,
            creado_en=firma.creado_en,
            num_clientes=num_clientes
        ))
    return response

@router.patch("/firmas/{firma_id}", response_model=FirmaResponse)
async def update_firma(
    firma_id: str,
    body: FirmaUpdateBody,
    super_admin: Usuario = Depends(get_current_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Actualiza el plan, vigencia de trial o estado de una firma."""
    result = await db.execute(select(Firma).where(Firma.id == firma_id))
    firma = result.scalar_one_or_none()
    if not firma:
        raise HTTPException(status_code=404, detail="Firma no encontrada")

    if body.plan is not None:
        # Validar plan
        from config.plans import PLANES, PLAN_ALIAS_MAP
        resolved = PLAN_ALIAS_MAP.get(body.plan, body.plan)
        if resolved not in PLANES and body.plan != "trial":
            raise HTTPException(status_code=400, detail=f"Plan inválido: {body.plan}")
        firma.plan = body.plan
    if body.activa is not None:
        firma.activa = body.activa
    if body.trial_hasta is not None:
        firma.trial_hasta = body.trial_hasta

    await db.commit()
    
    # Obtener conteo de clientes
    count_res = await db.execute(select(func.count(Cliente.id)).where(Cliente.firma_id == firma_id))
    num_clientes = count_res.scalar() or 0

    return FirmaResponse(
        id=firma.id,
        nombre=firma.nombre,
        ruc=firma.ruc,
        email=firma.email,
        plan=firma.plan,
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
            creado_en=user.creado_en,
            ultimo_acceso=user.ultimo_acceso
        ))
    return response

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
    """Restablece la contraseña de cualquier usuario del sistema."""
    result = await db.execute(select(Usuario).where(Usuario.id == usuario_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres")
        
    user.password_hash = _hash(body.password)
    await db.commit()
    return {"ok": True, "message": "Contraseña restablecida con éxito"}
