"""
Tests para validación de configuración de producción y generador de secretos.
"""
import pytest
from cryptography.fernet import Fernet
from api.main import _validate_config
from config.settings import settings
from scripts.generate_production_secrets import generate_secrets


def test_generate_secrets_creates_valid_keys():
    """Verifica que el generador produzca SECRET_KEY de 64 hex y ENCRYPTION_KEY Fernet válido."""
    secrets = generate_secrets()
    assert "SECRET_KEY" in secrets
    assert "ENCRYPTION_KEY" in secrets
    assert len(secrets["SECRET_KEY"]) == 64
    # Validar que sea Fernet key válida
    f = Fernet(secrets["ENCRYPTION_KEY"].encode())
    token = f.encrypt(b"test-secret-marangatu")
    assert f.decrypt(token) == b"test-secret-marangatu"


def test_validate_config_detects_default_and_invalid_keys(monkeypatch):
    """Verifica que _validate_config detecte secret default y encryption_key inválida."""
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "secret_key", "dev-secret-change-in-production")
    monkeypatch.setattr(settings, "encryption_key", "clave-invalida-no-fernet")
    
    errors, warnings = _validate_config()
    
    # Debe advertir sobre la SECRET_KEY por defecto
    assert any("SECRET_KEY" in w for w in warnings)
    # Debe advertir sobre la ENCRYPTION_KEY inválida
    assert any("ENCRYPTION_KEY" in w and "inválid" in w.lower() for w in warnings)


def test_validate_config_passes_with_valid_keys(monkeypatch):
    """Verifica que con claves generadas válidas no reporte warnings de claves."""
    valid_secrets = generate_secrets()
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "secret_key", valid_secrets["SECRET_KEY"])
    monkeypatch.setattr(settings, "encryption_key", valid_secrets["ENCRYPTION_KEY"])
    
    errors, warnings = _validate_config()
    
    assert not any("SECRET_KEY" in w for w in warnings)
    assert not any("ENCRYPTION_KEY" in w for w in warnings)
