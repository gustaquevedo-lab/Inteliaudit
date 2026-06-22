import { useState, useEffect, useMemo } from 'react'
import { Search, ChevronRight, Download } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import { BadgeRiesgo, BadgeEstadoHallazgo, BadgeImpuesto } from '../../components/Badge'
import HallazgoPanel from './HallazgoPanel'
import { pyg, periodo } from '../../utils/formatters'
import type { Hallazgo } from '../../api/types'

// Extended type with client data
interface GlobalHallazgo extends Hallazgo {
  cliente_nombre: string
  cliente_ruc: string
  auditoria_id: string
}

const ESTADOS = ['pendiente', 'revisado', 'aceptado', 'descartado', 'regularizado']
const RIESGOS = ['alto', 'medio', 'bajo']
const IMPUESTOS = ['IVA', 'IRE', 'IRP', 'IDU', 'RET_IVA', 'RET_IRE', 'OTRO']

export default function HallazgosGlobal() {
  const { success, error } = useToast()
  const [hallazgos, setHallazgos] = useState<GlobalHallazgo[]>([])
  const [loading, setLoading] = useState(true)
  const [busqueda, setBusqueda] = useState('')
  const [filtroRiesgo, setFiltroRiesgo] = useState('')
  const [filtroEstado, setFiltroEstado] = useState('')
  const [filtroImpuesto, setFiltroImpuesto] = useState('')
  const [filtroPeriodo, setFiltroPeriodo] = useState('')
  const [seleccionado, setSeleccionado] = useState<GlobalHallazgo | null>(null)

  const load = () => {
    setLoading(true)
    api.get<GlobalHallazgo[]>('/hallazgos')
      .then(setHallazgos)
      .catch(() => error('Error al cargar los hallazgos'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const periodos = useMemo(() => [...new Set(hallazgos.map(h => h.periodo))].sort().reverse(), [hallazgos])

  const filtrados = useMemo(() => hallazgos.filter(h => {
    if (filtroRiesgo && h.nivel_riesgo !== filtroRiesgo) return false
    if (filtroEstado && h.estado !== filtroEstado) return false
    if (filtroImpuesto && h.impuesto !== filtroImpuesto) return false
    if (filtroPeriodo && h.periodo !== filtroPeriodo) return false
    if (busqueda) {
      const q = busqueda.toLowerCase()
      return (
        h.descripcion.toLowerCase().includes(q) || 
        h.tipo_hallazgo.toLowerCase().includes(q) ||
        h.cliente_nombre.toLowerCase().includes(q) ||
        h.cliente_ruc.includes(q)
      )
    }
    return true
  }), [hallazgos, busqueda, filtroRiesgo, filtroEstado, filtroImpuesto, filtroPeriodo])

  const handleUpdated = (updated: Hallazgo) => {
    setHallazgos(prev => prev.map(x => x.id === updated.id ? { ...x, ...updated } : x))
    setSeleccionado(prev => prev && prev.id === updated.id ? { ...prev, ...updated } : prev)
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tight">Hallazgos Globales</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {filtrados.length} hallazgo{filtrados.length !== 1 ? 's' : ''} detectado{filtrados.length !== 1 ? 's' : ''} en la firma
          </p>
        </div>
      </div>

      {/* Toolbar */}
      <div className="card p-4 flex flex-col gap-3">
        <div className="relative">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input className="input-field pl-9 text-sm" placeholder="Buscar por cliente, RUC, tipo o descripción..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
        </div>
        <div className="flex gap-2 flex-wrap">
          <select className="input-field text-sm w-auto flex-1 sm:flex-initial" value={filtroImpuesto} onChange={e => setFiltroImpuesto(e.target.value)}>
            <option value="">Impuesto</option>
            {IMPUESTOS.map(i => <option key={i} value={i}>{i.replace('_',' ')}</option>)}
          </select>
          <select className="input-field text-sm w-auto flex-1 sm:flex-initial" value={filtroRiesgo} onChange={e => setFiltroRiesgo(e.target.value)}>
            <option value="">Riesgo</option>
            {RIESGOS.map(r => <option key={r} value={r} className="capitalize">{r}</option>)}
          </select>
          <select className="input-field text-sm w-auto flex-1 sm:flex-initial" value={filtroEstado} onChange={e => setFiltroEstado(e.target.value)}>
            <option value="">Estado</option>
            {ESTADOS.map(e => <option key={e} value={e} className="capitalize">{e}</option>)}
          </select>
          <select className="input-field text-sm w-auto flex-1 sm:flex-initial" value={filtroPeriodo} onChange={e => setFiltroPeriodo(e.target.value)}>
            <option value="">Periodo</option>
            {periodos.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="table-header">
                <tr>
                  <th className="table-cell">Cliente</th>
                  <th className="table-cell">Impuesto</th>
                  <th className="table-cell">Periodo</th>
                  <th className="table-cell">Tipo / Descripcion</th>
                  <th className="table-cell">Riesgo</th>
                  <th className="table-cell text-right">Contingencia</th>
                  <th className="table-cell">Estado</th>
                  <th className="table-cell"></th>
                </tr>
              </thead>
              <tbody>
                {filtrados.length === 0 ? (
                  <tr><td colSpan={8} className="text-center py-16 text-sm text-gray-400">Sin hallazgos encontrados.</td></tr>
                ) : (
                  filtrados.map((h) => (
                    <tr key={h.id} className={`table-row cursor-pointer ${seleccionado?.id === h.id ? 'bg-primary/5' : ''}`}
                      onClick={() => setSeleccionado(h)}>
                      <td className="table-td">
                        <div>
                          <p className="font-bold text-gray-900 dark:text-white text-xs">{h.cliente_nombre}</p>
                          <p className="text-[10px] text-gray-500 font-mono">{h.cliente_ruc}</p>
                        </div>
                      </td>
                      <td className="table-td"><BadgeImpuesto impuesto={h.impuesto} /></td>
                      <td className="table-td text-xs font-mono text-gray-500">{periodo(h.periodo)}</td>
                      <td className="table-td max-w-[240px]">
                        <p className="text-sm font-bold text-gray-800 dark:text-gray-200 truncate">{h.tipo_hallazgo}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{h.descripcion.slice(0, 80)}{h.descripcion.length > 80 ? '...' : ''}</p>
                      </td>
                      <td className="table-td"><BadgeRiesgo nivel={h.nivel_riesgo} /></td>
                      <td className="table-td text-right font-black text-gray-900 dark:text-white whitespace-nowrap">{pyg(h.total_contingencia)}</td>
                      <td className="table-td"><BadgeEstadoHallazgo estado={h.estado as any} /></td>
                      <td className="table-td"><ChevronRight size={14} className="text-gray-400" /></td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Side panel */}
      {seleccionado && (
        <HallazgoPanel 
          hallazgo={seleccionado} 
          auditoriaId={seleccionado.auditoria_id}
          onClose={() => setSeleccionado(null)} 
          onUpdated={handleUpdated} 
        />
      )}
    </div>
  )
}
