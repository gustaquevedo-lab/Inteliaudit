# Especificación de Diseño: Agente Forense con RAG Legal, Memoria en Grafo y Aislamiento Multi-Tenant

**Fecha:** 2026-10-24  
**Estado:** Propuesta aprobada por el usuario  
**Subsistema:** Inteligencia Artificial, RAG Legal y Memoria Forense (`Inteliaudit`)  

---

## 1. Resumen Ejecutivo y Objetivos

Inteliaudit requiere un agente auditor forense inteligente conectado a su entorno de ejecución local en el dev-server (Ollama Qwen 14B / `inteliaudit-forense`), capaz de:
1. **Asimilar y actualizar dinámicamente el marco legal tributario paraguayo** mediante un RAG vectorial y textual de normativas (Ley 6380/19, Decretos 3107/19 y 3181/19, RG 90/2021, Ley 125/91 y compendio NIAs).
2. **Garantizar un aislamiento criptográfico y relacional absoluto** entre firmas auditoras (tenants) y entre clientes auditados dentro de una misma firma, eliminando alucinaciones y contaminación cruzada de datos.
3. **Mantener una memoria en grafo persistente** de las relaciones económicas del cliente (proveedores, comprobantes, CDCs, bancos y hallazgos) que permita al agente razonar forensemente.
4. **Ejecutar herramientas en vivo (*Tool Calling*)** para consultar la base de datos de comprobantes, verificar estados de RUC, calcular contingencias y redactar papeles de trabajo NIA 230 con 1 clic.
5. **Ofrecer una interfaz visual administrativa** (`/admin/normativas`) para consultar las leyes vigentes y subir nuevas resoluciones DNIT para su ingesta inmediata.

---

## 2. Aislamiento Multi-Tenant y por Cliente (Zero Cross-Contamination)

La arquitectura divide el conocimiento en tres capas estrictamente segregadas:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        CAPA 1: GLOBAL / PÚBLICA                        │
│  Base Legal Paraguay (Ley 6380, Dec 3107, RG 90/21, Ley 125, NIAs)    │
│  • Almacenamiento: Tablas `normativas_legales` y `normativas_chunks`   │
│  • Criterio: Datos públicos generales, sin datos de contribuyentes     │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │
                                   ▼
