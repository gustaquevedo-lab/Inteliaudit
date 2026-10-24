"""
Parser semántico para normativas tributarias y legales paraguayas.
Divide leyes, decretos y resoluciones generales preservando la jerarquía jurídica
(Libro, Título, Capítulo, Artículo, Inciso).
"""
import re
from dataclasses import dataclass
from typing import Optional

@dataclass
class ChunkNormativo:
    jerarquia: str
    articulo: str
    numeral_inciso: Optional[str]
    texto: str


def parsear_texto_normativa(texto: str, nombre_normativa: str) -> list[ChunkNormativo]:
    """
    Segmenta un texto legal estructurado por Artículos, manteniendo el encabezado jerárquico.
    """
    lineas = [l.strip() for l in texto.split("\n") if l.strip()]
    chunks: list[ChunkNormativo] = []
    
    current_jerarquia_parts = [nombre_normativa]
    current_articulo: Optional[str] = None
    current_texto_lines: list[str] = []
    
    # Patrones jerárquicos
    re_libro = re.compile(r'^(LIBRO\s+[IVXLCDM\d]+.*?)$', re.IGNORECASE)
    re_titulo = re.compile(r'^(TÍTULO\s+[IVXLCDM\d]+.*?)$', re.IGNORECASE)
    re_capitulo = re.compile(r'^(CAPÍTULO\s+[IVXLCDM\d]+.*?)$', re.IGNORECASE)
    re_seccion = re.compile(r'^(SECCIÓN\s+[IVXLCDM\d]+.*?)$', re.IGNORECASE)
    
    # Patrón de artículo: "Artículo 16.-", "Art. 16", "Artículo 1°.-"
    re_articulo = re.compile(r'^(Art[ií]culo\s+\d+[°º\.]?|Art\.\s*\d+[°º\.]?)(.*)$', re.IGNORECASE)
    
    for linea in lineas:
        # Detectar cambios de jerarquía mayor
        m_lib = re_libro.match(linea)
        if m_lib:
            current_jerarquia_parts = [p for p in current_jerarquia_parts if not p.upper().startswith("LIBRO") and not p.upper().startswith("TÍTULO") and not p.upper().startswith("CAPÍTULO")]
            current_jerarquia_parts.append(m_lib.group(1))
            continue
            
        m_tit = re_titulo.match(linea)
        if m_tit:
            current_jerarquia_parts = [p for p in current_jerarquia_parts if not p.upper().startswith("TÍTULO") and not p.upper().startswith("CAPÍTULO")]
            current_jerarquia_parts.append(m_tit.group(1))
            continue
            
        m_cap = re_capitulo.match(linea)
        if m_cap:
            current_jerarquia_parts = [p for p in current_jerarquia_parts if not p.upper().startswith("CAPÍTULO")]
            current_jerarquia_parts.append(m_cap.group(1))
            continue

        # Detectar nuevo artículo
        m_art = re_articulo.match(linea)
        if m_art:
            # Guardar el artículo anterior si existía
            if current_articulo and current_texto_lines:
                chunks.append(ChunkNormativo(
                    jerarquia=" > ".join(current_jerarquia_parts),
                    articulo=current_articulo,
                    numeral_inciso=None,
                    texto="\n".join(current_texto_lines).strip()
                ))
                current_texto_lines = []
            
            # Iniciar nuevo artículo
            art_prefix = m_art.group(1).strip().rstrip(".")
            current_articulo = art_prefix
            resto = m_art.group(2).strip()
            if resto.startswith(".-") or resto.startswith("-"):
                resto = resto.lstrip(".-").strip()
            current_texto_lines = [f"{art_prefix}.- {resto}" if resto else art_prefix]
        else:
            if current_articulo:
                current_texto_lines.append(linea)
            else:
                # Texto introductorio antes del primer artículo
                pass

    # Guardar el último artículo
    if current_articulo and current_texto_lines:
        chunks.append(ChunkNormativo(
            jerarquia=" > ".join(current_jerarquia_parts),
            articulo=current_articulo,
            numeral_inciso=None,
            texto="\n".join(current_texto_lines).strip()
        ))
        
    return chunks
