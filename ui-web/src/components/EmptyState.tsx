import { ReactNode } from 'react'
import { FolderOpen } from 'lucide-react'

interface EmptyStateProps {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}

export default function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="p-4 bg-gray-100 dark:bg-gray-800 rounded-2xl mb-4 text-gray-400 dark:text-gray-500">
        {icon ?? <FolderOpen size={32} />}
      </div>
      <h3 className="text-base font-black text-gray-700 dark:text-gray-300 uppercase tracking-tight mb-1">{title}</h3>
      {description && <p className="text-sm text-gray-500 dark:text-gray-400 max-w-xs mb-4">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  )
}
