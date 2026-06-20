"""
Tests para conciliación contable → fiscal — analisis/conciliacion_fiscal.py
"""
import pytest
import pytest_asyncio

from analisis.conciliacion_fiscal import (
    ConciliacionFiscal,
    AjusteExtracontable,
    ResultadoConciliacionFiscal,
    TASAS_DEPRECIACION,
    GASTOS_NO_DEDUCIBLES,
)


class TestAjusteExtracontable:
    def test_dataclass_creation(self):
        a = AjusteExtracontable(
            concepto="Multas SET", tipo="suma",
            monto=500000, articulo_legal="Art. 16 Ley 6380",
        )
        assert a.concepto == "Multas SET"
        assert a.tipo == "suma"
        assert a.monto == 500000
        assert a.es_permanente is True


class TestResultadoConciliacionFiscal:
    def test_default_values(self):
        r = ResultadoConciliacionFiscal(periodo="2024-03", procedimiento="Test")
        assert r.resultado_contable == 0
        assert r.ajustes_suma == 0
        assert r.ajustes_resta == 0
        assert r.renta_neta_imponible == 0
        assert r.impuesto_esperado == 0


class TestTasasDepreciacion:
    def test_inmuebles_rate(self):
        assert TASAS_DEPRECIACION["inmuebles"] == 0.025

    def test_vehiculos_rate(self):
        assert TASAS_DEPRECIACION["vehiculos"] == 0.20

    def test_equipos_informaticos_rate(self):
        assert TASAS_DEPRECIACION["equipos_informaticos"] == 0.333

    def test_all_rates_below_100_percent(self):
        for tipo, tasa in TASAS_DEPRECIACION.items():
            assert 0 < tasa < 1.0, f"Tasa inválida para {tipo}: {tasa}"


class TestGastosNoDeducibles:
    def test_all_categories_exist(self):
        assert "multas" in GASTOS_NO_DEDUCIBLES
        assert "intereses_mora" in GASTOS_NO_DEDUCIBLES
        assert "gastos_personales" in GASTOS_NO_DEDUCIBLES
        assert "retiros" in GASTOS_NO_DEDUCIBLES
        assert "donaciones_exceso" in GASTOS_NO_DEDUCIBLES