┌──────────────────────────────────┴─────────────────────────────────────┐
│                    CAPA 2: TENANT DE LA FIRMA                          │
│  Firma Auditora (`firma_id` obligatorio)                               │
│  • Manuales internos de procedimientos, umbrales de materialidad       │
├────────────────────────────────────────────────────────────────────────┤
│                    CAPA 3: CLIENTE AUDITADO                            │
│  Auditoría Activa (`firma_id` + `cliente_id` + `auditoria_id`)         │
│  • Grafo de Entidades: `grafo_nodos` y `grafo_aristas`                 │
│  • Memoria de Conversaciones: `agente_conversaciones` y `mensajes`     │
│  • Filtro Forzoso: Todas las tools inyectan cláusulas WHERE compuestas │
└────────────────────────────────────────────────────────────────────────┘
```

### Reglas de Seguridad en Consultas
- Ningún parámetro de `firma_id` o `cliente_id` es aceptado libremente desde el texto del prompt del usuario.
- El contexto se extrae forzosamente de la sesión autenticada (`get_current_user`) y de la entidad `Auditoria` verificada en base de datos.
- Si un auditor intenta consultar comprobantes o RUCs pertenecientes a otro cliente, la capa de herramientas responde con un error de autorización y no retorna registros.

---

## 3. Modelo de Datos en PostgreSQL

Se añadirán las siguientes tablas en el esquema relacional gestionadas vía Alembic:

### 3.1. Normativas Legales y RAG (Capa Global / Tenant)
```sql
CREATE TABLE normativas_legales (
    id VARCHAR(36) PRIMARY KEY,
    firma_id VARCHAR(36) REFERENCES firmas(id) ON DELETE CASCADE NULL, -- NULL si es global
    tipo VARCHAR(50) NOT NULL, -- 'ley', 'decreto', 'resolucion_general', 'nia'
    numero VARCHAR(50) NOT NULL, -- '6380/2019', '90/2021', '3107/2019'
    titulo TEXT NOT NULL,
    organismo VARCHAR(100) DEFAULT 'DNIT',
    fecha_vigencia DATE,
    estado VARCHAR(20) DEFAULT 'vigente', -- 'vigente', 'modificada', 'derogada'
    fuente_url TEXT,
    archivo_ruta TEXT,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE normativas_chunks (
    id VARCHAR(36) PRIMARY KEY,
    normativa_id VARCHAR(36) REFERENCES normativas_legales(id) ON DELETE CASCADE,
    jerarquia TEXT NOT NULL, -- 'Título I > Cap. III > Art. 16'
    articulo VARCHAR(50),
    numeral_inciso VARCHAR(50),
    texto TEXT NOT NULL,
    embedding JSONB, -- Vector de 768 dimensiones generado por nomic-embed-text
    tsv TSVECTOR, -- Para Full-Text Search en español
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_normativas_chunks_normativa ON normativas_chunks(normativa_id);
CREATE INDEX idx_normativas_chunks_tsv ON normativas_chunks USING GIN(tsv);
```

### 3.2. Grafo de Conocimiento Contable-Forense (Capa Cliente)
```sql
CREATE TABLE grafo_nodos (
    id VARCHAR(36) PRIMARY KEY,
    firma_id VARCHAR(36) REFERENCES firmas(id) ON DELETE CASCADE NOT NULL,
    cliente_id VARCHAR(36) REFERENCES clientes(id) ON DELETE CASCADE NOT NULL,
    auditoria_id VARCHAR(36) REFERENCES auditorias(id) ON DELETE CASCADE NOT NULL,
    tipo VARCHAR(50) NOT NULL, -- 'cliente', 'proveedor', 'banco', 'hallazgo'
    identificador VARCHAR(100) NOT NULL, -- ej: RUC o Nombre
    etiqueta TEXT NOT NULL,
    atributos_json JSONB DEFAULT '{}'::jsonb,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE grafo_aristas (
    id VARCHAR(36) PRIMARY KEY,
    firma_id VARCHAR(36) REFERENCES firmas(id) ON DELETE CASCADE NOT NULL,
    cliente_id VARCHAR(36) REFERENCES clientes(id) ON DELETE CASCADE NOT NULL,
    auditoria_id VARCHAR(36) REFERENCES auditorias(id) ON DELETE CASCADE NOT NULL,
    nodo_origen_id VARCHAR(36) REFERENCES grafo_nodos(id) ON DELETE CASCADE NOT NULL,
    nodo_destino_id VARCHAR(36) REFERENCES grafo_nodos(id) ON DELETE CASCADE NOT NULL,
    relacion VARCHAR(50) NOT NULL, -- 'PROVEEDOR_DE', 'DECLARADO_EN', 'DISCREPA_CON', 'PAGO_BANCARIO'
    peso FLOAT DEFAULT 1.0,
    metadatos_json JSONB DEFAULT '{}'::jsonb,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_grafo_nodos_scope ON grafo_nodos(firma_id, cliente_id, auditoria_id);
CREATE INDEX idx_grafo_aristas_scope ON grafo_aristas(firma_id, cliente_id, auditoria_id);
```

### 3.3. Memoria Persistente de Sesión del Agente
```sql
CREATE TABLE agente_conversaciones (
    id VARCHAR(36) PRIMARY KEY,
    firma_id VARCHAR(36) REFERENCES firmas(id) ON DELETE CASCADE NOT NULL,
    auditoria_id VARCHAR(36) REFERENCES auditorias(id) ON DELETE CASCADE NOT NULL,
    usuario_id VARCHAR(36) REFERENCES usuarios(id) ON DELETE SET NULL,
    titulo VARCHAR(200) NOT NULL,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE agente_mensajes (
    id VARCHAR(36) PRIMARY KEY,
    conversacion_id VARCHAR(36) REFERENCES agente_conversaciones(id) ON DELETE CASCADE NOT NULL,
    rol VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system', 'tool'
    contenido TEXT NOT NULL,
    herramientas_usadas JSONB,
    tokens INT DEFAULT 0,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 4. Pipeline de Ingestión y Chunking Legal

1. **Parser Semántico Jurídico (`ingesta/normativas_parser.py`):**
   - No corta por cantidad fija de caracteres, sino por límites gramaticales y normativos: `Artículo \d+°?`, `Capítulo [IVXLCDM]+`, `Inciso [a-z]\)`.
   - Asocia el contexto superior al chunk para garantizar que la citación sea exacta (ej: *"Ley 6380/2019, Libro I IRE, Capítulo III Gastos, Art. 16 Gastos No Deducibles, Inciso b)"*).
2. **Generación de Embeddings:**
   - Consume el endpoint local de Ollama: `POST http://localhost:11434/api/embeddings` con modelo `nomic-embed-text` (768 dimensiones).
3. **Búsqueda Híbrida (`analisis/rag_service.py`):**
   - Pondera similitud de coseno vectorial (70%) + Full-Text Search de PostgreSQL en español (30%).
   - Retorna los fragmentos con su referencia legal exacta y nivel de coincidencia.

---

## 5. Tool Calling y Capacidades Forenses del Agente

El orquestador en `api/routers/agente.py` expone al modelo local las siguientes herramientas:

| Herramienta | Entradas | Acción Realizada |
| :--- | :--- | :--- |
| `consultar_normativa_legal` | `query: str, impuesto?: str` | Búsqueda híbrida en la base de normativas paraguayas |
| `buscar_comprobantes_cliente` | `tipo: str, ruc?: str, solo_sin_cdc?: bool` | Consulta en PostgreSQL acotada a `(firma_id, cliente_id)` |
| `consultar_relaciones_proveedor` | `ruc: str` | Recorre el grafo local para obtener historial de compras, estado DNIT y alertas |
| `recalcular_contingencia_fiscal` | `monto: int, periodo: str, reincidente: bool` | Aplica cálculo del Art. 175 Ley 125/91 con recargos e intereses |
| `crear_borrador_cedula_trabajo` | `tipo: str, titulo: str, conclusiones: str` | Inserta un registro en `cedulas` vinculado a la auditoría |

---

## 6. Interfaz de Usuario Web (`ui-web`)

1. **Panel de Gestión Normativa (`/admin/normativas`):**
   - Catálogo de leyes y resoluciones vigentes.
   - Indicador del total de chunks indexados.
   - Dropzone para arrastrar nuevos PDFs o textos de normativas con botón de "Indexar y Actualizar Cerebro".
2. **Copilot Drawer Mejorado con Memoria:**
   - Selección o creación de hilos de conversación guardados por auditoría.
   - Visualización de herramientas ejecutadas en vivo (tags colapsables *"Consultó Art. 16 Ley 6380"*, *"Consultó compras proveedor 80012345-6"*).
   - Botón directo para convertir una conclusión del agente en Cédula de Auditoría NIA 230.

---

## 7. Plan de Pruebas y Validación

1. **Test de Aislamiento Tenant/Cliente:** Verificar que una consulta en la auditoría del Cliente A jamás reciba registros ni del grafo ni de los comprobantes del Cliente B.
2. **Test de Ingestión y RAG:** Subir una resolución simulada, verificar chunking por artículos, generación de embedding vía Ollama y recuperación exacta ante una consulta.
3. **Test de Tool Calling:** Simular consulta forense en el chat y verificar que el agente invoque `consultar_relaciones_proveedor` y `consultar_normativa_legal` antes de emitir la conclusión.
4. **Verificación en Dev-Server:** Despliegue en PM2, ejecución de migraciones Alembic y prueba interactiva en `https://inteliaudit.intellihouse.lat`.
