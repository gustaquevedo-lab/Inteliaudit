"""
Backup automatizado de PostgreSQL a Cloudflare R2 — Inteliaudit.
Realiza pg_dump, comprime en .sql.gz, sube al bucket R2 y purga respaldos antiguos.
"""
import asyncio
import gzip
import logging
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from config.settings import settings
from storage.adapter import get_storage

logger = logging.getLogger("inteliaudit.backup")


def purge_old_backups(directory: str, retention_days: int = 7) -> list[str]:
    """Elimina respaldos locales más antiguos que retention_days."""
    dir_path = Path(directory)
    if not dir_path.exists():
        return []

    cutoff = time.time() - (retention_days * 86400)
    deleted = []

    for file in dir_path.glob("inteliaudit_backup_*.sql.gz"):
        try:
            if file.stat().st_mtime < cutoff:
                file.unlink()
                deleted.append(str(file))
        except Exception as e:
            logger.warning(f"Error al eliminar backup antiguo {file}: {e}")

    return deleted


async def perform_database_backup(
    backup_dir: str = "./storage/backups",
    upload_to_r2: bool = True,
    retention_days: int = 7,
) -> dict:
    """Ejecuta el volcado de la base de datos, lo comprime y lo sube a R2."""
    dir_path = Path(backup_dir).resolve()
    dir_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sql_file = dir_path / f"inteliaudit_backup_{timestamp}.sql"
    gz_file = dir_path / f"inteliaudit_backup_{timestamp}.sql.gz"
    r2_key = f"backups/postgres/inteliaudit_backup_{timestamp}.sql.gz"

    db_url = settings.database_url
    logger.info(f"Iniciando backup de base de datos ({timestamp})...")

    # Si es SQLite
    if "sqlite" in db_url:
        sqlite_path = db_url.split(":///")[-1]
        if os.path.exists(sqlite_path):
            shutil.copyfile(sqlite_path, sql_file)
        else:
            with open(sql_file, "w") as f:
                f.write("-- Empty database\n")
    else:
        # PostgreSQL: extraer parámetros
        parsed = urlparse(db_url.replace("+asyncpg", ""))
        env = os.environ.copy()
        if parsed.password:
            env["PGPASSWORD"] = parsed.password

        cmd = [
            "pg_dump",
            "-h", parsed.hostname or "localhost",
            "-p", str(parsed.port or 5432),
            "-U", parsed.username or "postgres",
            "-d", parsed.path.lstrip("/") or "inteliaudit",
            "-F", "p",
            "-f", str(sql_file),
        ]
        res = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if res.returncode != 0:
            logger.error(f"Error ejecutando pg_dump: {res.stderr}")
            return {"success": False, "error": res.stderr}

    # Comprimir con gzip
    with open(sql_file, "rb") as f_in:
        with gzip.open(gz_file, "wb", compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)

    # Eliminar el .sql sin comprimir
    if sql_file.exists():
        sql_file.unlink()

    # Subir a R2
    uploaded_url = None
    if upload_to_r2:
        storage = get_storage()
        data = gz_file.read_bytes()
        uploaded_url = await storage.upload(r2_key, data, content_type="application/gzip")
        logger.info(f"Backup subido a R2 exitosamente: {r2_key}")

    # Purgar copias locales antiguas
    purged = purge_old_backups(str(dir_path), retention_days=retention_days)

    return {
        "success": True,
        "local_path": str(gz_file),
        "key": r2_key,
        "url": uploaded_url,
        "size_bytes": gz_file.stat().st_size,
        "purged_files": purged,
    }


def main():
    res = asyncio.run(perform_database_backup())
    if res.get("success"):
        print(f"✅ Backup completado: {res['key']} ({res['size_bytes']} bytes)")
    else:
        print(f"❌ Error en backup: {res.get('error')}")


if __name__ == "__main__":
    main()
