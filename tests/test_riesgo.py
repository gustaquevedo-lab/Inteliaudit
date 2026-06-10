"""
Tests de calculo de contingencia, multas, intereses y clasificacion de riesgo.
analisis/riesgo.py — logica financiera critica.
"""
import pytest
from analisis.riesgo import (
    MATERIALIDAD_ALTA, MATERIALIDAD_BAJA, MATERIALIDAD_MEDIA,
    MULTA_CONTUMACIA, MULTA_OMISION_SIMPLE, TASA_INTERES_MENSUAL,
    calcular_contingencia, calcular_contingencia_lote,
    calcular_iva_sobre_monto, clasificar_riesgo, clasificar_riesgo_lote,
    formatear_pyg, proporcionalidad_cf, resumir_contingencias,
)


class TestCalcularContingencia:

    def test_contingencia_basica_1_mes(self):
        r = calcular_contingencia(1000000, "2024-02-20", "2024-03-20")
        assert r["impuesto_omitido"] == 1000000
        assert r["multa_estimada"] == 500000
        assert r["intereses_estimados"] == 10000
        assert r["total_contingencia"] == 1510000
        assert r["meses_mora"] == 1
        assert r["tasa_multa"] == 0.50

    def test_contingencia_12_meses(self):
        r = calcular_contingencia(10000000, "2023-01-20", "2024-01-20")
        assert r["meses_mora"] == 12
        assert r["multa_estimada"] == 5000000
        assert r["intereses_estimados"] == 1200000
        assert r["total_contingencia"] == 16200000

    def test_contingencia_reincidente(self):
        r = calcular_contingencia(1000000, "2024-02-20", "2024-03-20", reincidente=True)
        assert r["tasa_multa"] == 1.00
        assert r["multa_estimada"] == 1000000

    def test_contingencia_formato_yyyy_mm(self):
        r = calcular_contingencia(500000, "2024-03", "2024-06-20")
        assert r["meses_mora"] == 3
        assert r["intereses_estimados"] == 15000

    def test_contingencia_meses_cero(self):
        r = calcular_contingencia(1000000, "2024-06-20", "2024-06-20")
        assert r["meses_mora"] == 0
        assert r["intereses_estimados"] == 0
        assert r["total_contingencia"] == 1500000

    def test_contingencia_lote(self):
        hallazgos = [
            {"impuesto_omitido": 1000000, "fecha_omision": "2024-02-20"},
            {"impuesto_omitido": 2000000, "fecha_omision": "2024-01-20", "reincidente": True},
        ]
        resultados = calcular_contingencia_lote(hallazgos, "2024-03-20")
        assert len(resultados) == 2
        assert resultados[0]["tasa_multa"] == 0.50
        assert resultados[1]["tasa_multa"] == 1.00


class TestClasificarRiesgo:

    def test_riesgo_alto(self):
        assert clasificar_riesgo(15000000) == "alto"

    def test_riesgo_medio(self):
        assert clasificar_riesgo(5000000) == "medio"

    def test_riesgo_bajo(self):
        assert clasificar_riesgo(100000) == "bajo"

    def test_riesgo_con_materialidad(self):
        assert clasificar_riesgo(3000000, materialidad=500000) == "medio"
        assert clasificar_riesgo(15000000, materialidad=500000) == "alto"

    def test_riesgo_lote(self):
        hallazgos = [
            {"total_contingencia": 15000000},
            {"total_contingencia": 5000000},
            {"total_contingencia": 100000},
        ]
        resultado = clasificar_riesgo_lote(hallazgos)
        assert resultado[0]["nivel_riesgo"] == "alto"
        assert resultado[1]["nivel_riesgo"] == "medio"
        assert resultado[2]["nivel_riesgo"] == "bajo"


class TestCalcularIVASobreMonto:

    def test_iva_10(self):
        base, iva = calcular_iva_sobre_monto(11000000, 10)
        assert base == 10000000
        assert iva == 1000000

    def test_iva_5(self):
        base, iva = calcular_iva_sobre_monto(5250000, 5)
        assert base == 5000000
        assert iva == 250000

    def test_iva_redondeo(self):
        base, iva = calcular_iva_sobre_monto(1000000, 10)
        assert base + iva == 1000000


class TestProporcionalidadCF:

    def test_proporcional_total_gravado(self):
        assert proporcionalidad_cf(1000000, 10000000, 10000000) == 1000000

    def test_proporcional_50_por_ciento(self):
        assert proporcionalidad_cf(1000000, 5000000, 10000000) == 500000

    def test_proporcional_ventas_cero(self):
        assert proporcionalidad_cf(1000000, 0, 0) == 0


class TestResumirContingencias:

    def test_resumen_basico(self):
        hallazgos = [
            {"impuesto": "IVA", "nivel_riesgo": "alto", "total_contingencia": 10000000,
             "impuesto_omitido": 5000000, "multa_estimada": 2500000, "intereses_estimados": 500000},
            {"impuesto": "IRE", "nivel_riesgo": "medio", "total_contingencia": 3000000,
             "impuesto_omitido": 1500000, "multa_estimada": 750000, "intereses_estimados": 150000},
        ]
        r = resumir_contingencias(hallazgos)
        assert r["total_contingencia"] == 13000000
        assert r["cantidad_hallazgos"] == 2
        assert r["por_impuesto"]["IVA"]["total"] == 10000000
        assert r["por_impuesto"]["IRE"]["cantidad"] == 1
        assert r["por_riesgo"]["alto"] == 10000000

    def test_resumen_excluye_descartados(self):
        hallazgos = [
            {"impuesto": "IVA", "nivel_riesgo": "alto", "total_contingencia": 10000000,
             "impuesto_omitido": 5000000, "multa_estimada": 2500000, "intereses_estimados": 500000,
             "estado": "descartado"},
        ]
        r = resumir_contingencias(hallazgos)
        assert r["total_contingencia"] == 0


class TestFormatearPYG:

    def test_formatear_monto(self):
        assert formatear_pyg(1500000) == "1.500.000"

    def test_formatear_cero(self):
        assert formatear_pyg(0) == "0"

    def test_formatear_grande(self):
        assert formatear_pyg(1234567890) == "1.234.567.890"
