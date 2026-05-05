// ─── Auth ────────────────────────────────────────────────────────────────────
export interface AuthUser {
  id: string
  email: string
  nombre: string
  rol: 'super_admin' | 'admin' | 'auditor_senior' | 'auditor'
  firma_id: string
  firma_nombre: string
  firma_plan: string
  firma_plan_id: string
  en_trial: boolean
  dias_trial_restantes: number
  plan_tiene_ia: boolean
  clientes_actuales: number
  clientes_maximos: number | null
  plan_features: string[]
  avatar_path?: string
  ultimo_acceso?: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user_id: string
  nombre: string
  email: string
  rol: string
  firma_id: string
  firma_nombre: string
}

// ─── Clientes ────────────────────────────────────────────────────────────────
export interface Cliente {
  id: string
  firma_id: string
  ruc: string
  razon_social: string
  nombre_fantasia?: string
  regimen: string
  tipo_contribuyente?: string
  actividad_principal?: string
  estado_dnit: string
  direccion?: string
  email_dnit?: string
  fecha_inscripcion?: string
}

// ─── Auditorías ──────────────────────────────────────────────────────────────
export type EstadoAuditoria = 'borrador' | 'en_progreso' | 'revision' | 'finalizada' | 'cerrada' | 'cancelada'

export interface Tarea {
  id: string
  titulo: string
  descripcion?: string
  categoria: string
  completada: boolean
  fecha_completado?: string
  orden: number
}

export interface Auditoria {
  id: string
  firma_id: string
  cliente_id: string
  periodo_desde: string
  periodo_hasta: string
  tipo_encargo: 'auditoria_anual' | 'devolucion_iva' | 'fiscalizacion' | 'due_diligence'
  impuestos: string[]
  materialidad: number
  estado: EstadoAuditoria
  auditor?: string
  fecha_inicio?: string
  notas?: string
  tareas?: Tarea[]
}

export interface AuditoriaConCliente extends Auditoria {
  cliente?: Cliente
}

// ─── Hallazgos ───────────────────────────────────────────────────────────────
export type NivelRiesgo = 'alto' | 'medio' | 'bajo'
export type EstadoHallazgo = 'pendiente' | 'confirmado' | 'descartado' | 'regularizado'
export type TipoImpuesto = 'IVA' | 'IRE' | 'IRP' | 'IDU' | 'RET_IVA' | 'RET_IRE' | 'OTRO'

export interface Hallazgo {
  id: string
  impuesto: TipoImpuesto
  periodo: string
  tipo_hallazgo: string
  descripcion: string
  descripcion_tecnica?: string
  articulo_legal: string
  base_ajuste: number
  impuesto_omitido: number
  multa_estimada: number
  intereses_estimados: number
  total_contingencia: number
  nivel_riesgo: NivelRiesgo
  estado: EstadoHallazgo
  evidencias: unknown[]
  notas_auditor?: string
  creado_por: string
  creado_en?: string
}

export interface ResumenContingencias {
  total_hallazgos: number
  hallazgos_activos: number
  total_impuesto_omitido: number
  total_multas: number
  total_intereses: number
  total_contingencia: number
  por_impuesto: Record<string, number>
  por_riesgo: { alto: number; medio: number; bajo: number }
}

// ─── Archivos ─────────────────────────────────────────────────────────────────
export interface ArchivoSubido {
  tipo: string
  nombre: string
  tamaño_kb: number
  ruta: string
}

// ─── Informes ────────────────────────────────────────────────────────────────
export interface Informe {
  id: string
  tipo: string
  version: number
  estado: string
  archivo_docx?: string
  archivo_pdf?: string
  generado_en?: string
}

// ─── Usuarios ────────────────────────────────────────────────────────────────
export interface Usuario {
  id: string
  email: string
  nombre: string
  rol: string
  activo: boolean
  creado_en?: string
  ultimo_acceso?: string
}
