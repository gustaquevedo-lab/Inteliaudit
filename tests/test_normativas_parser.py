import pytest
from ingesta.normativas_parser import parsear_texto_normativa, ChunkNormativo
from analisis.embeddings import generar_embedding

def test_parsear_normativa_articulos():
    texto_ejemplo = """
    LEY N° 6380
    DE MODERNIZACIÓN Y SIMPLIFICACIÓN DEL SISTEMA TRIBUTARIO NACIONAL
    
    LIBRO I
    IMPUESTO A LA RENTA EMPRESARIAL (IRE)
    
    CAPÍTULO III
    RENTA NETA
    
    Artículo 16.- Gastos no deducibles.
    No serán deducibles en la determinación del IRE:
    1. Los intereses moratorios y multas.
    2. Los gastos personales del dueño o socios.
    
    Artículo 17.- Tasa del Impuesto.
    La tasa del IRE será del 10% (diez por ciento) sobre la renta neta imponible.
    """
    chunks = parsear_texto_normativa(texto_ejemplo, "Ley 6380/2019")
    assert len(chunks) == 2
    assert chunks[0].articulo == "Artículo 16"
    assert "Gastos no deducibles" in chunks[0].texto
    assert "LIBRO I" in chunks[0].jerarquia
    assert chunks[1].articulo == "Artículo 17"
    assert "10%" in chunks[1].texto

def test_parsear_resolucion_general():
    texto_rg = """
    RESOLUCIÓN GENERAL N° 90/2021
    POR LA CUAL SE IMPLEMENTA EL REGISTRO ELECTRÓNICO DE COMPROBANTES
    
    Artículo 1°.- Objeto.
    Establecer la obligación de registrar electrónicamente los comprobantes de compras y ventas.
    
    Artículo 2°.- Sujetos obligados.
    Estarán obligados los contribuyentes del IVA e IRE.
    """
    chunks = parsear_texto_normativa(texto_rg, "RG 90/2021")
    assert len(chunks) == 2
    assert chunks[0].articulo == "Artículo 1°"
    assert "comprobantes" in chunks[0].texto
    assert chunks[1].articulo == "Artículo 2°"

def test_generar_embedding_dummy_or_live():
    # En entorno de test sin Ollama activo o con Ollama, debe retornar lista de floats de dimensión 768
    vector = generar_embedding("Art. 16 Gastos no deducibles")
    assert isinstance(vector, list)
    assert len(vector) == 768
    assert all(isinstance(x, (float, int)) for x in vector)
