import { useState } from 'react'
import { Plus, Filter, Search, ChevronRight, Zap } from 'lucide-react'
import { api } from '../../../api/client'
import { useToast } from '../../../components/Toaster'
import { BadgeRiesgo, BadgeEstadoHallazgo, BadgeImpuesto } from '../../../components/Badge'
import EmptyState from '../../../components/EmptyState'
import HallazgoPanel from '../HallazgoPanel'
import NuevoHallazgoModal from '../NuevoHallazgoModal'
import { pyg, periodo } from '../../../utils/formatters'
import { ConfirmModal } from '../../../components/Modal'
import type { Hallazgo, NivelRiesgo, EstadoHallazgo, TipoImpuesto } from '../../../api/types'

const ESTADOS: EstadoHallazgo[] = ['pendiente', 'confirmado', 'descartado', 'regularizado']
const RIESGOS: NivelRiesgo[] = ['alto', 'medio', 'bajo']
const IMPUESTOS: TipoImpuesto[] = ['IVA', 'IRE', 'IRP', 'IDU', 'RET_IVA', 'RET_IRE', 'OTRO']

interface Props {
  auditoriaId: string
  hallazgos: Hallazgo[]
  onUpdate: (hallazgos: Hallazgo[]) => void
}

export default function TabHallazgos({ auditoriaId, hallazgos, onUpdate }: Props) {
  const { success, error } = useToast()
  const [busqueda, setBusqueda] = useState('')
  const [filtroRiesgo, setFiltroRiesgo] = useState<string>('')
  const [filtroEstado, setFiltroEstado] = useState<string>('')
  const [filtroImpuesto, setFiltroImpuesto] = useState<string>('')
  const [seleccionado, setSeleccionado] = useState<Hallazgo | null>(null)
  const [showNuevo, setShowNuevo] = useState(false)
  const [analizando, setAnalizando] = useState(false)
  const [confirmAnalisis, setConfirmAnalisis] = useState(false)

  const filtrados = hallazgos.filter(h => {
    if (filtroRiesgo && h.nivel_riesgo !== filtroRiesgo) return false
    if (filtroEstado && h.estado !== filtroEstado) return false
    if (filtroImpuesto && h.impuesto !== filtroImpuesto) return false
    if (busqueda) {
      const q = busqueda.toLowerCase()
      if (!h.descripcion.toLowerCase().includes(q) && !h.tipo_hallazgo.toLowerCase().includes(q)) return false
    }
    return true
  })

  const handleUpdated = (updated: Hallazgo) => {
    const nuevo = hallazgos.map(h => h.id === updated.id ? updated : h)
    onUpdate(nuevo)
    setSeleccionado(updated)
  }

  const handleCreated = (h: Hallazgo) => {
    onUpdate([h, ...hallazgos])
  }

  const ejecutarAnalisis = async () => {
    setAnalizando(true)
    setConfirmAnalisis(false)
    try {
      await api.post(`/auditorias/${auditoriaId}/analizar`)
      // Recargar hallazgos
      const nuevos = await api.get<Hallazgo[]>(`/auditorias/${auditoriaId}/hallazgos`)
      onUpdate(nuevos)
      success('Análisis completado. Revisá los nuevos hallazgos detectados.')
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al ejecutar análisis')
    } finally {
      setAnalizando(false)
    }
  }

  const activos = hallazgos.filter(h => h.estado !== 'descartado')
  const pendientes = activos.filter(h => h.estado === 'pendiente').length

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input className="input-field pl-9 text-sm" placeholder="Buscar hallazgo..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
        </div>
        <div className="flex gap-2 flex-wrap">
          <select className="input-field text-sm w-auto" value={filtroImpuesto} onChange={e => setFiltroImpuesto(e.target.value)}>
            <option value="">Todos los impuestos</option>
            {IMPUESTOS.map(i => <option key={i} value={i}>{i.replace('_',' ')}</option>)}
          </select>
          <select className="input-field text-sm w-auto" value={filtroRiesgo} onChange={e => setFiltroRiesgo(e.target.value)}>
            <option value="">Todos los riesgos</option>
            {RIESGOS.map(r => <option key={r} value={r} className="capitalize">{r}</option>)}
          </select>
          <select className="input-field text-sm w-auto" value={filtroEstado} onChange={e => setFiltroEstado(e.target.value)}>
            <option value="">Todos los estados</option>
            {ESTADOS.map(e => <option key={e} value={e} className="capitalize">{e}</option>)}
          </select>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setConfirmAnalisis(true)} disabled={analizando} className="btn-outline text-sm py-2.5 whitespace-nowrap">
            {analizando
              ? <span className="w-4 h-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
              : <Zap size={15} />}
            Analizar
          </button>
          <button onClick={() => setShowNuevo(true)} className="btn-primary text-sm py-2.5 whitespace-nowrap">
            <Plus size={15} /> Manual
          </button>
        </div>
      </div>

      {/* Summary strip */}
      {pendientes > 0 && (
        <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/30 rounded-xl text-sm">
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          <span className="font-bold text-amber-700 dark:text-amber-400">{pendientes} hallazgo{pendientes > 1 ? 's' : ''} pendiente{pendientes > 1 ? 's' : ''} de revisión</span>
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        {filtrados.length === 0 ? (
          <EmptyState
            title="Sin hallazgos"
            description={busqueda || filtroRiesgo || filtroEstado || filtroImpuesto ? 'Ajustá los filtros para ver resultados' : 'Ejecutá el análisis automático o creá un hallazgo manual'}
            action={
              <div className="flex gap-2">
                <button onClick={() => setConfirmAnalisis(true)} className="btn-outline text-sm py-2">
                  <Zap size={14} /> Analizar datos
                </button>
                <button onClick={() => setShowNuevo(true)} className="btn-primary text-sm py-2">
                  <Plus size={14} /> Nuevo manual
                </button>
              </div>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="table-header">
                <tr>
                  <th className="table-cell">Impuesto</th>
                  <th className="table-cell">Período</th>
                  <th className="table-cell">Tipo</th>
                  <th className="table-cell">Riesgo</th>
                  <th className="table-cell text-right">Contingencia</th>
                  <th className="table-cell">Estado</th>
                  <th className="table-cell"></th>
                </tr>
              </thead>
              <tbody>
                {filtrados.map(h => (
                  <tr
                    key={h.id}
                    className={`table-row ${seleccionado?.id === h.id ? 'bg-primary/5 dark:bg-primary/10' : ''}`}
                    onClick={() => setSeleccionado(h)}
                  >
                    <td className="table-td"><BadgeImpuesto impuesto={h.impuesto} /></td>
                    <td className="table-td text-xs font-mono text-gray-600 dark:text-gray-400">{periodo(h.periodo)}</td>
                    <td className="table-td max-w-[200px]">
                      <p className="text-sm font-bold text-gray-800 dark:text-gray-200 truncate">{h.tipo_hallazgo}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{h.descripcion.slice(0, 60)}{h.descripcion.length > 60 ? '…' : ''}</p>
                    </td>
                    <td className="table-td"><BadgeRiesgo nivel={h.nivel_riesgo} /></td>
                    <td className="table-td text-right font-black text-gray-900 dark:text-white whitespace-nowrap">{pyg(h.total_contingencia)}</td>
                    <td className="table-td"><BadgeEstadoHallazgo estado={h.estado} /></td>
                    <td className="table-td"><ChevronRight size={14} className="text-gray-400" /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Side panel */}
      {seleccionado && (
        <HallazgoPanel
          hallazgo={seleccionado}
          auditoriaId={auditoriaId}
          onClose={() => setSeleccionado(null)}
          onUpdated={handleUpdated}
        />
      )}

      {/* Modals */}
      <NuevoHallazgoModal open={showNuevo} onClose={() => setShowNuevo(false)} auditoriaId={auditoriaId} onCreated={handleCreated} />
      <ConfirmModal
        open={confirmAnalisis}
        onClose={() => setConfirmAnalisis(false)}
        onConfirm={ejecutarAnalisis}
        title="Ejecutar análisis automático"
        message="Se ejecutarán todos los procedimientos de auditoría sobre los datos ingestados. Los hallazgos detectados se agregarán a la lista para tu revisión."
        confirmLabel="Ejecutar análisis"
      />
    </div>
  )
}