class TestConciliacionFiscal:
    @pytest.mark.asyncio
    async def test_cliente_no_encontrado(self, db_session, firma, auditoria):
        conciliacion = ConciliacionFiscal(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        resultado = await conciliacion.ejecutar(
            cliente_id="nonexistent-id",
            periodo="2024-03",
            resultado_contable=50000000,
        )
        assert "Cliente no encontrado" in resultado.errores

    @pytest.mark.asyncio
    async def test_renta_neta_calculation(self, db_session, firma, cliente, auditoria):
        """Renta neta = resultado contable + ajustes suma - ajustes resta."""
        conciliacion = ConciliacionFiscal(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            resultado_contable=100000000,
        )
        assert resultado.renta_neta_imponible == 100000000
        assert resultado.resultado_contable == 100000000

    @pytest.mark.asyncio
    async def test_gastos_multas_no_deducibles(self, db_session, firma, cliente, auditoria):
        """Multas SET son gastos no deducibles (ajuste suma)."""
        conciliacion = ConciliacionFiscal(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=0,
        )
        gastos = {"Multas SET": 5000000, "Servicios normales": 10000000}
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            resultado_contable=100000000,
            gastos_operativos=gastos,
        )
        assert resultado.ajustes_suma == 5000000
        assert resultado.renta_neta_imponible == 105000000

    @pytest.mark.asyncio
    async def test_gastos_personales_no_deducibles(self, db_session, firma, cliente, auditoria):
        """Gastos personales del dueño son no deducibles."""
        conciliacion = ConciliacionFiscal(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=0,
        )
        gastos = {"Gastos personales del dueño": 3000000}
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            resultado_contable=50000000,
            gastos_operativos=gastos,
        )
        assert resultado.ajustes_suma == 3000000

    @pytest.mark.asyncio
    async def test_donaciones_deducibles_dentro_limite(self, db_session, firma, cliente, auditoria):
        """Donaciones ≤ 1% renta bruta son deducibles."""
        conciliacion = ConciliacionFiscal(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=0,
        )
        # 1% de 100M = 1M → donación de 800K está dentro
        gastos = {"Donación Fundación": 800000}
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            resultado_contable=100000000,
            gastos_operativos=gastos,
        )
        # No debe ser no deducible
        assert resultado.ajustes_suma == 0

    @pytest.mark.asyncio
    async def test_donaciones_exceso_no_deducible(self, db_session, firma, cliente, auditoria):
        """Donaciones > 1% renta bruta → exceso es no deducible."""
        conciliacion = ConciliacionFiscal(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=0,
        )
        # 1% de 100M = 1M → donación de 2M → 1M excedente
        gastos = {"Donación Fundación": 2000000}
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            resultado_contable=100000000,
            gastos_operativos=gastos,
        )
        assert resultado.ajustes_suma == 1000000  # Solo el excedente

    @pytest.mark.asyncio
    async def test_ire_esperado_10_percent(self, db_session, firma, cliente, auditoria):
        """IRE esperado = 10% de renta neta imponible."""
        conciliacion = ConciliacionFiscal(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=0,
        )
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            resultado_contable=100000000,
        )
        assert resultado.impuesto_esperado == 10000000  # 10% de 100M

    @pytest.mark.asyncio
    async def test_compras_ruc_inactivo_ajuste(
        self, db_session, firma, cliente, auditoria, rg90_compras
    ):
        """Compras con RUC inactivo generan ajuste suma."""
        conciliacion = ConciliacionFiscal(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=0,
        )
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            resultado_contable=50000000,
        )
        # rg90_compras tiene 1 compra con ruc_activo=False (IVA: 500K)
        ajuste_inactivo = [
            a for a in resultado.ajustes
            if "RUC" in a.concepto and "inactivo" in a.concepto
        ]
        assert len(ajuste_inactivo) == 1
        assert ajuste_inactivo[0].monto == 500000

    @pytest.mark.asyncio
    async def test_diferencia_genera_hallazgo(
        self, db_session, firma, cliente, auditoria
    ):
        """Si IRE esperado ≠ declarado → hallazgo generado."""
        from db.models import Declaracion
        from tests.conftest import _uuid
        import json

        # Declarar IRE de 0 cuando debería ser 10M
        decl = Declaracion(
            id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
            auditoria_id=auditoria.id, formulario="500", periodo="2024-03",
            fecha_presentacion="2024-04-20", estado_declaracion="original",
            nro_rectificativa=0,
            datos_json=json.dumps({"ire_a_pagar": 0}),
        )
        db_session.add(decl)
        await db_session.flush()

        conciliacion = ConciliacionFiscal(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=0,
        )
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            resultado_contable=100000000,
        )
        assert resultado.diferencia == 10000000
        assert resultado.hallazgos_generados >= 1


class TestConciliacionFiscalCompleja:
    @pytest.mark.asyncio
    async def test_multiple_ajustes(self, db_session, firma, cliente, auditoria):
        """Múltiples gastos no deducibles se suman correctamente."""
        conciliacion = ConciliacionFiscal(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=0,
        )
        gastos = {
            "Multas SET": 2000000,
            "Intereses mora": 1500000,
            "Gastos personales dueño": 3000000,
            "Retiro socio": 5000000,
            "Servicios normales": 8000000,
        }
        resultado = await conciliacion.ejecutar(
            cliente_id=cliente.id,
            periodo="2024-03",
            resultado_contable=80000000,
            gastos_operativos=gastos,
        )
        # 2M + 1.5M + 3M + 5M = 11.5M en ajustes
        assert resultado.ajustes_suma == 11500000
        assert resultado.renta_neta_imponible == 91500000
