#!/usr/bin/env python3
"""
Generador de Secretos Criptográficos para Producción — Inteliaudit.
Genera SECRET_KEY (64 hex characters) y ENCRYPTION_KEY (Fernet AES-128-CBC + HMAC).
"""
import secrets
from cryptography.fernet import Fernet


def generate_secrets() -> dict[str, str]:
    """Genera las claves criptográficas para el entorno de producción."""
    secret_key = secrets.token_hex(32)  # 64 caracteres hex
    encryption_key = Fernet.generate_key().decode()
    return {
        "SECRET_KEY": secret_key,
        "ENCRYPTION_KEY": encryption_key,
    }


def main():
    keys = generate_secrets()
    print("=" * 60)
    print("  INTELIAUDIT — CLAVES CRIPTOGRÁFICAS DE PRODUCCIÓN")
    print("=" * 60)
    print("\nCopia y pega estas variables en tu archivo .env de producción:\n")
    print(f"SECRET_KEY={keys['SECRET_KEY']}")
    print(f"ENCRYPTION_KEY={keys['ENCRYPTION_KEY']}")
    print("\n" + "=" * 60)
    print("GUARDAR CON CUIDADO: La pérdida de ENCRYPTION_KEY impedirá descifrar")
    print("las credenciales tributarias de Marangatú previamente almacenadas.")
    print("=" * 60)


if __name__ == "__main__":
    main()
