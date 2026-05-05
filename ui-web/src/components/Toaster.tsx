import { createContext, useContext, useState, useCallback, ReactNode } from 'react'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'

type ToastType = 'success' | 'error' | 'warning' | 'info'

interface Toast {
  id: string
  type: ToastType
  message: string
}

interface ToasterCtx {
  toast: (message: string, type?: ToastType) => void
  success: (message: string) => void
  error: (message: string) => void
  warning: (message: string) => void
}

const Ctx = createContext<ToasterCtx>({
  toast: () => {},
  success: () => {},
  error: () => {},
  warning: () => {},
})

const icons = {
  success: <CheckCircle size={16} className="text-green-500 shrink-0" />,
  error: <XCircle size={16} className="text-red-500 shrink-0" />,
  warning: <AlertTriangle size={16} className="text-amber-500 shrink-0" />,
  info: <Info size={16} className="text-blue-500 shrink-0" />,
}

const colors = {
  success: 'border-green-200 dark:border-green-800/40',
  error: 'border-red-200 dark:border-red-800/40',
  warning: 'border-amber-200 dark:border-amber-800/40',
  info: 'border-blue-200 dark:border-blue-800/40',
}

export function ToasterProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const remove = (id: string) => setToasts(t => t.filter(x => x.id !== id))

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = Math.random().toString(36).slice(2)
    setToasts(t => [...t, { id, type, message }])
    setTimeout(() => remove(id), 4500)
  }, [])

  const success = useCallback((m: string) => toast(m, 'success'), [toast])
  const error = useCallback((m: string) => toast(m, 'error'), [toast])
  const warning = useCallback((m: string) => toast(m, 'warning'), [toast])

  return (
    <Ctx.Provider value={{ toast, success, error, warning }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
        {toasts.map(t => (
          <div
            key={t.id}
            className={`pointer-events-auto flex items-start gap-3 px-4 py-3 rounded-xl
              bg-white dark:bg-slate-800 shadow-lg border ${colors[t.type]}
              animate-fade-in-up max-w-sm`}
          >
            {icons[t.type]}
            <p className="text-sm font-medium text-gray-800 dark:text-gray-200 flex-1">{t.message}</p>
            <button onClick={() => remove(t.id)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  )
}

export const useToast = () => useContext(Ctx)
