-- ============================================================
--  Inteliaudit — Schema SQL
--  Base de datos por tenant (una DB por cliente o shared con RUC)
--  Compatible con SQLite 3.35+ y PostgreSQL 14+
-- ============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ============================================================
--  CLIENTES / CONTRIBUYENTES
-- ============================================================

CREATE TABLE clientes (
    ruc                 TEXT PRIMARY KEY,          -- ej: "80012345-6"
    razon_social        TEXT NOT NULL,
    nombre_fantasia     TEXT,
    actividad_principal TEXT,
    regimen             TEXT NOT NULL,             -- 'general' | 'simplificado' | 'pequeno'
    tipo_contribuyente  TEXT,                      -- 'empresa' | 'unipersonal' | 'persona_fisica'
    direccion           TEXT,
    email_set           TEXT,
    clave_marangatu     TEXT,                      -- cifrada en producción
    estado_set          TEXT DEFAULT 'activo',     -- 'activo' | 'inactivo' | 'cancelado'
    fecha_inscripcion   TEXT,                      -- YYYY-MM-DD
    fecha_cancelacion   TEXT,
    creado_en           TEXT DEFAULT (datetime('now')),
    actualizado_en      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE obligaciones_activas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_ruc     TEXT NOT NULL REFERENCES clientes(ruc),
    impuesto        TEXT NOT NULL,   -- 'IVA' | 'IRE' | 'IRP' | 'IDU' | 'IRNR' | 'RET_IVA' | 'RET_IRE'
    formulario      TEXT NOT NULL,   -- '120' | '500' | '510' | '520' | '530' | '800' | '820'
    periodicidad    TEXT NOT NULL,   -- 'mensual' | 'anual'
    vigente_desde   TEXT NOT NULL,   -- YYYY-MM-DD
    vigente_hasta   TEXT,            -- NULL = aún activa
    UNIQUE(cliente_ruc, impuesto, formulario, vigente_desde)
);

-- ============================================================
--  AUDITORÍAS
-- ============================================================

CREATE TABLE auditorias (
    id              TEXT PRIMARY KEY,              -- UUID
    cliente_ruc     TEXT NOT NULL REFERENCES clientes(ruc),
    periodo_desde   TEXT NOT NULL,                 -- YYYY-MM
    periodo_hasta   TEXT NOT NULL,                 -- YYYY-MM
    impuestos       TEXT NOT NULL,                 -- JSON array: ["IVA","IRE","RET_IVA"]
    materialidad    INTEGER DEFAULT 0,             -- monto mínimo para reportar hallazgo (PYG)
    estado          TEXT DEFAULT 'en_progreso',    -- 'en_progreso' | 'revision' | 'cerrada'
    auditor         TEXT,
    fecha_inicio    TEXT DEFAULT (datetime('now')),
    fecha_cierre    TEXT,
    notas           TEXT,
    creado_en       TEXT DEFAULT (datetime('now'))
);

-- ============================================================
--  DECLARACIONES JURADAS (lo presentado en Marangatú)
-- ============================================================

CREATE TABLE declaraciones (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    auditoria_id        TEXT REFERENCES auditorias(id),
    cliente_ruc         TEXT NOT NULL REFERENCES clientes(ruc),
    formulario          TEXT NOT NULL,             -- '120', '500', '800', etc.
    periodo             TEXT NOT NULL,             -- YYYY-MM (o YYYY para anuales)
    fecha_presentacion  TEXT NOT NULL,             -- YYYY-MM-DD HH:MM:SS
    estado_declaracion  TEXT NOT NULL,             -- 'original' | 'rectificativa' | 'fuera_plazo'
    nro_rectificativa   INTEGER DEFAULT 0,         -- 0 = original
    datos_json          TEXT NOT NULL,             -- JSON con todos los campos del formulario
    archivo_pdf         TEXT,                      -- ruta relativa al PDF descargado
    descargado_en       TEXT DEFAULT (datetime('now')),
    UNIQUE(cliente_ruc, formulario, periodo, nro_rectificativa)
);

-- índices de búsqueda frecuente
CREATE INDEX idx_declaraciones_cliente_periodo ON declaraciones(cliente_ruc, periodo);
CREATE INDEX idx_declaraciones_formulario ON declaraciones(formulario, periodo);

-- ============================================================
--  RG 90 — Detalle comprobantes declarados en IVA
-- ============================================================

CREATE TABLE rg90 (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    auditoria_id        TEXT REFERENCES auditorias(id),
    cliente_ruc         TEXT NOT NULL REFERENCES clientes(ruc),
    periodo             TEXT NOT NULL,             -- YYYY-MM
    tipo                TEXT NOT NULL,             -- 'compra' | 'venta'
    ruc_contraparte     TEXT NOT NULL,
    nombre_contraparte  TEXT,
    timbrado            TEXT,
    establecimiento     TEXT,                      -- '001'
    punto_expedicion    TEXT,                      -- '001'
    nro_comprobante     TEXT NOT NULL,
    cdc                 TEXT,                      -- 44 dígitos si es electrónico, NULL si papel
    tipo_comprobante    TEXT,                      -- '1'=factura, '4'=autofactura, '5'=NC, '6'=ND
    fecha_emision       TEXT NOT NULL,             -- YYYY-MM-DD
    base_gravada_10     INTEGER DEFAULT 0,         -- PYG sin decimales
    base_gravada_5      INTEGER DEFAULT 0,
    monto_exento        INTEGER DEFAULT 0,
    iva_10              INTEGER DEFAULT 0,
    iva_5               INTEGER DEFAULT 0,
    iva_total           INTEGER DEFAULT 0,
    total_comprobante   INTEGER DEFAULT 0,
    -- Campos de validación (llenados por el sistema después)
    cdc_valido          INTEGER,                   -- 1=válido, 0=inválido, NULL=no verificado
    ruc_activo          INTEGER,                   -- 1=activo, 0=inactivo, NULL=no verificado
    en_sifen            INTEGER,                   -- 1=existe en SIFEN, 0=no existe, NULL=no verificado
    observaciones       TEXT,
    fuente_archivo      TEXT,                      -- nombre del archivo XLSX de origen
    creado_en           TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_rg90_cliente_periodo ON rg90(cliente_ruc, periodo);
CREATE INDEX idx_rg90_cdc ON rg90(cdc) WHERE cdc IS NOT NULL;
CREATE INDEX idx_rg90_ruc_contra ON rg90(ruc_contraparte);

-- ============================================================
--  SIFEN — Comprobantes electrónicos
-- ============================================================

CREATE TABLE sifen_comprobantes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    auditoria_id        TEXT REFERENCES auditorias(id),
    cdc                 TEXT NOT NULL UNIQUE,      -- 44 dígitos
    tipo_de             TEXT NOT NULL,             -- '1'=factura, '4'=auto, '5'=NC, '6'=ND, '7'=remisión
    ruc_emisor          TEXT NOT NULL,
    nombre_emisor       TEXT,
    ruc_receptor        TEXT,
    nombre_receptor     TEXT,
    timbrado            TEXT,
    establecimiento     TEXT,
    punto_expedicion    TEXT,
    nro_comprobante     TEXT,
    fecha_emision       TEXT NOT NULL,             -- YYYY-MM-DDTHH:MM:SS
    fecha_emision_date  TEXT GENERATED ALWAYS AS (substr(fecha_emision,1,10)) VIRTUAL,
    periodo             TEXT GENERATED ALWAYS AS (substr(fecha_emision,1,7)) VIRTUAL,
    base_gravada_10     INTEGER DEFAULT 0,
    base_gravada_5      INTEGER DEFAULT 0,
    monto_exento        INTEGER DEFAULT 0,
    iva_total           INTEGER DEFAULT 0,
    total_comprobante   INTEGER DEFAULT 0,
    estado_sifen        TEXT DEFAULT 'aprobado',   -- 'aprobado' | 'cancelado' | 'inutilizado'
    xml_raw             TEXT,                      -- XML completo para referencia
    consultado_en       TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_sifen_emisor ON sifen_comprobantes(ruc_emisor);
CREATE INDEX idx_sifen_receptor ON sifen_comprobantes(ruc_receptor);
CREATE INDEX idx_sifen_periodo ON sifen_comprobantes(periodo);

-- ============================================================
--  HECHAUKA — Información declarada por terceros
-- ============================================================

CREATE TABLE hechauka (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    auditoria_id        TEXT REFERENCES auditorias(id),
    cliente_ruc         TEXT NOT NULL REFERENCES clientes(ruc),
    periodo             TEXT NOT NULL,             -- YYYY-MM
    ruc_informante      TEXT NOT NULL,             -- quien declaró esta info
    nombre_informante   TEXT,
    tipo_operacion      TEXT NOT NULL,             -- 'compra_a_cliente' | 'retencion_practicada'
    formulario_origen   TEXT,                      -- '120', '800', etc.
    monto_operacion     INTEGER DEFAULT 0,
    iva_operacion       INTEGER DEFAULT 0,
    retencion_iva       INTEGER DEFAULT 0,
    retencion_ire       INTEGER DEFAULT 0,
    fecha_operacion     TEXT,
    nro_comprobante     TEXT,
    fuente_archivo      TEXT,
    creado_en           TEXT DEFAULT (datetime('now'))
);

CREATE INDEX idx_hechauka_cliente_periodo ON hechauka(cliente_ruc, periodo);

-- ============================================================
--  ESTADO DE CUENTA SET
-- ============================================================

CREATE TABLE estado_cuenta (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    auditoria_id        TEXT REFERENCES auditorias(id),
    cliente_ruc         TEXT NOT NULL REFERENCES clientes(ruc),
    impuesto            TEXT NOT NULL,
    periodo             TEXT NOT NULL,
    tipo_movimiento     TEXT NOT NULL,             -- 'deuda' | 'pago' | 'credito' | 'multa' | 'interes'
    monto               INTEGER NOT NULL,
    fecha               TEXT NOT NULL,
    descripcion         TEXT,
    nro_boleta          TEXT,
    descargado_en       TEXT DEFAULT (datetime('now'))
);

-- ============================================================
--  DATOS COMPLEMENTARIOS DEL CLIENTE
-- ============================================================

CREATE TABLE estados_contables (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    auditoria_id        TEXT REFERENCES auditorias(id),
    cliente_ruc         TEXT NOT NULL REFERENCES clientes(ruc),
    ejercicio           TEXT NOT NULL,             -- YYYY
    cuenta_codigo       TEXT NOT NULL,
    cuenta_nombre       TEXT NOT NULL,
    tipo_cuenta         TEXT NOT NULL,             -- 'activo'|'pasivo'|'patrimonio'|'ingreso'|'egreso'
    saldo_inicial       INTEGER DEFAULT 0,
    debitos             INTEGER DEFAULT 0,
    creditos            INTEGER DEFAULT 0,
    saldo_final         INTEGER DEFAULT 0,
    fuente              TEXT                       -- nombre del archivo subido
);

CREATE TABLE movimientos_bancarios (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    auditoria_id        TEXT REFERENCES auditorias(id),
    cliente_ruc         TEXT NOT NULL REFERENCES clientes(ruc),
    banco               TEXT NOT NULL,
    cuenta_nro          TEXT,
    fecha               TEXT NOT NULL,             -- YYYY-MM-DD
    descripcion         TEXT,
    debito              INTEGER DEFAULT 0,
    credito             INTEGER DEFAULT 0,
    saldo               INTEGER,
    conciliado          INTEGER DEFAULT 0,         -- 1 si se encontró comprobante
    comprobante_ref     TEXT,                      -- CDC o nro comprobante relacionado
    fuente              TEXT
);

-- ============================================================
--  ANÁLISIS — Hallazgos
-- ============================================================

CREATE TABLE hallazgos (
    id                  TEXT PRIMARY KEY,          -- UUID
    auditoria_id        TEXT NOT NULL REFERENCES auditorias(id),
    impuesto            TEXT NOT NULL,             -- 'IVA' | 'IRE' | 'RET_IVA' etc.
    periodo             TEXT NOT NULL,             -- YYYY-MM
    tipo_hallazgo       TEXT NOT NULL,             -- ver catálogo abajo
    descripcion         TEXT NOT NULL,
    descripcion_tecnica TEXT,                      -- para papeles de trabajo
    articulo_legal      TEXT NOT NULL,             -- "Art. 95 Ley 125/1991"
    base_ajuste         INTEGER DEFAULT 0,         -- base imponible ajustada (PYG)
    impuesto_omitido    INTEGER DEFAULT 0,         -- impuesto calculado sobre ajuste
    multa_estimada      INTEGER DEFAULT 0,         -- 50% o 100% del impuesto
    intereses_estimados INTEGER DEFAULT 0,         -- 1% mensual desde omisión
    total_contingencia  INTEGER GENERATED ALWAYS AS
                            (impuesto_omitido + multa_estimada + intereses_estimados) VIRTUAL,
    nivel_riesgo        TEXT DEFAULT 'medio',      -- 'alto' | 'medio' | 'bajo'
    estado              TEXT DEFAULT 'pendiente',  -- 'pendiente' | 'confirmado' | 'descartado' | 'regularizado'
    evidencias          TEXT DEFAULT '[]',         -- JSON array de refs a comprobantes/archivos
    notas_auditor       TEXT,
    creado_por          TEXT DEFAULT 'sistema',    -- 'sistema' | 'auditor'
    creado_en           TEXT DEFAULT (datetime('now')),
    actualizado_en      TEXT DEFAULT (datetime('now'))
);

-- Catálogo de tipos de hallazgo (referencia)
-- IVA_CREDITO_RUC_INACTIVO
-- IVA_CREDITO_SIN_CDC
-- IVA_COMPROBANTE_NO_DECLARADO
-- IVA_DIFERENCIA_RG90_DJ
-- IVA_DEBITO_OMITIDO_HECHAUKA
-- IVA_NOTA_CREDITO_NO_APLICADA
-- IRE_GASTO_NO_DEDUCIBLE
-- IRE_DEPRECIACION_EXCEDIDA
-- IRE_INGRESO_NO_DECLARADO
-- IRE_GASTO_SIN_COMPROBANTE
-- IRE_PARTE_VINCULADA
-- RET_NO_PRACTICADA
-- RET_NO_DEPOSITADA
-- RET_DIFERENCIA_HECHAUKA
-- BANCO_INGRESO_NO_FACTURADO

CREATE INDEX idx_hallazgos_auditoria ON hallazgos(auditoria_id);
CREATE INDEX idx_hallazgos_impuesto ON hallazgos(impuesto, periodo);
CREATE INDEX idx_hallazgos_riesgo ON hallazgos(nivel_riesgo, estado);

-- ============================================================
--  PAPELES DE TRABAJO
-- ============================================================

CREATE TABLE cedulas (
    id                  TEXT PRIMARY KEY,          -- UUID
    auditoria_id        TEXT NOT NULL REFERENCES auditorias(id),
    codigo              TEXT NOT NULL,             -- ej: "IVA-2024-03-A"
    nombre              TEXT NOT NULL,
    impuesto            TEXT NOT NULL,
    periodo             TEXT NOT NULL,
    tipo                TEXT NOT NULL,             -- 'cruce' | 'calculo' | 'conciliacion' | 'resumen'
    datos_json          TEXT NOT NULL,             -- estructura de la cédula
    hallazgos_refs      TEXT DEFAULT '[]',         -- JSON array de IDs de hallazgos
    preparado_por       TEXT DEFAULT 'Inteliaudit',
    revisado_por        TEXT,
    fecha_preparacion   TEXT DEFAULT (datetime('now')),
    UNIQUE(auditoria_id, codigo)
);

-- ============================================================
--  TRAIL DE AUDITORÍA (inmutable)
-- ============================================================

CREATE TABLE audit_trail (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    auditoria_id TEXT REFERENCES auditorias(id),
    timestamp   TEXT DEFAULT (datetime('now')),
    accion      TEXT NOT NULL,
    modulo      TEXT NOT NULL,                     -- 'ingesta' | 'analisis' | 'hallazgos' | 'informes'
    detalle     TEXT,
    datos_json  TEXT,
    resultado   TEXT                               -- 'ok' | 'error' | 'advertencia'
);

-- audit_trail es append-only, sin UPDATE ni DELETE permitidos en producción

-- ============================================================
--  INFORMES GENERADOS
-- ============================================================

CREATE TABLE informes (
    id                  TEXT PRIMARY KEY,          -- UUID
    auditoria_id        TEXT NOT NULL REFERENCES auditorias(id),
    tipo                TEXT NOT NULL,             -- 'auditoria_impositiva' | 'nota_hallazgos' | 'carta_gerencia' | 'due_diligence'
    version             INTEGER DEFAULT 1,
    estado              TEXT DEFAULT 'borrador',   -- 'borrador' | 'final' | 'firmado'
    archivo_docx        TEXT,
    archivo_pdf         TEXT,
    generado_en         TEXT DEFAULT (datetime('now')),
    firmado_en          TEXT,
    firmado_por         TEXT
);

-- ============================================================
--  VISTAS ÚTILES
-- ============================================================

-- Resumen de contingencias por auditoría
CREATE VIEW v_contingencias_resumen AS
SELECT
    h.auditoria_id,
    h.impuesto,
    COUNT(*)                        AS cantidad_hallazgos,
    SUM(h.impuesto_omitido)         AS total_impuesto,
    SUM(h.multa_estimada)           AS total_multa,
    SUM(h.intereses_estimados)      AS total_intereses,
    SUM(h.total_contingencia)       AS total_contingencia,
    SUM(CASE WHEN h.nivel_riesgo = 'alto'  THEN 1 ELSE 0 END) AS hallazgos_alto,
    SUM(CASE WHEN h.nivel_riesgo = 'medio' THEN 1 ELSE 0 END) AS hallazgos_medio,
    SUM(CASE WHEN h.nivel_riesgo = 'bajo'  THEN 1 ELSE 0 END) AS hallazgos_bajo
FROM hallazgos h
WHERE h.estado != 'descartado'
GROUP BY h.auditoria_id, h.impuesto;

-- Comprobantes RG90 con problema
CREATE VIEW v_rg90_problemas AS
SELECT
    r.*,
    CASE
        WHEN r.ruc_activo = 0                          THEN 'RUC inactivo'
        WHEN r.cdc IS NOT NULL AND r.en_sifen = 0      THEN 'CDC no encontrado en SIFEN'
        WHEN r.cdc IS NULL AND r.fecha_emision >= '2022-01-01' THEN 'Sin CDC (posible apócrifo)'
        ELSE 'Sin observaciones'
    END AS problema
FROM rg90 r
WHERE r.ruc_activo = 0
   OR (r.cdc IS NOT NULL AND r.en_sifen = 0)
   OR (r.cdc IS NULL AND r.fecha_emision >= '2022-01-01' AND r.tipo = 'compra');
