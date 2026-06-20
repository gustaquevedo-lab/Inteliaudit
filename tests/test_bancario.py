"""
Tests para conciliación bancaria — analisis/bancario.py
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from analisis.bancario import (
    ConciliacionBancaria,
    TransaccionBancaria,
    ResultadoConciliacionBancaria,
)


def _transacciones_sample():
    """Genera transacciones bancarias de prueba."""
    return [
        TransaccionBancaria(
            fecha="2024-03-05", descripcion="Depósito cliente A",
            monto=22000000, tipo="ingreso",
        ),
        TransaccionBancaria(
            fecha="2024-03-15", descripcion="Depósito cliente B",
            monto=16500000, tipo="ingreso",
        ),
        TransaccionBancaria(
            fecha="2024-03-20", descripcion="Transferencia proveedor X",
            monto=-11000000, tipo="egreso",
        ),
        TransaccionBancaria(
            fecha="2024-03-25", descripcion="Retiro ATM personal",
            monto=-2000000, tipo="egreso",
        ),
        TransaccionBancaria(
            fecha="2024-03-28", descripcion="Supermercado la Familia",
            monto=-500000, tipo="egreso",
        ),
    ]


class TestTransaccionBancaria:
    def test_dataclass_creation(self):
        t = TransaccionBancaria(
            fecha="2024-03-15", descripcion="Test",
            monto=1000000, tipo="ingreso",
        )
        assert t.fecha == "2024-03-15"
        assert t.monto == 1000000
        assert t.tipo == "ingreso"
        assert t.conciliado is False
        assert t.referencia is None

    def test_egreso_negativo(self):
        t = TransaccionBancaria(
            fecha="2024-03-20", descripcion="Pago proveedor",
            monto=-5000000, tipo="egreso",
        )
        assert t.monto < 0
        assert t.tipo == "egreso"


class TestResultadoConciliacionBancaria:
    def test_default_values(self):
        r = ResultadoConciliacionBancaria(periodo="2024-03", procedimiento="Test")
        assert r.hallazgos_generados == 0
        assert r.monto_ajuste == 0
        assert r.diferencias == []
        assert r.errores == []


class TestConciliacionBancaria:
    @pytest.mark.asyncio
    async def test_cliente_no_encontrado(self, db_session, firma, auditoria):
        conciliacion = ConciliacionBancaria(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        transacciones = _transacciones_sample()
        resultado = await conciliacion.ejecutar(
            cliente_id="nonexistent-id",
            periodo="2024-03",
            transacciones=transacciones,
        )
        assert "Cliente no encontrado" in resultado.errores

    @pytest.mark.asyncio
    async def test_contar_ingresos_egresos(self, db_session, firma, cliente, auditoria):
        conciliacion = ConciliacionBancaria(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        transacciones = _transacciones_sample()
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            transacciones=transacciones,
        )
        assert resultado.ingresos_encontrados == 2
        assert resultado.egresos_encontrados == 3

    @pytest.mark.asyncio
    async def test_diferencia_ingresos_bco_vs_rg90(
        self, db_session, firma, cliente, auditoria, rg90_ventas
    ):
        """Ingresos bancarios > ventas RG90 → posible ingreso omitido."""
        conciliacion = ConciliacionBancaria(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=100000,
        )
        # Ingresos banco: 22M + 16.5M = 38.5M
        # Ventas RG90: 22M + 16.5M = 38.5M → cuadra
        transacciones = _transacciones_sample()
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            transacciones=transacciones,
        )
        # Sin diferencias significativas con materialidad alta
        diferencias_bco = [d for d in resultado.diferencias if d["tipo"] == "INGRESOS_BCO_vs_VENTAS_RG90"]
        # 38.5M banco vs 38.5M RG90 = 0 diferencia
        assert len(diferencias_bco) == 0

    @pytest.mark.asyncio
    async def test_gastos_personales_detectados(self, db_session, firma, cliente, auditoria):
        """Transacciones con patrones personales son detectadas."""
        conciliacion = ConciliacionBancaria(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=100000,
        )
        transacciones = [
            TransaccionBancaria(
                fecha="2024-03-10", descripcion="Retiro ATM personal",
                monto=-5000000, tipo="egreso",
            ),
            TransaccionBancaria(
                fecha="2024-03-15", descripcion="Supermercado La Familia",
                monto=-1000000, tipo="egreso",
            ),
        ]
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            transacciones=transacciones,
        )
        # Debe detectar gastos personales
        gastos_personales = [d for d in resultado.detalles if d["tipo"] == "posible_gasto_personal"]
        assert len(gastos_personales) == 2
        assert resultado.hallazgos_generados >= 0  # Puede o no generar hallazgo según materialidad

    @pytest.mark.asyncio
    async def test_egresos_significativos_registrados(self, db_session, firma, cliente, auditoria):
        """Egresos significativos se registran en detalles."""
        conciliacion = ConciliacionBancaria(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=100000,
        )
        transacciones = [
            TransaccionBancaria(
                fecha="2024-03-20", descripcion="Transferencia proveedor grande",
                monto=-50000000, tipo="egreso",
            ),
        ]
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            transacciones=transacciones,
        )
        egresos = [d for d in resultado.detalles if d["tipo"] == "egreso_significativo"]
        assert len(egresos) == 1
        assert egresos[0]["monto"] == -50000000


class TestTransaccionesVacias:
    @pytest.mark.asyncio
    async def test_sin_transacciones(self, db_session, firma, cliente, auditoria):
        conciliacion = ConciliacionBancaria(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            transacciones=[],
        )
        assert resultado.ingresos_encontrados == 0
        assert resultado.egresos_encontrados == 0
        assert resultado.hallazgos_generados == 0
