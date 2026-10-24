"""
Servicio RAG Legal Híbrido para Inteliaudit.
Combina embeddings vectoriales (nomic-embed-text) con coincidencia léxica / FTS.
Garantiza el aislamiento multi-tenant: normativas globales (firma_id IS NULL)
más las normativas privadas de la firma en sesión.
"""
import math
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import NormativaLegal, NormativaChunk
from analisis.embeddings import generar_embedding


@dataclass
class ResultadoRAG:
    normativa_id: str
    normativa_numero: str
    normativa_titulo: str
    jerarquia: str
    articulo: Optional[str]
    texto: str
    score: float


def _similitud_coseno(v1: list[float], v2: list[float]) -> float:
    """Calcula similitud coseno entre dos vectores numéricos."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a, b in zip(v1, v1)))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 <= 0.0 or norm2 <= 0.0:
        return 0.0
    return dot / (norm1 * norm2)


async def indexar_normativa(
    db: AsyncSession,
    normativa_id: str,
    chunks: list[dict | Any]
) -> int:
    """
    Persiste y vectoriza los fragmentos de una normativa.
    """
    total = 0
    for ch in chunks:
        articulo = ch.articulo if hasattr(ch, "articulo") else ch.get("articulo")
        jerarquia = ch.jerarquia if hasattr(ch, "jerarquia") else ch.get("jerarquia", "")
        numeral = ch.numeral_inciso if hasattr(ch, "numeral_inciso") else ch.get("numeral_inciso")
        texto = ch.texto if hasattr(ch, "texto") else ch.get("texto", "")

        emb = generar_embedding(f"{jerarquia} {articulo or ''} {texto}")
        
        chunk_obj = NormativaChunk(
            normativa_id=normativa_id,
            jerarquia=jerarquia,
            articulo=articulo,
            numeral_inciso=numeral,
            texto=texto,
            embedding=emb
        )
        db.add(chunk_obj)
        total += 1

    await db.commit()
    return total


async def buscar_normativas(
    db: AsyncSession,
    query: str,
    limit: int = 5,
    firma_id: Optional[str] = None
) -> list[ResultadoRAG]:
    """
    Búsqueda híbrida de normativas tributarias:
    Score = 0.7 * Similitud Coseno + 0.3 * Coincidencia Léxica.
    Aislamiento: sólo normativas globales (firma_id IS NULL) o de la firma indicada.
    """
    if not query or not query.strip():
        return []

    # 1. Embedding de la consulta
    query_emb = generar_embedding(query.strip())
    palabras_query = [p.lower() for p in query.lower().split() if len(p) > 2]

    # 2. Filtrado con aislamiento de firma
    condicion_firma = NormativaLegal.firma_id.is_(None)
    if firma_id:
        condicion_firma = or_(NormativaLegal.firma_id.is_(None), NormativaLegal.firma_id == firma_id)

    stmt = (
        select(NormativaChunk, NormativaLegal)
        .join(NormativaLegal, NormativaChunk.normativa_id == NormativaLegal.id)
        .where(condicion_firma)
    )
    result = await db.execute(stmt)
    rows = result.all()

    candidatos: list[ResultadoRAG] = []
    for chunk, norm in rows:
        sim_vec = _similitud_coseno(query_emb, chunk.embedding or [])
        
        # Puntuación léxica complementaria
        texto_completo = f"{norm.numero} {norm.titulo} {chunk.jerarquia} {chunk.articulo or ''} {chunk.texto}".lower()
        coincidencias = sum(1 for p in palabras_query if p in texto_completo)
        sim_lex = (coincidencias / max(len(palabras_query), 1))

        # Score híbrido normalizado
        score = 0.7 * max(0.0, sim_vec) + 0.3 * sim_lex

        candidatos.append(ResultadoRAG(
            normativa_id=norm.id,
            normativa_numero=norm.numero,
            normativa_titulo=norm.titulo,
            jerarquia=chunk.jerarquia,
            articulo=chunk.articulo,
            texto=chunk.texto,
            score=score
        ))

    # Ordenar por mayor score descendente
    candidatos.sort(key=lambda x: x.score, reverse=True)
    return candidatos[:limit]
