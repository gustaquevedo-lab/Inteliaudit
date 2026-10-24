"""
Tests para parser de extractos bancarios — ingesta/parser_banco.py
"""
import tempfile
from pathlib import Path
import openpyxl
import pytest

from ingesta.parser_banco import (
    _normalizar_header,
    _normalizar_fecha_iso,
    _parsear_monto_py,
    parsear_extracto_bancario,
)


def test_normalizar_fecha_iso():
    assert _normalizar_fecha_iso("15/03/2024") == "2024-03-15"
    assert _normalizar_fecha_iso("05-12-2023") == "2023-12-05"
    assert _normalizar_fecha_iso("2024-04-10") == "2024-04-10"
    assert _normalizar_fecha_iso("1/2/24") == "2024-02-01"


def test_parsear_monto_py():
    assert _parsear_monto_py("1.500.000") == 1500000
    assert _parsear_monto_py("-500.000") == -500000
    assert _parsear_monto_py("2,500,000") == 2500000
    assert _parsear_monto_py("(100.000)") == -100000
    assert _parsear_monto_py(1200000) == 1200000
    assert _parsear_monto_py("0") == 0


def test_parsear_extracto_csv():
    csv_content = """Fecha,Concepto,Debito,Credito,Saldo
01/03/2024,Venta cliente Alfa,,15000000,15000000
05/03/2024,Pago proveedor Beta,5000000,,10000000
10/03/2024,Supermercado personal,350000,,9650000
"""
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
        f.write(csv_content)
        path = f.name

    try:
        txs = parsear_extracto_bancario(path)
        assert len(txs) == 3
        assert txs[0].tipo == "ingreso"
        assert txs[0].monto == 15000000
        assert txs[0].fecha == "2024-03-01"

        assert txs[1].tipo == "egreso"
        assert txs[1].monto == -5000000

        assert txs[2].tipo == "egreso"
        assert txs[2].monto == -350000
        assert "supermercado" in txs[2].descripcion.lower()
    finally:
        Path(path).unlink(missing_ok=True)


def test_parsear_extracto_xlsx():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Fecha Movimiento", "Detalle de Transacción", "Monto"])
    ws.append(["15/04/2024", "Cobro factura 001-001-000123", 22000000])
    ws.append(["18/04/2024", "Retiro ATM cajero", -2000000])

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        wb.save(f.name)
        path = f.name

    try:
        txs = parsear_extracto_bancario(path)
        assert len(txs) == 2
        assert txs[0].monto == 22000000
        assert txs[0].tipo == "ingreso"
        assert txs[1].monto == -2000000
        assert txs[1].tipo == "egreso"
    finally:
        Path(path).unlink(missing_ok=True)
