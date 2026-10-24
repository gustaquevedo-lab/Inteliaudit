"""
Router para validación y consulta de comprobantes electrónicos SIFEN.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from api.routers.auth import get_current_user
from db.models import Usuario
from ingesta.sifen_client import consultar_o_validar_cdc

router = APIRouter(prefix="/sifen", tags=["sifen"])


@router.get("/validar-cdc/{cdc}")
async def validar_cdc_endpoint(
    cdc: str,
    consultar_online: bool = False,
    db: AsyncSession = Depends(get_db),
    user: Usuario = Depends(get_current_user)
):
    """
    Valida un Código de Control (CDC) de 44 dígitos.
    Aplica verificación algorítmica Módulo 11 y caché global persistente.
    """
    resultado = await consultar_o_validar_cdc(db, cdc, consultar_online=consultar_online)
    return resultado
