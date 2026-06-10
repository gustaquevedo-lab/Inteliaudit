"""
Storage adapter — interfaz abstracta para almacenamiento de archivos.
Soporta LocalStorage (dev) y Cloudflare R2 (produccion).
"""
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from config.settings import settings


class StorageAdapter(ABC):
    """Interfaz abstracta para almacenamiento de archivos."""

    @abstractmethod
    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Sube un archivo. Retorna URL publica o key."""

    @abstractmethod
    async def download(self, key: str) -> Optional[bytes]:
        """Descarga un archivo. Retorna bytes o None si no existe."""

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Elimina un archivo. Retorna True si existia."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Verifica si un archivo existe."""

    @abstractmethod
    def get_url(self, key: str, expires_in: int = 3600) -> str:
        """Retorna URL publica o presignada."""


class LocalStorageAdapter(StorageAdapter):
    """Almacenamiento en filesystem local (desarrollo)."""

    def __init__(self):
        self.base = Path(settings.storage_path).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        full = self.base / key
        full.parent.mkdir(parents=True, exist_ok=True)
        return full

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        path.write_bytes(data)
        return key

    async def download(self, key: str) -> Optional[bytes]:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None

    async def delete(self, key: str) -> bool:
        path = self._path(key)
        if path.exists():
            path.unlink()
            return True
        return False

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        return key


class R2StorageAdapter(StorageAdapter):
    """Almacenamiento en Cloudflare R2 (S3-compatible, produccion)."""

    def __init__(self):
        import boto3
        endpoint = f"https://{settings.r2_account_id}.r2.cloudflarestorage.com"
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.r2_access_key,
            aws_secret_access_key=settings.r2_secret_key,
        )
        self._bucket = settings.r2_bucket

    async def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data, ContentType=content_type)
        return self.get_url(key)

    async def download(self, key: str) -> Optional[bytes]:
        try:
            obj = self._client.get_object(Bucket=self._bucket, Key=key)
            return obj["Body"].read()
        except self._client.exceptions.NoSuchKey:
            return None

    async def delete(self, key: str) -> bool:
        try:
            self._client.delete_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    async def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except Exception:
            return False

    def get_url(self, key: str, expires_in: int = 3600) -> str:
        if settings.r2_public_url:
            return f"{settings.r2_public_url}/{key}"
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires_in,
        )


# Factory
_storage: Optional[StorageAdapter] = None


def get_storage() -> StorageAdapter:
    """Retorna el adapter segun configuracion."""
    global _storage
    if _storage is not None:
        return _storage

    if settings.r2_account_id and settings.r2_access_key and settings.r2_secret_key:
        _storage = R2StorageAdapter()
    else:
        _storage = LocalStorageAdapter()

    return _storage
