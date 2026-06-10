"""
Tests de autenticacion: login, JWT, permisos por rol.
api/routers/auth.py — JWT HS256 + bcrypt.
"""
import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt

from config.settings import settings
from db.models import Firma, Usuario


class TestJWT:

    def test_crear_token(self, usuario_admin):
        from api.routers.auth import _crear_token
        token = _crear_token({"sub": usuario_admin.id, "rol": "admin"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_token_contiene_claims(self, usuario_admin, firma):
        from api.routers.auth import _crear_token
        token = _crear_token({"sub": usuario_admin.id, "firma_id": firma.id, "rol": "admin"})
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == usuario_admin.id
        assert payload["firma_id"] == firma.id
        assert payload["rol"] == "admin"
        assert "exp" in payload

    def test_token_expiracion(self, usuario_admin):
        from api.routers.auth import _crear_token
        token = _crear_token({"sub": usuario_admin.id}, expire_minutes=30)
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp > datetime.now(timezone.utc)

    def test_token_invalido_sin_secret(self, usuario_admin):
        from api.routers.auth import _crear_token
        token = _crear_token({"sub": usuario_admin.id})
        with pytest.raises(Exception):
            jwt.decode(token, "wrong-secret", algorithms=[settings.jwt_algorithm])


class TestPasswordHashing:

    def test_hash_y_verify(self):
        from api.routers.auth import _hash, _verify
        password = "mi_password_seguro_123"
        hashed = _hash(password)
        assert hashed != password
        assert _verify(password, hashed) is True

    def test_verify_wrong_password(self):
        from api.routers.auth import _hash, _verify
        hashed = _hash("password_correcto")
        assert _verify("password_incorrecto", hashed) is False

    def test_hash_diferente_cada_vez(self):
        from api.routers.auth import _hash
        h1 = _hash("mismo_password")
        h2 = _hash("mismo_password")
        assert h1 != h2


class TestCifradoCredenciales:

    def test_cifrar_y_descifrar(self):
        from api.routers.auth import _cifrar_credencial, _descifrar_credencial
        texto = "mi_usuario_dnit"
        cifrado = _cifrar_credencial(texto)
        assert cifrado != texto
        assert _descifrar_credencial(cifrado) == texto

    def test_cifrar_diferente_cada_vez(self):
        from api.routers.auth import _cifrar_credencial
        c1 = _cifrar_credencial("mismo_texto")
        c2 = _cifrar_credencial("mismo_texto")
        assert c1 != c2


class TestRoles:

    def test_admin_tiene_acceso_admin(self, usuario_admin):
        assert usuario_admin.rol in ("super_admin", "admin")

    def test_auditor_no_tiene_acceso_admin(self, usuario_auditor):
        assert usuario_auditor.rol not in ("super_admin", "admin")

    def test_usuario_activo(self, usuario_admin):
        assert usuario_admin.activo is True

    def test_usuario_datos_firma(self, usuario_admin, firma):
        assert usuario_admin.firma_id == firma.id
