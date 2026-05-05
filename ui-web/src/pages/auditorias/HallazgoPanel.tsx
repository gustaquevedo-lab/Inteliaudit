import { useState } from 'react'
import { X, Save, CheckCircle, XCircle, AlertTriangle, FileText } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import { BadgeRiesgo, BadgeEstadoHallazgo, BadgeImpuesto } from '../../components/Badge'
import { pyg, fecha, periodo } from '../../utils/formatters'
import type { Hallazgo } from '../../api/types'

interface HallazgoPanelProps {
  hallazgo: Hallazgo
  auditoriaId: string
  onClose: () => void
  onUpdated: (h: Hallazgo) => void
}

export default function HallazgoPanel({ hallazgo: h, auditoriaId, onClose, onUpdated }: HallazgoPanelProps) {
  const { success, error } = useToast()
  const [notas, setNotas] = useState(h.notas_auditor ?? '')
  const [saving, setSaving] = useState(false)
  const [acting, setActing] = useState(false)

  const patch = async (body: Record<string, unknown>) => {
    const updated = await api.patch<Hallazgo>(`/auditorias/${auditoriaId}/hallazgos/${h.id}`, body)
    onUpdated(updated)
    return updated
  }

  const guardarNotas = async () => {
    setSaving(true)
    try {
      await patch({ notas_auditor: notas })
      success('Notas guardadas')
    } catch { error('Error al guardar notas') }
    finally { setSaving(false) }
  }

  const confirmar = async () => {
    setActing(true)
    try {
      await api.post(`/auditorias/${auditoriaId}/hallazgos/${h.id}/confirmar`, { notas: notas || undefined })
      const updated = await api.get<Hallazgo>(`/auditorias/${auditoriaId}/hallazgos/${h.id}`)
      onUpdated(updated)
      success('Hallazgo confirmado')
    } catch { error('Error al confirmar') }
    finally { setActing(false) }
  }

  const descartar = async () => {
    setActing(true)
    try {
      await api.delete(`/auditorias/${auditoriaId}/hallazgos/${h.id}?motivo=${encodeURIComponent(notas || 'Descartado por el auditor')}`)
      const updated = { ...h, estado: 'descartado' as const }
      onUpdated(updated)
      success('Hallazgo descartado')
    } catch { error('Error al descartar') }
    finally { setActing(false) }
  }

  const riesgoColor = { alto: 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800/30', medio: 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800/30', bajo: 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800/30' }

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/20 dark:bg-black/40 z-30" onClick={onClose} />
      {/* Panel */}
      <div className="side-panel overflow-y-auto">
        {/* Header */}
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 flex items-start gap-3 shrink-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <BadgeImpuesto impuesto={h.impuesto} />
              <BadgeRiesgo nivel={h.nivel_riesgo} />
              <BadgeEstadoHallazgo estado={h.estado} />
            </div>
            <h2 className="text-sm font-black text-gray-900 dark:text-white leading-tight mt-1">{h.tipo_hallazgo}</h2>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{periodo(h.periodo)}</p>
          </div>
          <button onClick={onClose} className="btn-ghost p-1.5 shrink-0"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Contingencia */}
          <div className={`p-4 rounded-2xl border ${riesgoColor[h.nivel_riesgo]}`}>
            <p className="section-label mb-3">Exposición fiscal estimada</p>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Impuesto omitido', value: pyg(h.impuesto_omitido), bold: false },
                { label: 'Multa estimada (50%)', value: pyg(h.multa_estimada), bold: false },
                { label: 'Intereses estimados', value: pyg(h.intereses_estimados), bold: false },
                { label: 'Total contingencia', value: pyg(h.total_contingencia), bold: true },
              ].map(item => (
                <div key={item.label}>
                  <p className="text-[10px] uppercase tracking-wider text-gray-500 dark:text-gray-400">{item.label}</p>
                  <p className={`text-sm mt-0.5 ${item.bold ? 'font-black text-gray-900 dark:text-white' : 'font-bold text-gray-700 dark:text-gray-300'}`}>{item.value}</p>
                </div>
              ))}
            </div>
            {h.base_ajuste > 0 && (
              <div className="mt-3 pt-3 border-t border-current/10">
                <p className="text-[10px] uppercase tracking-wider text-gray-500">Base de ajuste</p>
                <p className="text-sm font-bold text-gray-700 dark:text-gray-300">{pyg(h.base_ajuste)}</p>
              </div>
            )}
          </div>

          {/* Descripción */}
          <div>
            <p className="section-label">Descripción del hallazgo</p>
            <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed">{h.descripcion}</p>
          </div>

          {h.descripcion_tecnica && (
            <div>
              <p className="section-label">Descripción técnica</p>
              <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed font-mono text-xs bg-gray-50 dark:bg-gray-800/50 p-3 rounded-xl">{h.descripcion_tecnica}</p>
            </div>
          )}

          {/* Marco legal */}
          <div className="p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800/30 rounded-xl">
            <p className="section-label text-blue-600 dark:text-blue-400 mb-1">Marco legal aplicable</p>
            <p className="text-sm text-blue-700 dark:text-blue-300 font-medium">{h.articulo_legal}</p>
          </div>

          {/* Meta */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div><p className="text-gray-400">Creado por</p><p className="font-bold text-gray-700 dark:text-gray-300 capitalize">{h.creado_por}</p></div>
            <div><p className="text-gray-400">Fecha</p><p className="font-bold text-gray-700 dark:text-gray-300">{fecha(h.creado_en)}</p></div>
          </div>

          {/* Notas auditor */}
          <div>
            <label className="section-label">Notas del auditor</label>
            <textarea
              className="input-field resize-none text-sm"
              rows={4}
              placeholder="Agregar notas, observaciones o justificaciones..."
              value={notas}
              onChange={e => setNotas(e.target.value)}
              disabled={h.estado === 'descartado'}
            />
            {h.estado !== 'descartado' && (
              <button onClick={guardarNotas} disabled={saving || notas === (h.notas_auditor ?? '')} className="btn-outline text-xs py-1.5 mt-2">
                <Save size={12} /> {saving ? 'Guardando...' : 'Guardar notas'}
              </button>
            )}
          </div>
        </div>

        {/* Actions */}
        {h.estado === 'pendiente' && (
          <div className="p-5 border-t border-gray-100 dark:border-gray-700 flex gap-3 shrink-0">
            <button onClick={descartar} disabled={acting} className="btn-outline flex-1 text-sm py-2.5">
              <XCircle size={15} /> Descartar
            </button>
            <button onClick={confirmar} disabled={acting} className="btn-secondary flex-1 text-sm py-2.5">
              {acting
                ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                : <><CheckCircle size={15} /> Confirmar</>
              }
            </button>
          </div>
        )}
      </div>
    </>
  )
}
