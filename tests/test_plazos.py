"""
Tests para gestión de plazos y prescripción — analisis/plazos.py
"""
import pytest
import pytest_asyncio
from datetime import datetime, timedelta

from analisis.plazos import (
    GestionPlazos,
    ObligacionConPlazo,
    ResultadoPlazos,
)


class TestObligacionConPlazo:
    def test_dataclass_creation(self):
        o = ObligacionConPlazo(
            impuesto="120", periodo="2024-03",
            fecha_vencimiento="2024-04-15",
        )
        assert o.impuesto == "120"
        assert o.estado == "pendiente"
        assert o.nivel_riesgo == "bajo"


class TestResultadoPlazos:
    def test_default_values(self):
        r = ResultadoPlazos(fecha_calculo="2024-06-15")
        assert r.obligaciones == []
        assert r.ventanas_fiscalizacion == []
        assert r.alertas == []


class TestGestionPlazos:
    @pytest.mark.asyncio
    async def test_cliente_no_encontrado(self, db_session, firma):
        gestion = GestionPlazos(db=db_session, firma_id=firma.id)
        resultado = await gestion.calcular_plazos(
            cliente_id="nonexistent-id",
            fecha_calculo="2024-06-15",
        )
        assert "Cliente no encontrado" in resultado.errores

    @pytest.mark.asyncio
    async def test_ventanas_fiscalizacion_generadas(self, db_session, firma, cliente):
        gestion = GestionPlazos(db=db_session, firma_id=firma.id)
        resultado = await gestion.calcular_plazos(
            cliente_id=cliente.id,
            fecha_calculo="2024-06-15",
        )
        assert len(resultado.ventanas_fiscalizacion) > 0

    @pytest.mark.asyncio
    async def test_periodos_recientes_no_prescritos(self, db_session, firma, cliente):
        """Períodos recientes (2024) no deben estar prescritos."""
        gestion = GestionPlazos(db=db_session, firma_id=firma.id)
        resultado = await gestion.calcular_plazos(
            cliente_id=cliente.id,
            fecha_calculo="2024-06-15",
        )
        ventana_2024 = [
            v for v in resultado.ventanas_fiscalizacion
            if v["periodo"] == "2024-03"
        ]
        assert len(ventana_2024) == 1
        assert ventana_2024[0]["prescrito_fiscal"] is False
        assert ventana_2024[0]["prescrito_cobro"] is False

    @pytest.mark.asyncio
    async def test_periodos_muy_antiguos_prescritos(self, db_session, firma, cliente):
        """Períodos > 3 años atrás pueden estar prescritos fiscalmente."""
        gestion = GestionPlazos(db=db_session, firma_id=firma.id)
        resultado = await gestion.calcular_plazos(
            cliente_id=cliente.id,
            fecha_calculo="2028-06-15",  # 4+ años después de 2024
        )
        ventana_2024 = [
            v for v in resultado.ventanas_fiscalizacion
            if v["periodo"] == "2024-01"
        ]
        assert len(ventana_2024) == 1
        # 2024-01 + 3 años = 2027-01 → prescrito en 2028
        assert ventana_2024[0]["prescrito_fiscal"] is True

    @pytest.mark.asyncio
    async def test_dias_para_prescribir_fiscal(self, db_session, firma, cliente):
        """Cálculo correcto de días para prescripción fiscal (3 años)."""
        gestion = GestionPlazos(db=db_session, firma_id=firma.id)
        resultado = await gestion.calcular_plazos(
            cliente_id=cliente.id,
            fecha_calculo="2024-06-15",
        )
        ventana_2024 = [
            v for v in resultado.ventanas_fiscalizacion
            if v["periodo"] == "2024-03"
        ][0]
        # 2024-03-28 + 3*365 = ~2027-03-28
        assert ventana_2024["dias_para_prescribir_fiscal"] > 700

    @pytest.mark.asyncio
    async def test_dias_para_prescribir_cobro(self, db_session, firma, cliente):
        """Cálculo correcto de días para prescripción de cobro (5 años)."""
        gestion = GestionPlazos(db=db_session, firma_id=firma.id)
        resultado = await gestion.calcular_plazos(
            cliente_id=cliente.id,
            fecha_calculo="2024-06-15",
        )
        ventana_2024 = [
            v for v in resultado.ventanas_fiscalizacion
            if v["periodo"] == "2024-03"
        ][0]
        # 2024-03-28 + 5*365 = ~2029-03-28
        assert ventana_2024["dias_para_prescribir_cobro"] > 1400

    @pytest.mark.asyncio
    async def test_alertas_prescripcion_proxima(self, db_session, firma, cliente):
        """Genera alertas para períodos con prescripción próxima."""
        gestion = GestionPlazos(db=db_session, firma_id=firma.id)
        # Fecha donde 2021-01 está a ~180 días de prescribir
        # 2021-01 + 3 años = 2024-01 → si estamos en 2023-07, faltan ~180 días
        resultado = await gestion.calcular_plazos(
            cliente_id=cliente.id,
            fecha_calculo="2023-07-01",
        )
        proximas = [a for a in resultado.alertas if a["tipo"] == "prescripcion_proxima"]
        assert len(proximas) > 0

    @pytest.mark.asyncio
    async def test_alertas_ordenadas_por_nivel(self, db_session, firma, cliente):
        """Alertas deben estar ordenadas: alto → medio → bajo → info."""
        gestion = GestionPlazos(db=db_session, firma_id=firma.id)
        resultado = await gestion.calcular_plazos(
            cliente_id=cliente.id,
            fecha_calculo="2023-07-01",
        )
        niveles = [a["nivel"] for a in resultado.alertas]
        nivel_orden = {"alto": 0, "medio": 1, "bajo": 2, "info": 3}
        ordenados = [nivel_orden.get(n, 99) for n in niveles]
        assert ordenados == sorted(ordenados)


class TestCalcularFechaPrescripcion:
    def test_fiscal_3_years(self):
        gestion = GestionPlazos(db=None, firma_id="test")
        fecha = gestion.calcular_fecha_prescripcion("2024-03", "fiscal")
        # 2024-03-28 + timedelta(days=1095) = 2027-03-28 (no leap day between Mar 28s)
        assert fecha == "2027-03-28"

    def test_cobro_5_years(self):
        gestion = GestionPlazos(db=None, firma_id="test")
        fecha = gestion.calcular_fecha_prescripcion("2024-03", "cobro")
        # timedelta(days=5*365) from 2024-03-28 = 2029-03-27
        assert fecha == "2029-03-27"

    def test_enero(self):
        gestion = GestionPlazos(db=None, firma_id="test")
        fecha = gestion.calcular_fecha_prescripcion("2024-01", "fiscal")
        # timedelta(days=3*365) from 2024-01-28 = 2027-01-27
        assert fecha == "2027-01-27"


class TestEstaEnVentanaFiscalizacion:
    def test_dentro_ventana(self):
        gestion = GestionPlazos(db=None, firma_id="test")
        assert gestion.esta_en_ventana_fiscalizacion("2024-03", "2024-06-15") is True

    def test_fuera_ventana(self):
        gestion = GestionPlazos(db=None, firma_id="test")
        assert gestion.esta_en_ventana_fiscalizacion("2020-01", "2025-01-01") is False

    def test_limite_exacto(self):
        gestion = GestionPlazos(db=None, firma_id="test")
        # 2024-03 + 3 años = 2027-03-28
        assert gestion.esta_en_ventana_fiscalizacion("2024-03", "2027-03-28") is True
