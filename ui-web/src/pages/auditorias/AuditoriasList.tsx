import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, FolderSearch, ChevronRight, Plus } from 'lucide-react'
import { api } from '../../api/client'
import EmptyState from '../../components/EmptyState'
import { BadgeEstadoAuditoria } from '../../components/Badge'
import { rangoPeríodos, fecha } from '../../utils/formatters'

interface Auditoria {
  id: string
  cliente_id: string
  cliente_nombre: string
  periodo_desde: string
  periodo_hasta: string
  tipo_encargo: string
  impuestos: string[]
  estado: string
  auditor: string
  fecha_inicio: string
}

export default function AuditoriasList() {
  const navigate = useNavigate()
  const [auditorias, setAuditorias] = useState<Auditoria[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [estadoFilter, setEstadoFilter] = useState('todos')

  const load = () => {
    api.get<Auditoria[]>('/auditorias')
      .then(setAuditorias)
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const filtered = auditorias.filter(a => {
    const matchesSearch = 
      a.cliente_nombre.toLowerCase().includes(search.toLowerCase()) ||
      a.auditor?.toLowerCase().includes(search.toLowerCase())
    
    const matchesEstado = estadoFilter === 'todos' || a.estado === estadoFilter

    return matchesSearch && matchesEstado
  })

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tight">Auditorías</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {auditorias.length} proceso{auditorias.length !== 1 ? 's' : ''} de auditoría
          </p>
        </div>
        <button onClick={() => navigate('/auditorias/nueva')} className="btn-primary self-start">
          <Plus size={16} /> Nueva auditoría
        </button>
      </div>

      {/* Filters */}
      <div className="card p-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="relative sm:col-span-2">
          <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input-field pl-10"
            placeholder="Buscar por cliente o auditor..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div>
          <select 
            className="input-field" 
            value={estadoFilter} 
            onChange={e => setEstadoFilter(e.target.value)}
          >
            <option value="todos">Todos los estados</option>
            <option value="en_progreso">En progreso</option>
            <option value="analizando">Analizando</option>
            <option value="analisis_completado">Análisis completado</option>
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<FolderSearch size={32} />}
            title={search || estadoFilter !== 'todos' ? 'Sin resultados' : 'Sin auditorías aún'}
            description={search || estadoFilter !== 'todos' ? 'Probá con otro término o filtro' : 'Comenzá creando tu primera auditoría'}
            action={!search && estadoFilter === 'todos' ? <button onClick={() => navigate('/auditorias/nueva')} className="btn-primary text-sm py-2">Crear auditoría</button> : undefined}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="table-header">
                <tr>
                  <th className="table-cell">Cliente</th>
                  <th className="table-cell">Período</th>
                  <th className="table-cell">Impuestos</th>
                  <th className="table-cell">Auditor</th>
                  <th className="table-cell">Estado</th>
                  <th className="table-cell">Inicio</th>
                  <th className="table-cell"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(a => (
                  <tr key={a.id} className="table-row" onClick={() => navigate(`/auditorias/${a.id}`)}>
                    <td className="table-td font-bold text-gray-900 dark:text-white">{a.cliente_nombre}</td>
                    <td className="table-td font-mono font-bold text-xs">{rangoPeríodos(a.periodo_desde, a.periodo_hasta)}</td>
                    <td className="table-td">
                      <div className="flex flex-wrap gap-1">
                        {a.impuestos.map(imp => (
                          <span key={imp} className="badge-gray text-[10px]">{imp.replace('_', ' ')}</span>
                        ))}
                      </div>
                    </td>
                    <td className="table-td text-gray-500 dark:text-gray-400 text-xs">{a.auditor ?? '—'}</td>
                    <td className="table-td"><BadgeEstadoAuditoria estado={a.estado as any} /></td>
                    <td className="table-td text-gray-500 text-xs">{fecha(a.fecha_inicio)}</td>
                    <td className="table-td"><ChevronRight size={14} className="text-gray-400" /></td>
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
