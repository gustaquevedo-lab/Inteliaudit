"""
Script de siembra inicial de Normativas Legales y RAG para Inteliaudit.
Carga e indexa en la base de datos (PostgreSQL / SQLite) los textos y artículos
fundamentales de la legislación tributaria paraguaya y compendio NIA.
"""
import os
import sys

# Asegurar path raíz del proyecto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import asyncio
import logging
from sqlalchemy import select
from db.base import AsyncSessionLocal
from db.models import NormativaLegal, NormativaChunk
from ingesta.normativas_parser import parsear_texto_normativa
from analisis.rag_service import indexar_normativa

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_normativas")

NORMATIVAS_SEED = [
    {
        "tipo": "ley",
        "numero": "6380/2019",
        "titulo": "De Modernización y Simplificación del Sistema Tributario Nacional",
        "organismo": "Congreso Nacional / DNIT",
        "texto": """
LEY N° 6380/2019
DE MODERNIZACIÓN Y SIMPLIFICACIÓN DEL SISTEMA TRIBUTARIO NACIONAL

LIBRO I
IMPUESTO A LA RENTA EMPRESARIAL (IRE)

CAPÍTULO III
RENTA NETA

Artículo 16.- Gastos no deducibles.
No serán deducibles en la determinación del IRE:
1. Los intereses moratorios, recargos y multas aplicadas por infracciones cometidas ante la Administración Tributaria u otros organismos públicos.
2. Los gastos personales del dueño, socios, accionistas, directores o sus familiares, así como retiros de utilidades por cuenta de socios.
3. Las donaciones que excedan el 1% (uno por ciento) del ingreso bruto gravado del contribuyente en el ejercicio fiscal.
4. Los gastos que carezcan de comprobantes de venta debidamente timbrados o autorizados conforme a la reglamentación.
5. Los gastos respaldados por comprobantes emitidos por contribuyentes con RUC en estado cancelado, suspendido o inactivo al momento de la operación.
6. Las depreciaciones de activos fijos que superen las tasas máximas establecidas en el Decreto reglamentario.
7. Los gastos de representación que superen el 1% (uno por ciento) de los ingresos brutos del ejercicio.

Artículo 17.- Tasa del Impuesto.
La tasa del IRE general será del 10% (diez por ciento) sobre la renta neta imponible determinada conforme a esta ley.

Artículo 35.- Normas de Valoración (Partes Vinculadas).
Las operaciones realizadas entre partes vinculadas residentes o no residentes deberán ser pactadas a precios de mercado bajo el principio de plena competencia (arm's length), aplicando los métodos de precios de transferencia.

LIBRO II
IMPUESTO AL VALOR AGREGADO (IVA)

CAPÍTULO II
BASE IMPONIBLE Y CRÉDITO FISCAL

Artículo 85.- Crédito Fiscal.
El crédito fiscal se integrará con el impuesto discriminado en los comprobantes de compra de bienes y servicios destinados a operaciones gravadas por el IVA. Solo será admisible cuando provenga de comprobantes legales válidos y vigentes en el SIFEN (factura electrónica) o autorizados por la DNIT.

Artículo 86.- Liquidación y Alícuotas.
La tasa general del IVA será del 10% (diez por ciento) para la generalidad de bienes y servicios, y del 5% (cinco por ciento) para productos de la canasta familiar, medicamentos y servicios personales.
"""
    },
    {
        "tipo": "resolucion_general",
        "numero": "90/2021",
        "titulo": "Por la cual se implementa el Registro Electrónico de Comprobantes y se reglamenta el Talón de Presentación",
        "organismo": "DNIT",
        "texto": """
RESOLUCIÓN GENERAL N° 90/2021
REGISTRO ELECTRÓNICO DE COMPROBANTES DE COMPRAS Y VENTAS

Artículo 1°.- Objeto y Alcance.
Establécese la obligación del Registro Electrónico de Comprobantes de compras y ventas para contribuyentes del IVA e IRE en el Sistema Marangatú.

Artículo 3°.- Modalidad y Plazos de Presentación.
Los contribuyentes designados deberán confirmar el registro de sus comprobantes de compras y ventas mensualmente a través del Formulario N° 241 (Talón de Presentación) y Formulario N° 242 (Talón Resumen) según el calendario de vencimientos de la DNIT.

Artículo 16°.- Derogación del Régimen HECHAUKA.
A partir del 01 de enero de 2022 quedan derogadas las disposiciones de la Resolución General N° 48/2014 (HECHAUKA) relativas al registro de libros de compras y ventas, quedando vigente únicamente para la presentación de Estados Financieros y Estudios de Precios de Transferencia.
"""
    },
    {
        "tipo": "ley",
        "numero": "125/1991",
        "titulo": "Código Tributario de la República del Paraguay",
        "organismo": "Congreso Nacional",
        "texto": """
LEY N° 125/1991
RÉGIMEN TRIBUTARIO Y SANCIONATORIO

Artículo 175.- Infracciones y Sanciones por Omisión de Pago.
La omisión del pago de tributos configurará contravención u omisión simple sujeta a una multa equivalente al 50% (cincuenta por ciento) del impuesto omitido. En casos de reincidencia o contumacia debidamente comprobada, la sanción ascenderá al 100% (cien por ciento) del impuesto omitido, más los intereses moratorios devengados por mes o fracción de mes de atraso.

Artículo 218.- Prescripción de la Acción de Cobro.
La acción de la Administración Tributaria para perseguir el cobro de la deuda tributaria líquida y exigible prescribe a los 5 (cinco) años contados a partir del primer día del año siguiente a aquel en que debió abonarse el tributo.

Artículo 219.- Prescripción de la Facultad de Fiscalización y Determinación.
La facultad de la Administración Tributaria para determinar de oficio obligaciones fiscales y aplicar sanciones prescribe a los 3 (tres) años contados desde el año calendario siguiente a la fecha de vencimiento de la presentación de la declaración jurada.
"""
    },
    {
        "tipo": "nia",
        "numero": "NIA 230 / 520",
        "titulo": "Normas Internacionales de Auditoría: Documentación y Procedimientos Analíticos",
        "organismo": "IFAC",
        "texto": """
NORMAS INTERNACIONALES DE AUDITORÍA
COMPENDIO PAPELES DE TRABAJO Y EVIDENCIA

Artículo 230.- Documentación de Auditoría (NIA 230).
El auditor preparará oportunamente documentación que proporcione un registro suficiente y adecuado de las bases para el dictamen del auditor y evidencia de que la auditoría se planificó y ejecutó de conformidad con las NIA y requisitos legales aplicables. Comprende cédulas sumarias, cédulas analíticas y notas explicativas.

Artículo 520.- Procedimientos Analíticos Sustantivos (NIA 520).
El auditor aplicará procedimientos analíticos evaluando información financiera mediante análisis de relaciones factibles entre datos financieros y no financieros. Cuando los procedimientos identifiquen fluctuaciones o relaciones inconsistentes con información relevante o que difieran de los valores esperados por más del umbral de materialidad (variaciones superiores al 30%), el auditor investigará tales diferencias solicitando indagaciones a la dirección y obteniendo evidencia sustantiva adicional.
"""
    }
]


