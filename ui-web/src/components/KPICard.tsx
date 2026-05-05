import { ReactNode } from 'react'
import { clsx } from 'clsx'

interface KPICardProps {
  label: string
  value: string | number
  icon: ReactNode
  iconBg?: string
  trend?: { value: string; positive: boolean }
  subtitle?: string
  onClick?: () => void
}

export default function KPICard({ label, value, icon, iconBg = 'bg-primary/10', trend, subtitle, onClick }: KPICardProps) {
  return (
    <div
      className={clsx(
        'card card-hover p-5 flex items-start gap-4',
        onClick && 'cursor-pointer'
      )}
      onClick={onClick}
    >
      <div className={clsx('p-3 rounded-2xl shrink-0', iconBg)}>
        {icon}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-black uppercase tracking-widest text-gray-400 dark:text-gray-500 mb-1">{label}</p>
        <p className="text-2xl font-black text-gray-900 dark:text-white leading-none truncate">{value}</p>
        {subtitle && <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 truncate">{subtitle}</p>}
        {trend && (
          <p className={clsx('text-xs font-bold mt-1.5', trend.positive ? 'text-green-600 dark:text-green-400' : 'text-red-500 dark:text-red-400')}>
            {trend.positive ? '▲' : '▼'} {trend.value}
          </p>
        )}
      </div>
    </div>
  )
}
