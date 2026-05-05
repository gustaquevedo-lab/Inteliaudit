-- ============================================================
--  Inteliaudit SaaS — Schema SQL (PostgreSQL)
--  Arquitectura Multi-tenant Centralizada
-- ============================================================

-- Extensiones recomendadas para PostgreSQL
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
--  USUARIOS (CONTADORES / AUDITORES)
-- ============================================================

CREATE TABLE usuarios (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email               TEXT UNIQUE NOT NULL,
    password_hash       TEXT NOT NULL,
    nombre              TEXT NOT NULL,
    ruc_contador        TEXT UNIQUE,               -- RUC personal del contador
    registro_profesional TEXT,                     -- Matrícula profesional
    cargo               TEXT DEFAULT 'auditor',    -- 'admin' | 'auditor' | 'junior'
    estado              TEXT DEFAULT 'activo',     -- 'activo' | 'suspendido' | 'pendiente'
    suscripcion_plan    TEXT DEFAULT 'free',       -- 'free' | 'pro' | 'enterprise'
    config_json         JSONB DEFAULT '{}',        -- Preferencias de UI, firmas, etc.
    ultimo_login        TIMESTAMPTZ,
    creado_en           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
--  CLIENTES / CONTRIBUYENTES (Aislados por usuario)
-- ============================================================

CREATE TABLE clientes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id          UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    ruc                 TEXT NOT NULL,             -- ej: "80012345-6"
    razon_social        TEXT NOT NULL,
    nombre_fantasia     TEXT,
    actividad_principal TEXT,
    regimen             TEXT NOT NULL,             -- 'general' | 'simplificado' | 'pequeno'
    tipo_contribuyente  TEXT,                      -- 'empresa' | 'unipersonal' | 'persona_fisica'
    direccion           TEXT,
    email_set           TEXT,
    clave_marangatu     TEXT,                      -- CIFRADA
    estado_set          TEXT DEFAULT 'activo',
    fecha_inscripcion   DATE,
    creado_en           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    
    -- Un usuario no puede tener dos veces el mismo RUC de cliente
    UNIQUE(usuario_id, ruc)
);

CREATE INDEX idx_clientes_usuario ON clientes(usuario_id);
CREATE INDEX idx_clientes_ruc ON clientes(ruc);

-- ============================================================
--  AUDITORÍAS
-- ============================================================

CREATE TABLE auditorias (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id          UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    cliente_id          UUID NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    periodo_desde       TEXT NOT NULL,             -- YYYY-MM
    periodo_hasta       TEXT NOT NULL,             -- YYYY-MM
    impuestos           JSONB NOT NULL,            -- ["IVA", "IRE"]
    materialidad        BIGINT DEFAULT 0,          -- PYG
    estado              TEXT DEFAULT 'en_progreso',-- 'en_progreso' | 'revision' | 'cerrada'
    auditor_asignado    TEXT,                      -- Nombre del responsable
    fecha_inicio        TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    fecha_cierre        TIMESTAMPTZ,
    notas               TEXT,
    creado_en           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_auditorias_usuario ON auditorias(usuario_id);
CREATE INDEX idx_auditorias_cliente ON auditorias(cliente_id);

-- ============================================================
--  DECLARACIONES JURADAS
-- ============================================================

CREATE TABLE declaraciones (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id          UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    auditoria_id        UUID REFERENCES auditorias(id) ON DELETE SET NULL,
    cliente_id          UUID NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    formulario          TEXT NOT NULL,             -- '120', '500', etc.
    periodo             TEXT NOT NULL,             -- YYYY-MM
    fecha_presentacion  TIMESTAMPTZ NOT NULL,
    estado_declaracion  TEXT NOT NULL,             -- 'original' | 'rectificativa'
    nro_rectificativa   INTEGER DEFAULT 0,
    datos_json          JSONB NOT NULL,
    archivo_pdf_url     TEXT,                      -- URL a S3/Storage
    creado_en           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
--  RG 90 — Detalle Comprobantes
-- ============================================================

CREATE TABLE rg90 (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id          UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    auditoria_id        UUID REFERENCES auditorias(id) ON DELETE SET NULL,
    cliente_id          UUID NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
    periodo             TEXT NOT NULL,
    tipo                TEXT NOT NULL,             -- 'compra' | 'venta'
    ruc_contraparte     TEXT NOT NULL,
    nombre_contraparte  TEXT,
    timbrado            TEXT,
    nro_comprobante     TEXT NOT NULL,
    cdc                 TEXT,                      -- 44 dígitos
    tipo_comprobante    TEXT,                      -- '1', '4', '5', '6'
    fecha_emision       DATE NOT NULL,
    base_10             BIGINT DEFAULT 0,
    base_5              BIGINT DEFAULT 0,
    exento              BIGINT DEFAULT 0,
    iva_10              BIGINT DEFAULT 0,
    iva_5               BIGINT DEFAULT 0,
    iva_total           BIGINT DEFAULT 0,
    total               BIGINT DEFAULT 0,
    
    -- Validaciones
    cdc_valido          BOOLEAN,
    ruc_activo          BOOLEAN,
    en_sifen            BOOLEAN,
    
    creado_en           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rg90_usuario_periodo ON rg90(usuario_id, periodo);
CREATE INDEX idx_rg90_cdc ON rg90(cdc) WHERE cdc IS NOT NULL;

-- ============================================================
--  HALLAZGOS (El "Core" del valor)
-- ============================================================

CREATE TABLE hallazgos (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id          UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    auditoria_id        UUID NOT NULL REFERENCES auditorias(id) ON DELETE CASCADE,
    impuesto            TEXT NOT NULL,
    periodo             TEXT NOT NULL,
    tipo_hallazgo       TEXT NOT NULL,
    descripcion         TEXT NOT NULL,
    articulo_legal      TEXT,
    impuesto_omitido    BIGINT DEFAULT 0,
    multa_estimada      BIGINT DEFAULT 0,
    intereses_estimados BIGINT DEFAULT 0,
    nivel_riesgo        TEXT DEFAULT 'medio',      -- 'alto' | 'medio' | 'bajo'
    estado              TEXT DEFAULT 'pendiente',  -- 'pendiente' | 'confirmado' | 'descartado'
    evidencias_json     JSONB DEFAULT '[]',        -- [{tipo: 'cdc', ref: '...'}, {tipo: 'pdf', page: 1}]
    notas_auditor       TEXT,
    creado_en           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    actualizado_en      TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
--  TRAIL DE AUDITORÍA (Logs inmutables del sistema)
-- ============================================================

CREATE TABLE audit_trail (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id          UUID REFERENCES usuarios(id),
    auditoria_id        UUID REFERENCES auditorias(id),
    accion              TEXT NOT NULL,
    modulo              TEXT NOT NULL,
    detalle             TEXT,
    ip_address          TEXT,
    creado_en           TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
--  DISPARADORES (Triggers) para actualizado_en
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.actualizado_en = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_usuarios_updated_at BEFORE UPDATE ON usuarios FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_clientes_updated_at BEFORE UPDATE ON clientes FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
CREATE TRIGGER update_hallazgos_updated_at BEFORE UPDATE ON hallazgos FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
