import { useEffect, useState } from 'react'
import { Shield, Clock, User, Layers, CheckCircle, AlertCircle, Search, RefreshCw } from 'lucide-react'
import { api } from '../../api/client'
import { fecha } from '../../utils/formatters'

interface TrailEntry {
  id: string
  timestamp: string
  accion: string
  modulo: string | null
  detalle: string | null
  resultado: string
  auditoria_id: string | null
  usuario_nombre: string
}

const MODULO_COLOR: Record<string, string> = {
  ingesta:      'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300',
  analisis:     'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300',
  informes:     'bg-amber-100 dark:bg-amber-900/30 text-amber-700 dark:text-amber-300',
  hallazgos:    'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300',
  configuracion:'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400',
  auth:         'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300',
}

export default function AuditTrail() {
  const [entries, setEntries] = useState<TrailEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [moduloFiltro, setModuloFiltro] = useState('TODOS')

  const load = () => {
    setLoading(true)
    api.get<TrailEntry[]>('/audit-trail?limit=200')
      .then(setEntries)
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const modulos = ['TODOS', ...Array.from(new Set(entries.map(e => e.modulo ?? 'sistema').filter(Boolean)))]

  const filtered = entries.filter(e => {
    const matchMod = moduloFiltro === 'TODOS' || e.modulo === moduloFiltro
    const matchSearch = !search || e.accion.toLowerCase().includes(search.toLowerCase()) || e.usuario_nombre.toLowerCase().includes(search.toLowerCase())
    return matchMod && matchSearch
  })

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-primary/10 rounded-xl">
            <Shield className="text-primary" size={20} />
          </div>
          <div>
            <h1 className="text-xl font-black text-gray-900 dark:text-white leading-none">Audit Trail</h1>
            <p className="text-[10px] text-gray-500 mt-0.5 uppercase font-bold tracking-wider">Trazabilidad completa de acciones</p>
          </div>
        </div>
        <button onClick={load} className="btn-ghost text-xs flex items-center gap-2">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Actualizar
        </button>
      </div>

      {/* Filtros */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Buscar por acción o usuario..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="input-field pl-9 text-sm py-2 w-full"
          />
        </div>
        <div className="flex bg-gray-100 dark:bg-gray-800 p-1 rounded-xl gap-1">
          {modulos.slice(0, 7).map(m => (
            <button
              key={m}
              onClick={() => setModuloFiltro(m)}
              className={`px-3 py-1.5 text-[10px] font-black rounded-lg transition-all uppercase ${
                moduloFiltro === m
                  ? 'bg-white dark:bg-gray-700 text-primary shadow-sm'
                  : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Stats rápidas */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total acciones', val: entries.length, icon: Layers, color: 'text-primary' },
          { label: 'Hoy', val: entries.filter(e => e.timestamp?.startsWith(new Date().toISOString().slice(0,10))).length, icon: Clock, color: 'text-secondary' },
          { label: 'Errores', val: entries.filter(e => e.resultado === 'error').length, icon: AlertCircle, color: 'text-red-500' },
          { label: 'Exitosas', val: entries.filter(e => e.resultado === 'ok').length, icon: CheckCircle, color: 'text-green-500' },
        ].map(stat => (
          <div key={stat.label} className="card p-4 flex items-center gap-3">
            <stat.icon size={20} className={stat.color} />
            <div>
              <p className="text-[10px] text-gray-400 uppercase font-bold">{stat.label}</p>
              <p className="text-xl font-black text-gray-900 dark:text-white">{stat.val}</p>
            </div>
          </div>
        ))}
      </div>

      {/* Tabla */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="w-8 h-8 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-gray-400 gap-3">
            <Shield size={40} className="opacity-20" />
            <p className="text-sm font-bold uppercase tracking-widest opacity-50">Sin registros</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-800/50">
                <tr>
                  {['Timestamp', 'Módulo', 'Acción', 'Usuario', 'Estado'].map(h => (
                    <th key={h} className="px-4 py-3 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                {filtered.map(e => (
                  <tr key={e.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 font-mono whitespace-nowrap">
                        <Clock size={11} className="shrink-0" />
                        {e.timestamp ? new Date(e.timestamp).toLocaleString('es-PY', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-md text-[10px] font-black uppercase ${MODULO_COLOR[e.modulo ?? ''] ?? 'bg-gray-100 text-gray-500'}`}>
                        {e.modulo ?? 'sistema'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-gray-800 dark:text-gray-200">{e.accion}</p>
                      {e.detalle && <p className="text-xs text-gray-400 mt-0.5 truncate max-w-xs">{e.detalle}</p>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                        <User size={11} />
                        {e.usuario_nombre}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      {e.resultado === 'ok' ? (
                        <span className="flex items-center gap-1 text-[10px] font-bold text-green-600 dark:text-green-400">
                          <CheckCircle size={12} /> OK
                        </span>
                      ) : (
                        <span className="flex items-center gap-1 text-[10px] font-bold text-red-500">
                          <AlertCircle size={12} /> Error
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
