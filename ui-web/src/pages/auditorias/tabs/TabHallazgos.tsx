import { useState, useMemo, useCallback } from 'react'
import { Filter, Search, ChevronRight, Download, CheckSquare, Square, XCircle, CheckCircle, Clock } from 'lucide-react'
import { api } from '../../../api/client'
import { useToast } from '../../../components/Toaster'
import { BadgeRiesgo, BadgeEstadoHallazgo, BadgeImpuesto } from '../../../components/Badge'
import { ConfirmModal } from '../../../components/Modal'
import HallazgoPanel from '../HallazgoPanel'
import { pyg, periodo } from '../../../utils/formatters'
import type { Hallazgo } from '../../../api/types'

const ESTADOS = ['pendiente', 'revisado', 'aceptado', 'descartado', 'regularizado']
const RIESGOS = ['alto', 'medio', 'bajo']
const IMPUESTOS = ['IVA', 'IRE', 'IRP', 'IDU', 'RET_IVA', 'RET_IRE', 'OTRO']

interface Props { auditoriaId: string; hallazgos: Hallazgo[]; onUpdate: (h: Hallazgo[]) => void }

export default function TabHallazgos({ auditoriaId, hallazgos, onUpdate }: Props) {
  const { success, error } = useToast()
  const [busqueda, setBusqueda] = useState('')
  const [filtroRiesgo, setFiltroRiesgo] = useState('')
  const [filtroEstado, setFiltroEstado] = useState('')
  const [filtroImpuesto, setFiltroImpuesto] = useState('')
  const [filtroPeriodo, setFiltroPeriodo] = useState('')
  const [seleccionado, setSeleccionado] = useState<Hallazgo | null>(null)
  const [seleccionados, setSeleccionados] = useState<Set<string>>(new Set())
  const [batchEstado, setBatchEstado] = useState('')
  const [confirmBatch, setConfirmBatch] = useState(false)
  const [batchLoading, setBatchLoading] = useState(false)

  const periodos = useMemo(() => [...new Set(hallazgos.map(h => h.periodo))].sort().reverse(), [hallazgos])

  const filtrados = useMemo(() => hallazgos.filter(h => {
    if (filtroRiesgo && h.nivel_riesgo !== filtroRiesgo) return false
    if (filtroEstado && h.estado !== filtroEstado) return false
    if (filtroImpuesto && h.impuesto !== filtroImpuesto) return false
    if (filtroPeriodo && h.periodo !== filtroPeriodo) return false
    if (busqueda) {
      const q = busqueda.toLowerCase()
      return h.descripcion.toLowerCase().includes(q) || h.tipo_hallazgo.toLowerCase().includes(q)
    }
    return true
  }), [hallazgos, busqueda, filtroRiesgo, filtroEstado, filtroImpuesto, filtroPeriodo])

  const toggleSelect = (id: string) => {
    setSeleccionados(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const toggleAll = () => {
    if (seleccionados.size === filtrados.length) setSeleccionados(new Set())
    else setSeleccionados(new Set(filtrados.map(h => h.id)))
  }

  const ejecutarBatch = useCallback(async () => {
    if (!batchEstado || seleccionados.size === 0) return
    setBatchLoading(true)
    try {
      await api.post(`/auditorias/${auditoriaId}/hallazgos/estado-batch`, {
        ids: Array.from(seleccionados), estado: batchEstado,
      })
      const nuevos = await api.get<Hallazgo[]>(`/auditorias/${auditoriaId}/hallazgos`)
      onUpdate(nuevos)
      setSeleccionados(new Set())
      setConfirmBatch(false)
      success(`${seleccionados.size} hallazgos actualizados a "${batchEstado}"`)
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error batch')
    }
    setBatchLoading(false)
  }, [batchEstado, seleccionados, auditoriaId, onUpdate, success, error])

  const exportExcel = async () => {
    const params = new URLSearchParams()
    if (filtroImpuesto) params.set('impuesto', filtroImpuesto)
    if (filtroEstado) params.set('estado', filtroEstado)
    if (filtroRiesgo) params.set('nivel_riesgo', filtroRiesgo)
    if (filtroPeriodo) params.set('periodo', filtroPeriodo)
    try {
      const blob = await api.postBlob(`/auditorias/${auditoriaId}/hallazgos/export-excel?${params.toString()}`)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `hallazgos_${auditoriaId.slice(0, 8)}.xlsx`; a.click()
      URL.revokeObjectURL(url)
      success('Excel exportado')
    } catch { error('Error al exportar') }
  }

  const handleUpdated = (h: Hallazgo) => {
    onUpdate(hallazgos.map(x => x.id === h.id ? h : x))
    setSeleccionado(h)
  }

  const pendientes = hallazgos.filter(h => h.estado === 'pendiente').length
  const hasSeleccion = seleccionados.size > 0

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
        <div className="relative flex-1">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input className="input-field pl-9 text-sm" placeholder="Buscar hallazgo..." value={busqueda} onChange={e => setBusqueda(e.target.value)} />
        </div>
        <div className="flex gap-2 flex-wrap">
          <select className="input-field text-sm w-auto" value={filtroImpuesto} onChange={e => setFiltroImpuesto(e.target.value)}>
            <option value="">Impuesto</option>
            {IMPUESTOS.map(i => <option key={i} value={i}>{i.replace('_',' ')}</option>)}
          </select>
          <select className="input-field text-sm w-auto" value={filtroRiesgo} onChange={e => setFiltroRiesgo(e.target.value)}>
            <option value="">Riesgo</option>
            {RIESGOS.map(r => <option key={r} value={r} className="capitalize">{r}</option>)}
          </select>
          <select className="input-field text-sm w-auto" value={filtroEstado} onChange={e => setFiltroEstado(e.target.value)}>
            <option value="">Estado</option>
            {ESTADOS.map(e => <option key={e} value={e} className="capitalize">{e}</option>)}
          </select>
          <select className="input-field text-sm w-auto" value={filtroPeriodo} onChange={e => setFiltroPeriodo(e.target.value)}>
            <option value="">Periodo</option>
            {periodos.map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          <button onClick={exportExcel} className="btn-outline text-sm py-2.5"><Download size={14} /> Exportar</button>
        </div>
      </div>

      {/* Batch actions bar */}
      {hasSeleccion && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-primary/5 border border-primary/20">
          <CheckCircle size={16} className="text-primary" />
          <span className="text-xs font-bold text-gray-700 dark:text-gray-300">{seleccionados.size} seleccionado{seleccionados.size > 1 ? 's' : ''}</span>
          <div className="flex items-center gap-2 ml-auto">
            <select className="input-field text-xs py-1.5 w-auto" value={batchEstado} onChange={e => setBatchEstado(e.target.value)}>
              <option value="">Cambiar estado...</option>
              <option value="revisado">Revisado</option>
              <option value="aceptado">Aceptado</option>
              <option value="descartado">Descartado</option>
            </select>
            <button onClick={() => setConfirmBatch(true)} disabled={!batchEstado} className="btn-primary text-xs py-1.5 px-3">
              Aplicar
            </button>
            <button onClick={() => setSeleccionados(new Set())} className="btn-ghost text-xs py-1.5 px-2">
              <XCircle size={14} />
            </button>
          </div>
        </div>
      )}

      {/* Summary */}
      {pendientes > 0 && !hasSeleccion && (
        <div className="flex items-center gap-2 px-4 py-2.5 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/30 rounded-xl text-sm">
          <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
          <span className="font-bold text-amber-700 dark:text-amber-400">{pendientes} hallazgo{pendientes > 1 ? 's' : ''} pendiente{pendientes > 1 ? 's' : ''}</span>
        </div>
      )}

      {/* Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="table-header">
              <tr>
                <th className="table-cell w-10">
                  <button onClick={toggleAll} className="p-1">
                    {seleccionados.size === filtrados.length && filtrados.length > 0
                      ? <CheckSquare size={14} className="text-primary" />
                      : <Square size={14} className="text-gray-400" />}
                  </button>
                </th>
                <th className="table-cell w-8 text-[10px] text-gray-400">#</th>
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
                <tr><td colSpan={9} className="text-center py-16 text-sm text-gray-400">Sin hallazgos. Ajusta los filtros o ejecuta un analisis.</td></tr>
              ) : filtrados.map((h, i) => (
                <tr key={h.id} className={`table-row cursor-pointer ${seleccionado?.id === h.id ? 'bg-primary/5' : ''}`}
                  onClick={() => setSeleccionado(h)}>
                  <td className="table-td" onClick={e => e.stopPropagation()}>
                    <button onClick={() => toggleSelect(h.id)} className="p-1">
                      {seleccionados.has(h.id) ? <CheckSquare size={14} className="text-primary" /> : <Square size={14} className="text-gray-300" />}
                    </button>
                  </td>
                  <td className="table-td text-[10px] text-gray-400 font-mono">{i + 1}</td>
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
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Side panel */}
      {seleccionado && (
        <HallazgoPanel hallazgo={seleccionado} auditoriaId={auditoriaId}
          onClose={() => setSeleccionado(null)} onUpdated={handleUpdated} />
      )}

      {/* Batch confirm modal */}
      <ConfirmModal open={confirmBatch} onClose={() => setConfirmBatch(false)}
        onConfirm={ejecutarBatch} loading={batchLoading}
        title={`Cambiar estado a "${batchEstado}"`}
        message={`Se actualizaran ${seleccionados.size} hallazgo${seleccionados.size > 1 ? 's' : ''} al estado "${batchEstado}".`}
        confirmLabel="Aplicar cambios" />
    </div>
  )
}
