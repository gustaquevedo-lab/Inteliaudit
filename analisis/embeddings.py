"""
Generación de embeddings vectoriales para RAG Legal y memoria.
Utiliza Ollama local con el modelo nomic-embed-text (768 dimensiones).
Incluye fallback determinista para entornos de test offline o CI.
"""
import hashlib
import json
import logging
import urllib.request
from typing import List, Optional
from config.settings import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "nomic-embed-text"
VECTOR_DIM = 768


def generar_embedding(texto: str) -> list[float]:
    """
    Genera un vector embedding de 768 dimensiones para el texto proporcionado.
    """
    if not texto or not texto.strip():
        return [0.0] * VECTOR_DIM

    url = f"{settings.ollama_base_url.rstrip('/')}/api/embeddings"
    payload = json.dumps({"model": EMBEDDING_MODEL, "prompt": texto.strip()}).encode("utf-8")

    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                vec = data.get("embedding", [])
                if isinstance(vec, list) and len(vec) == VECTOR_DIM:
                    return [float(x) for x in vec]
    except Exception as e:
        logger.debug(f"Ollama embedding offline o inalcanzable ({e}); usando fallback determinista.")

    # Fallback determinista de 768 dimensiones basado en sha256 para tests / offline
    return _generar_embedding_fallback(texto)


def _generar_embedding_fallback(texto: str) -> list[float]:
    """Genera un vector normalizado pseudo-aleatorio pero determinista de 768 dimensiones."""
    vector = []
    # Generar 768 floats basados en secuencias de hash
    seed = texto.strip().encode("utf-8")
    for i in range(VECTOR_DIM // 32):  # 24 bloques de 32 bytes
        h = hashlib.sha256(seed + i.to_bytes(4, "little")).digest()
        for b in h:
            vector.append((b - 128.0) / 128.0)
            
    # Normalizar norma L2
    norm = sum(x * x for x in vector) ** 0.5
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector
