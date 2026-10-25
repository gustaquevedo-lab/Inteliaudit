"""
Tests para el sistema de backup automatizado de PostgreSQL a Cloudflare R2.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from storage.backup_postgres import perform_database_backup, purge_old_backups


@pytest.mark.asyncio
async def test_perform_database_backup_generates_and_uploads_dump(tmp_path, monkeypatch):
    """Verifica que el script genere el volcado y lo suba mediante el storage adapter."""
    mock_storage = MagicMock()
    mock_storage.upload = AsyncMock(return_value="https://r2.storage/backups/postgres/test.sql.gz")
    
    # Mock subprocess.run para pg_dump
    def fake_subprocess_run(cmd, *args, **kwargs):
        # Crear archivo simulado .sql
        output_file = cmd[cmd.index("-f") + 1] if "-f" in cmd else None
        if output_file:
            with open(output_file, "wb") as f:
                f.write(b"-- PostgreSQL database dump simulated\n")
        return MagicMock(returncode=0)

    with patch("subprocess.run", side_effect=fake_subprocess_run), \
         patch("storage.backup_postgres.get_storage", return_value=mock_storage):
        
        result = await perform_database_backup(backup_dir=str(tmp_path), upload_to_r2=True)
        
        assert result["success"] is True
        assert result["key"].startswith("backups/postgres/inteliaudit_backup_")
        assert result["key"].endswith(".sql.gz")
        assert mock_storage.upload.called


@pytest.mark.asyncio
async def test_purge_old_backups(tmp_path):
    """Verifica la eliminación de volcados locales antiguos."""
    import time
    old_file = tmp_path / "inteliaudit_backup_20200101_000000.sql.gz"
    old_file.write_bytes(b"dummy old backup")
    
    # Modificar mtime para simular antigüedad de 10 días
    ten_days_ago = time.time() - (10 * 86400)
    import os
    os.utime(str(old_file), (ten_days_ago, ten_days_ago))
    
    new_file = tmp_path / "inteliaudit_backup_20261025_000000.sql.gz"
    new_file.write_bytes(b"dummy fresh backup")
    
    deleted = purge_old_backups(directory=str(tmp_path), retention_days=7)
    assert len(deleted) == 1
    assert deleted[0] == str(old_file)
    assert not old_file.exists()
    assert new_file.exists()
