"""
Tests de los 5 cruces IVA.
analisis/iva.py — procedimientos de auditoria IVA.
"""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from analisis.iva import AuditoriaIVA, ResultadoCruceIVA


class TestCruceRG90vsForm120:
    """Cruce 1: RG90 vs Form.120 — consistencia de totales."""

    @pytest.mark.asyncio
    async def test_sin_declaracion(self, db_session, firma, cliente, auditoria):
        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id, materialidad=500000)
        r = await auditor.cruce_rg90_vs_form120(cliente.id, "2024-03")
        assert r.hallazgos_generados == 0
        assert len(r.errores) > 0

    @pytest.mark.asyncio
    async def test_con_declaracion_sin_diferencia(
        self, db_session, firma, cliente, auditoria,
        rg90_compras, rg90_ventas, declaracion_form120
    ):
        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id, materialidad=500000)
        r = await auditor.cruce_rg90_vs_form120(cliente.id, "2024-03")
        assert isinstance(r, ResultadoCruceIVA)
        assert r.periodo == "2024-03"
        assert r.cruce == "RG90 vs Form.120"


class TestCruceRG90vsSIFEN:
    """Cruce 2: RG90 compras vs SIFEN — validacion de CDC."""

    @pytest.mark.asyncio
    async def test_cdc_cancelado_genera_hallazgo(
        self, db_session, firma, cliente, auditoria,
        rg90_compras, sifen_comprobantes
    ):
        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id, materialidad=500000)
        r = await auditor.cruce_rg90_vs_sifen(cliente.id, "2024-03")
        assert r.hallazgos_generados >= 1
        assert r.monto_ajuste > 0

    @pytest.mark.asyncio
    async def test_sin_cdc_post_obligatoriedad(
        self, db_session, firma, cliente, auditoria, rg90_compras
    ):
        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id, materialidad=0)
        r = await auditor.cruce_rg90_vs_sifen(cliente.id, "2024-03")
        sin_cdc = [c for c in rg90_compras if not c.cdc]
        if sin_cdc:
            assert r.hallazgos_generados >= 1


class TestCruceSIFENvsRG90:
    """Cruce 3: SIFEN recibidas vs RG90 — credito omitido."""

    @pytest.mark.asyncio
    async def test_requiere_descarga_marangatu(self, db_session, firma, cliente, auditoria):
        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id)
        r = await auditor.cruce_sifen_vs_rg90(cliente.id, "2024-03")
        assert len(r.errores) > 0


class TestCruceRG90vsHECHAUKA:
    """Cruce 4: RG90 ventas vs HECHAUKA — debito omitido."""

    @pytest.mark.asyncio
    async def test_venta_omitida_en_rg90(
        self, db_session, firma, cliente, auditoria,
        rg90_ventas, hechauka_registros
    ):
        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id, materialidad=0)
        r = await auditor.cruce_rg90_vs_hechauka(cliente.id, "2024-03")
        assert r.hallazgos_generados >= 1
        assert r.monto_ajuste > 0

    @pytest.mark.asyncio
    async def test_sin_hechauka(self, db_session, firma, cliente, auditoria, rg90_ventas):
        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id)
        r = await auditor.cruce_rg90_vs_hechauka(cliente.id, "2024-03")
        assert len(r.errores) > 0


class TestCruceRUCProveedores:
    """Cruce 5: RUC proveedores activos — credito fiscal invalido."""

    @pytest.mark.asyncio
    async def test_ruc_inactivo_genera_hallazgo(
        self, db_session, firma, cliente, auditoria, rg90_compras
    ):
        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id, materialidad=0)
        r = await auditor.cruce_ruc_proveedores(cliente.id, "2024-03")
        inactivos = [c for c in rg90_compras if c.ruc_activo is False]
        if inactivos:
            assert r.hallazgos_generados >= 1
            assert r.monto_ajuste > 0

    @pytest.mark.asyncio
    async def test_todos_activos_sin_hallazgos(
        self, db_session, firma, cliente, auditoria
    ):
        from db.models import RG90
        import uuid
        compra = RG90(
            id=str(uuid.uuid4()), firma_id=firma.id, cliente_id=cliente.id,
            auditoria_id=auditoria.id, periodo="2024-06", tipo="compra",
            ruc_contraparte="80011111-1", nombre_contraparte="Proveedor OK",
            nro_comprobante="001-001-9999999", cdc=None,
            fecha_emision="2024-06-15",
            base_gravada_10=1000000, iva_total=100000,
            total_comprobante=1100000, ruc_activo=True,
        )
        db_session.add(compra)
        await db_session.flush()

        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id, materialidad=0)
        r = await auditor.cruce_ruc_proveedores(cliente.id, "2024-06")
        assert r.hallazgos_generados == 0


class TestEjecutarAuditoriaCompleta:

    @pytest.mark.asyncio
    async def test_ejecuta_5_cruces_por_periodo(
        self, db_session, firma, cliente, auditoria,
        rg90_compras, rg90_ventas, sifen_comprobantes,
        hechauka_registros, declaracion_form120
    ):
        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id, materialidad=0)
        resultados = await auditor.ejecutar_auditoria_completa(
            cliente.id, ["2024-03"]
        )
        assert len(resultados) == 5

    @pytest.mark.asyncio
    async def test_multiples_periodos(
        self, db_session, firma, cliente, auditoria
    ):
        auditor = AuditoriaIVA(db_session, firma.id, auditoria.id)
        resultados = await auditor.ejecutar_auditoria_completa(
            cliente.id, ["2024-01", "2024-02", "2024-03"]
        )
        assert len(resultados) == 15
