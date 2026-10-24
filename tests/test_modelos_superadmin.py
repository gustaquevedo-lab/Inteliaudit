import pytest
from sqlalchemy import select
from db.models import Firma, Usuario, ErrorPlataforma


@pytest.mark.asyncio
async def test_modelo_error_plataforma_y_campos_superadmin(db_session, firma: Firma):
    # 1. Verificar campos en Usuario y Firma
    user = Usuario(
        firma_id=firma.id,
        email="nuevo_admin_test@estudio.com.py",
        nombre="Admin Tenant",
        password_hash="hash_dummy",
        rol="admin",
        debe_cambiar_password=True,
    )
    db_session.add(user)
    firma.features_override_json = '{"tiene_ia": true, "max_clientes": 20}'

    # 2. Verificar ErrorPlataforma
    err = ErrorPlataforma(
        fingerprint="test_fp_1234567890abcdef",
        tipo_error="ZeroDivisionError",
        mensaje="division by zero",
        path="/api/test/fail",
        metodo="POST",
        status_code=500,
        stacktrace="Traceback (most recent call last):\n  File ...",
        firma_id=firma.id,
        usuario_email=user.email,
        ocurrencias=1,
    )
    db_session.add(err)
    await db_session.commit()

    saved_err = (await db_session.execute(
        select(ErrorPlataforma).where(ErrorPlataforma.fingerprint == "test_fp_1234567890abcdef")
    )).scalar_one()

    assert saved_err.tipo_error == "ZeroDivisionError"
    assert saved_err.ocurrencias == 1
    assert saved_err.resuelto is False

    saved_user = (await db_session.execute(
        select(Usuario).where(Usuario.email == "nuevo_admin_test@estudio.com.py")
    )).scalar_one()
    assert saved_user.debe_cambiar_password is True