async def sembrar_normativas():
    logger.info("Iniciando siembra de normativas y chunks RAG...")
    async with AsyncSessionLocal() as db:
        for item in NORMATIVAS_SEED:
            stmt = select(NormativaLegal).where(
                NormativaLegal.numero == item["numero"],
                NormativaLegal.firma_id.is_(None)
            )
            existente = (await db.execute(stmt)).scalar_one_or_none()
            if existente:
                logger.info(f"Normativa {item['numero']} ya existe. Omitiendo creación de cabecera.")
                norm = existente
            else:
                norm = NormativaLegal(
                    firma_id=None,
                    tipo=item["tipo"],
                    numero=item["numero"],
                    titulo=item["titulo"],
                    organismo=item["organismo"],
                    estado="vigente"
                )
                db.add(norm)
                await db.commit()
                await db.refresh(norm)
                logger.info(f"Creada cabecera normativa: {norm.numero} - {norm.titulo}")

            # Parsear e indexar chunks
            chunks = parsear_texto_normativa(item["texto"], f"{norm.tipo.upper()} {norm.numero}")
            
            # Verificar si ya tiene chunks
            stmt_c = select(NormativaChunk).where(NormativaChunk.normativa_id == norm.id)
            c_exist = (await db.execute(stmt_c)).scalars().all()
            if not c_exist:
                total = await indexar_normativa(db, norm.id, chunks)
                logger.info(f"-> Indexados {total} artículos/chunks vectoriales para {norm.numero}")
            else:
                logger.info(f"-> Normativa {norm.numero} ya cuenta con {len(c_exist)} chunks indexados.")

    logger.info("Siembra de normativas finalizada con éxito.")


if __name__ == "__main__":
    asyncio.run(sembrar_normativas())
