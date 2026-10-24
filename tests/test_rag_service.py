import pytest
from sqlalchemy import select
from analisis.rag_service import indexar_normativa, buscar_normativas, ResultadoRAG
from db.models import NormativaLegal, NormativaChunk

@pytest.mark.asyncio
async def test_indexar_y_buscar_rag(db_session, firma):
    # 1. Normativa Global
    norm_global = NormativaLegal(
        tipo="ley",
        numero="6380/2019",
        titulo="De Modernización Tributaria",
        organismo="DNIT",
        firma_id=None # Global
    )
    db_session.add(norm_global)
    await db_session.flush()

    articulos_global = [
        {"articulo": "Art. 16", "jerarquia": "IRE > Renta Neta", "texto": "Gastos no deducibles: multas, sanciones e intereses por infracciones tributarias."},
        {"articulo": "Art. 85", "jerarquia": "IVA > Crédito Fiscal", "texto": "Crédito fiscal admitido con comprobantes legales válidos y vigentes en SIFEN."}
    ]
    total_idx = await indexar_normativa(db_session, norm_global.id, articulos_global)
    assert total_idx == 2

    # 2. Búsqueda semántica por concepto
    resultados = await buscar_normativas(
        db_session,
        query="sanciones fiscales multas deducibles",
        limit=2,
        firma_id=firma.id
    )
    assert len(resultados) >= 1
    assert "Art. 16" in resultados[0].articulo
    assert resultados[0].normativa_numero == "6380/2019"
    assert resultados[0].score > 0

@pytest.mark.asyncio
async def test_aislamiento_normativas_firma(db_session, firma):
    # Normativa privada de otra firma
    norm_otra_firma = NormativaLegal(
        tipo="manual",
        numero="MAN-2024",
        titulo="Manual de Auditoría Secreta",
        organismo="Privado",
        firma_id="otra-firma-uuid-999"
    )
    db_session.add(norm_otra_firma)
    await db_session.flush()

    await indexar_normativa(db_session, norm_otra_firma.id, [
        {"articulo": "Sección 1", "jerarquia": "Manual", "texto": "Criterio confidencial de muestreo interno."}
    ])

    # El auditor de la firma actual busca y NO debe ver el manual de la otra firma
    res = await buscar_normativas(
        db_session,
        query="muestreo interno confidencial",
        limit=5,
        firma_id=firma.id
    )
    numeros_encontrados = [r.normativa_numero for r in res]
    assert "MAN-2024" not in numeros_encontrados
