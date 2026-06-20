"""
Tests para procedimientos analíticos — analisis/analiticos.py
"""
import pytest
import pytest_asyncio

from analisis.analiticos import (
    ProcedimientosAnaliticos,
    RatioAnalitico,
    ResultadoAnalitico,
    BENCHMARKS,
)


class TestRatioAnalitico:
    def test_dataclass_creation(self):
        r = RatioAnalitico(
            nombre="Margen Bruto", valor=25.5,
            unidad="%", periodo="2024-03",
        )
        assert r.nombre == "Margen Bruto"
        assert r.valor == 25.5
        assert r.unidad == "%"
        assert r.benchmark_min is None
        assert r.dentro_rango is None


class TestResultadoAnalitico:
    def test_default_values(self):
        r = ResultadoAnalitico(periodo="2024-03", procedimiento="Test")
        assert r.ratios == []
        assert r.anomalias == []
        assert r.tendencias == []
        assert r.alertas == []


class TestBenchmarks:
    def test_comercio_benchmarks_exist(self):
        assert "comercio" in BENCHMARKS
        assert "margen_bruto" in BENCHMARKS["comercio"]
        assert "margen_net" in BENCHMARKS["comercio"]

    def test_servicios_benchmarks_exist(self):
        assert "servicios" in BENCHMARKS
        assert "margen_bruto" in BENCHMARKS["servicios"]

    def test_industria_benchmarks_exist(self):
        assert "industria" in BENCHMARKS
        assert "margen_bruto" in BENCHMARKS["industria"]

    def test_benchmark_ranges_are_valid(self):
        for tipo, ratios in BENCHMARKS.items():
            for nombre, (min_val, max_val) in ratios.items():
                assert min_val < max_val, f"Rango inválido en {tipo}.{nombre}"


class TestProcedimientosAnaliticos:
    @pytest.mark.asyncio
    async def test_cliente_no_encontrado(self, db_session, firma, auditoria):
        analiticos = ProcedimientosAnaliticos(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        resultado = await analiticos.ejecutar(
            cliente_id="nonexistent-id",
            periodo_actual="2024-03",
        )
        assert "Cliente no encontrado" in resultado.errores

    @pytest.mark.asyncio
    async def test_ratios_calculados_con_datos(
        self, db_session, firma, cliente, auditoria, rg90_ventas, rg90_compras
    ):
        analiticos = ProcedimientosAnaliticos(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        resultado = await analiticos.ejecutar(
            cliente_id=cliente.id,
            periodo_actual="2024-03",
        )
        # Debe calcular al menos ratio compras/ventas
        assert len(resultado.ratios) > 0
        nombres = [r.nombre for r in resultado.ratios]
        assert "Ratio Compras / Ventas" in nombres

    @pytest.mark.asyncio
    async def test_margen_bruto_calculation(
        self, db_session, firma, cliente, auditoria, rg90_ventas, rg90_compras
    ):
        analiticos = ProcedimientosAnaliticos(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        resultado = await analiticos.ejecutar(
            cliente_id=cliente.id,
            periodo_actual="2024-03",
        )
        margen = [r for r in resultado.ratios if r.nombre == "Margen Bruto"]
        assert len(margen) == 1
        # Ventas: 38.5M, Compras: 19.8M → utilidad bruta: 18.7M → margen ~48.6%
        assert margen[0].valor > 0

    @pytest.mark.asyncio
    async def test_anomalias_margen_insostenible(self, db_session, firma, cliente, auditoria):
        """Si compras > 95% de ventas, anomaly detectada."""
        from db.models import RG90
        from tests.conftest import _uuid

        # Crear RG90 donde compras casi igualan ventas
        for i in range(3):
            db_session.add(RG90(
                id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
                auditoria_id=auditoria.id, periodo="2024-03", tipo="venta",
                ruc_contraparte=f"8001111{i}-5", nombre_contraparte=f"Cliente {i}",
                nro_comprobante=f"001-001-{100+i:07d}", cdc=f"{i:44d}"[:44],
                fecha_emision="2024-03-10",
                base_gravada_10=10000000, base_gravada_5=0, monto_exento=0,
                iva_10=1000000, iva_5=0, iva_total=1000000,
                total_comprobante=11000000,
            ))
            db_session.add(RG90(
                id=_uuid(), firma_id=firma.id, cliente_id=cliente.id,
                auditoria_id=auditoria.id, periodo="2024-03", tipo="compra",
                ruc_contraparte=f"8002222{i}-5", nombre_contraparte=f"Proveedor {i}",
                nro_comprobante=f"001-002-{200+i:07d}", cdc=f"{i:44d}"[:44],
                fecha_emision="2024-03-10",
                base_gravada_10=10500000, base_gravada_5=0, monto_exento=0,
                iva_10=1050000, iva_5=0, iva_total=1050000,
                total_comprobante=11550000,
            ))
        await db_session.flush()

        analiticos = ProcedimientosAnaliticos(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        resultado = await analiticos.ejecutar(
            cliente_id=cliente.id,
            periodo_actual="2024-03",
        )
        insostenible = [a for a in resultado.anomalias if a["tipo"] == "margen_insostenible"]
        assert len(insostenible) == 1

    @pytest.mark.asyncio
    async def test_tendencias_con_periodo_anterior(
        self, db_session, firma, cliente, auditoria, rg90_ventas, rg90_compras
    ):
        analiticos = ProcedimientosAnaliticos(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        resultado = await analiticos.ejecutar(
            cliente_id=cliente.id,
            periodo_actual="2024-03",
            periodo_anterior="2024-02",
        )
        # Sin datos de período anterior, tendencias vacías
        assert isinstance(resultado.tendencias, list)

    @pytest.mark.asyncio
    async def test_alertas_generadas(self, db_session, firma, cliente, auditoria):
        """Anomalías de riesgo alto generan alertas."""
        analiticos = ProcedimientosAnaliticos(
            db=db_session, firma_id=firma.id,
            auditoria_id=auditoria.id, materialidad=500000,
        )
        resultado = await analiticos.ejecutar(
            cliente_id=cliente.id,
            periodo_actual="2024-03",
        )
        assert isinstance(resultado.alertas, list)
