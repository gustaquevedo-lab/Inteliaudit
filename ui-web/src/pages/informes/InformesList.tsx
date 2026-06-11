import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { FileText, Download, Loader2, Search, Clock, Calendar, ChevronRight } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import EmptyState from '../../components/EmptyState'


interface InformeGlobal {
  id: string
  auditoria_id: string
  tipo: string
  version: number
  estado: string
  archivo_docx: boolean
  archivo_pdf: boolean
  generado_en: string
  cliente_ruc: string | null
  cliente_razon_social: string | null
  periodo_desde: string | null
  periodo_hasta: string | null
}

const TIPO_LABELS: Record<string, string> = {
  auditoria_completa: 'Auditoría completa',
  carta_gerencia: 'Carta a la gerencia',
  resumen_ejecutivo: 'Resumen ejecutivo',
}

const TIPO_ICONS: Record<string, string> = {
  auditoria_completa: '#2E84F0',
  carta_gerencia: '#22C47E',
  resumen_ejecutivo: '#D97706',
}

export default function InformesList() {
  const navigate = useNavigate()
  const { success, error } = useToast()
  const [informes, setInformes] = useState<InformeGlobal[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [downloads, setDownloads] = useState<Record<string, boolean>>({})
  const [tipoFilter, setTipoFilter] = useState('')

  const load = () =>
    api.get<InformeGlobal[]>('/informes').then(setInformes).finally(() => setLoading(false))

  useEffect(() => { load() }, [])

  const filtered = informes.filter(inf => {
    if (search) {
      const q = search.toLowerCase()
      const matchCliente = (inf.cliente_razon_social ?? '').toLowerCase().includes(q)
      const matchTipo = (TIPO_LABELS[inf.tipo] ?? inf.tipo).toLowerCase().includes(q)
      if (!matchCliente && !matchTipo) return false
    }
    if (tipoFilter && inf.tipo !== tipoFilter) return false
    return true
  })

  const descargar = async (inf: InformeGlobal, fmt: 'docx' | 'pdf') => {
    const key = `${inf.id}-${fmt}`
    setDownloads(d => ({ ...d, [key]: true }))
    try {
      const token = localStorage.getItem('ia_token')
      const res = await fetch(`/api/informes/${inf.id}/descargar/${fmt}`, {
        headers: { Authorization: `Bearer ${token ?? ''}` },
      })
      if (!res.ok) throw new Error('Error al descargar')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = `informe_${inf.tipo}_${inf.cliente_ruc ?? inf.id}.${fmt}`; a.click()
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al descargar')
    }
    setDownloads(d => ({ ...d, [key]: false }))
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tight">Informes</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            {informes.length} informe{informes.length !== 1 ? 's' : ''} generado{informes.length !== 1 ? 's' : ''}
          </p>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400" />
            <input className="input-field pl-10" placeholder="Buscar por cliente o tipo de informe..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="input-field w-auto text-sm" value={tipoFilter} onChange={e => setTipoFilter(e.target.value)}>
            <option value="">Todos los tipos</option>
            <option value="auditoria_completa">Auditoría completa</option>
            <option value="carta_gerencia">Carta a la gerencia</option>
            <option value="resumen_ejecutivo">Resumen ejecutivo</option>
          </select>
        </div>
      </div>

      <div className="card overflow-hidden">
        {loading ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<FileText size={32} />}
            title={search || tipoFilter ? 'Sin resultados' : 'Sin informes aún'}
            description={
              search || tipoFilter
                ? 'Probá con otro término de búsqueda'
                : 'Los informes se generan desde cada auditoría. Andá a Auditorías, entrá en una y usá la pestaña Informes.'
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="table-header">
                <tr>
                  <th className="table-cell">Cliente</th>
                  <th className="table-cell">Tipo</th>
                  <th className="table-cell hidden sm:table-cell">Período</th>
                  <th className="table-cell hidden md:table-cell">Generado</th>
                  <th className="table-cell">Archivos</th>
                  <th className="table-cell"></th>
                </tr>
              </thead>
              <tbody>
                {filtered.map(inf => (
                  <tr key={inf.id} className="table-row" onClick={() => navigate(`/auditorias/${inf.auditoria_id}`)}>
                    <td className="table-td">
                      <div>
                        <p className="font-bold text-gray-900 dark:text-white text-sm">{inf.cliente_razon_social ?? '—'}</p>
                        {inf.cliente_ruc && <p className="text-[11px] font-mono text-gray-500 dark:text-gray-400">{inf.cliente_ruc}</p>}
                      </div>
                    </td>
                    <td className="table-td">
                      <div className="flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: TIPO_ICONS[inf.tipo] ?? '#999' }} />
                        <span className="text-sm font-semibold text-gray-800 dark:text-gray-200 capitalize">
                          {TIPO_LABELS[inf.tipo] ?? inf.tipo.replace(/_/g, ' ')}
                        </span>
                        {inf.version > 1 && <span className="badge-gray text-[10px]">v{inf.version}</span>}
                      </div>
                    </td>
                    <td className="table-td hidden sm:table-cell">
                      {inf.periodo_desde && inf.periodo_hasta ? (
                        <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                          <Calendar size={11} /> {inf.periodo_desde} → {inf.periodo_hasta}
                        </span>
                      ) : <span className="text-xs text-gray-400">—</span>}
                    </td>
                    <td className="table-td hidden md:table-cell">
                      <span className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                        <Clock size={11} /> {inf.generado_en ? new Date(inf.generado_en).toLocaleDateString('es-PY', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                      </span>
                    </td>
                    <td className="table-td">
                      <div className="flex gap-1.5" onClick={e => e.stopPropagation()}>
                        {inf.archivo_docx && (
                          <button onClick={() => descargar(inf, 'docx')} disabled={downloads[`${inf.id}-docx`]}
                            className="btn-outline text-[11px] py-1 px-2.5 flex items-center gap-1">
                            {downloads[`${inf.id}-docx`] ? <Loader2 size={10} className="animate-spin" /> : <FileText size={11} />}
                            DOCX
                          </button>
                        )}
                        {inf.archivo_pdf && (
                          <button onClick={() => descargar(inf, 'pdf')} disabled={downloads[`${inf.id}-pdf`]}
                            className="btn-outline text-[11px] py-1 px-2.5 flex items-center gap-1">
                            {downloads[`${inf.id}-pdf`] ? <Loader2 size={10} className="animate-spin" /> : <Download size={11} />}
                            PDF
                          </button>
                        )}
                        {!inf.archivo_docx && !inf.archivo_pdf && (
                          <span className="text-[11px] text-gray-400 italic">Sin archivos</span>
                        )}
                      </div>
                    </td>
                    <td className="table-td">
                      <ChevronRight size={14} className="text-gray-400" />
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
