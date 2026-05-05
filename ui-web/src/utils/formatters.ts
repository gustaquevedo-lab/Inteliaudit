/** Formatea guaraníes: 1500000 → "₲ 1.500.000" */
export function pyg(amount: number): string {
  return `₲ ${amount.toLocaleString('es-PY')}`
}

/** Formatea período YYYY-MM → "Mar 2024" */
export function periodo(p: string): string {
  if (!p || p.length < 7) return p
  const [year, month] = p.split('-')
  const date = new Date(Number(year), Number(month) - 1)
  return date.toLocaleDateString('es-PY', { month: 'short', year: 'numeric' })
}

/** Rango de períodos */
export function rangoPeríodos(desde: string, hasta: string): string {
  return `${periodo(desde)} — ${periodo(hasta)}`
}

/** Fecha ISO → "15 mar 2024" */
export function fecha(iso: string | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('es-PY', { day: '2-digit', month: 'short', year: 'numeric' })
}

/** Fecha ISO → "15/03/2024 10:30" */
export function fechaHora(iso: string | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('es-PY', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

/** Etiqueta de nivel de riesgo */
export function labelRiesgo(r: string): string {
  return { alto: 'Alto', medio: 'Medio', bajo: 'Bajo' }[r] ?? r
}

/** Etiqueta de estado de hallazgo */
export function labelEstado(e: string): string {
  return {
    pendiente: 'Pendiente',
    confirmado: 'Confirmado',
    descartado: 'Descartado',
    regularizado: 'Regularizado',
  }[e] ?? e
}

/** Etiqueta de estado de auditoría */
export function labelEstadoAuditoria(e: string): string {
  return {
    en_progreso: 'En progreso',
    revision: 'En revisión',
    cerrada: 'Cerrada',
  }[e] ?? e
}

/** Etiqueta de rol */
export function labelRol(r: string): string {
  return {
    super_admin: 'Super Admin',
    admin: 'Administrador',
    auditor_senior: 'Auditor Senior',
    auditor: 'Auditor',
  }[r] ?? r
}

/** Abreviatura de impuesto */
export function labelImpuesto(i: string): string {
  return {
    IVA: 'IVA', IRE: 'IRE', IRP: 'IRP', IDU: 'IDU',
    RET_IVA: 'Ret. IVA', RET_IRE: 'Ret. IRE', OTRO: 'Otro',
  }[i] ?? i
}

/** Tamaño en KB/MB legible */
export function fileSize(kb: number): string {
  if (kb < 1024) return `${kb.toFixed(0)} KB`
  return `${(kb / 1024).toFixed(1)} MB`
}

/** Iniciales del nombre */
export function initials(nombre: string): string {
  return nombre.split(' ').slice(0, 2).map(w => w[0]).join('').toUpperCase()
}
