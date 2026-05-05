import { clsx } from 'clsx'
import type { NivelRiesgo, EstadoHallazgo, EstadoAuditoria } from '../api/types'

export function BadgeRiesgo({ nivel }: { nivel: NivelRiesgo }) {
  return (
    <span className={clsx(
      nivel === 'alto' && 'badge-alto',
      nivel === 'medio' && 'badge-medio',
      nivel === 'bajo' && 'badge-bajo',
    )}>
      <span className={clsx(
        'w-1.5 h-1.5 rounded-full',
        nivel === 'alto' && 'bg-red-500',
        nivel === 'medio' && 'bg-amber-500',
        nivel === 'bajo' && 'bg-green-500',
      )} />
      {nivel === 'alto' ? 'Alto' : nivel === 'medio' ? 'Medio' : 'Bajo'}
    </span>
  )
}

export function BadgeEstadoHallazgo({ estado }: { estado: EstadoHallazgo }) {
  const labels: Record<EstadoHallazgo, string> = {
    pendiente: 'Pendiente',
    confirmado: 'Confirmado',
    descartado: 'Descartado',
    regularizado: 'Regularizado',
  }
  return (
    <span className={clsx(
      'badge-gray',
      estado === 'confirmado' && '!bg-blue-50 dark:!bg-blue-900/20 !text-blue-700 dark:!text-blue-400 !border-blue-100 dark:!border-blue-800/30',
      estado === 'descartado' && '!bg-gray-100 dark:!bg-gray-700 !text-gray-500 dark:!text-gray-400',
      estado === 'regularizado' && '!bg-green-50 dark:!bg-green-900/20 !text-green-700 dark:!text-green-400 !border-green-100 dark:!border-green-800/30',
    )}>
      {labels[estado]}
    </span>
  )
}

export function BadgeEstadoAuditoria({ estado }: { estado: EstadoAuditoria }) {
  const map: Record<EstadoAuditoria, { cls: string; label: string }> = {
    borrador:    { cls: 'badge-gray',  label: 'Borrador' },
    en_progreso: { cls: 'badge-info',  label: 'En progreso' },
    revision:    { cls: 'badge-medio', label: 'En revisión' },
    finalizada:  { cls: 'badge-bajo',  label: 'Finalizada' },
    cerrada:     { cls: 'badge-bajo',  label: 'Cerrada' },
    cancelada:   { cls: 'badge-alto',  label: 'Cancelada' },
  }
  const { cls, label } = map[estado] ?? { cls: 'badge-gray', label: estado }
  return <span className={cls}>{label}</span>
}

export function BadgeImpuesto({ impuesto }: { impuesto: string }) {
  const colors: Record<string, string> = {
    IVA: 'bg-purple-50 dark:bg-purple-900/20 text-purple-700 dark:text-purple-400 border-purple-100 dark:border-purple-800/30',
    IRE: 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 border-blue-100 dark:border-blue-800/30',
    IRP: 'bg-cyan-50 dark:bg-cyan-900/20 text-cyan-700 dark:text-cyan-400 border-cyan-100',
    IDU: 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-700 dark:text-indigo-400 border-indigo-100',
    RET_IVA: 'bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400 border-orange-100',
    RET_IRE: 'bg-pink-50 dark:bg-pink-900/20 text-pink-700 dark:text-pink-400 border-pink-100',
  }
  return (
    <span className={clsx(
      'inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-bold border',
      colors[impuesto] ?? 'bg-gray-100 text-gray-600 border-gray-200',
    )}>
      {impuesto.replace('_', ' ')}
    </span>
  )
}
