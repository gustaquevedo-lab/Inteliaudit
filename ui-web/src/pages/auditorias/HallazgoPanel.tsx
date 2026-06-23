import { useState, useEffect } from 'react'
import { X, Save, CheckCircle, XCircle, AlertTriangle, FileText, ExternalLink, History, Sparkles, Lock, Loader2 } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import { useAuth } from '../../context/AuthContext'
import { BadgeRiesgo, BadgeEstadoHallazgo, BadgeImpuesto } from '../../components/Badge'
import { ConfirmModal } from '../../components/Modal'
import { pyg, fecha, periodo } from '../../utils/formatters'
import type { Hallazgo } from '../../api/types'

interface HallazgoPanelProps {
  hallazgo: Hallazgo
  auditoriaId: string
  onClose: () => void
  onUpdated: (h: Hallazgo) => void
}

const ESTADOS_SIGUIENTES: Record<string, { label: string; action: string; icon: any; color: string }[]> = {
  pendiente: [{ label: 'Marcar como revisado', action: 'revisado', icon: CheckCircle, color: 'btn-primary' }],
  revisado: [
    { label: 'Aceptar hallazgo', action: 'aceptado', icon: CheckCircle, color: 'btn-primary' },
    { label: 'Descartar', action: 'descartado', icon: XCircle, color: 'btn-danger' },
  ],
  aceptado: [{ label: 'Marcar regularizado', action: 'regularizado', icon: CheckCircle, color: 'btn-secondary' }],
  descartado: [{ label: 'Reabrir hallazgo', action: 'revisado', icon: CheckCircle, color: 'btn-outline' }],
  regularizado: [],
}

export default function HallazgoPanel({ hallazgo: h, auditoriaId, onClose, onUpdated }: HallazgoPanelProps) {
  const { user } = useAuth()
  const { success, error } = useToast()
  const [notas, setNotas] = useState(h.notas_auditor ?? '')
  const [editDesc, setEditDesc] = useState(h.descripcion)
  const [editBase, setEditBase] = useState(String(h.base_ajuste))
  const [editImpuesto, setEditImpuesto] = useState(String(h.impuesto_omitido))
  const [editRiesgo, setEditRiesgo] = useState(h.nivel_riesgo)
  const [editando, setEditando] = useState(false)
  const [saving, setSaving] = useState(false)
  const [confirmAction, setConfirmAction] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [trail, setTrail] = useState<any[]>([])
  const [showTrail, setShowTrail] = useState(false)
  const [nuevaEvidencia, setNuevaEvidencia] = useState('')
  const [evidencias, setEvidencias] = useState<any[]>(h.evidencias || [])
  const [generandoNarrativa, setGenerandoNarrativa] = useState(false)
  const [usoSuggestions, setUsoSuggestions] = useState(false)

  const puedeEditar = user?.rol === 'admin' || user?.rol === 'super_admin' || user?.rol === 'auditor_senior'

  useEffect(() => {
    api.get<any[]>(`/auditorias/${auditoriaId}/hallazgos/${h.id}/trail`).then(setTrail).catch(() => {})
  }, [auditoriaId, h.id])

  const guardar = async () => {
    setSaving(true)
    try {
      const body: Record<string, unknown> = { notas_auditor: notas }
      if (editando) {
        body.descripcion = editDesc
        body.base_ajuste = parseInt(editBase) || 0
        body.impuesto_omitido = parseInt(editImpuesto) || 0
        body.nivel_riesgo = editRiesgo
      }
      const updated = await api.patch<Hallazgo>(`/auditorias/${auditoriaId}/hallazgos/${h.id}`, body)
      onUpdated(updated)
      success('Guardado')
      setEditando(false)
    } catch { error('Error al guardar') }
    setSaving(false)
  }

  const cambiarEstado = async () => {
    if (!confirmAction) return
    setActionLoading(true)
    try {
      const res = await api.patch<{ ok: boolean; advertencia?: string }>(
        `/auditorias/${auditoriaId}/hallazgos/${h.id}/estado`,
        { estado: confirmAction, notas_auditor: notas || undefined }
      )
      const updated = await api.get<Hallazgo>(`/auditorias/${auditoriaId}/hallazgos/${h.id}`)
      onUpdated(updated)
      success(`Hallazgo ${confirmAction}`)
      if (res.advertencia) error(res.advertencia)
      setConfirmAction(null)
    } catch (e: unknown) { error(e instanceof Error ? e.message : 'Error') }
    setActionLoading(false)
  }

  const agregarEvidencia = async () => {
    if (!nuevaEvidencia.trim()) return
    try {
      const res = await api.post<{ ok: boolean; evidencias: any[] }>(
        `/auditorias/${auditoriaId}/hallazgos/${h.id}/evidencias`,
        { tipo: 'rg90', referencia_id: nuevaEvidencia.trim(), descripcion: '' }
      )
      setEvidencias(res.evidencias)
      setNuevaEvidencia('')
      success('Evidencia vinculada')
    } catch (e: unknown) { error(e instanceof Error ? e.message : 'Error') }
  }

  const accs = ESTADOS_SIGUIENTES[h.estado] || []
  const riesgoColor = {
    alto: 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800/30',
    medio: 'bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800/30',
    bajo: 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800/30',
  }

  return (
    <>
      <div className="fixed inset-0 bg-black/20 dark:bg-black/40 z-30" onClick={onClose} />
      <div className="side-panel overflow-y-auto">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700 flex items-start gap-3 shrink-0">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-1">
              <BadgeImpuesto impuesto={h.impuesto} />
              <BadgeRiesgo nivel={h.nivel_riesgo} />
              <BadgeEstadoHallazgo estado={h.estado as any} />
            </div>
            <h2 className="text-sm font-black text-gray-900 dark:text-white leading-tight mt-1">{h.tipo_hallazgo}</h2>
            <p className="text-xs text-gray-500 mt-0.5">{periodo(h.periodo)}</p>
          </div>
          <button onClick={onClose} className="btn-ghost p-1.5 shrink-0"><X size={18} /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* Contingencia */}
          <div className={`p-4 rounded-2xl border ${riesgoColor[h.nivel_riesgo]}`}>
            <p className="section-label mb-3">Exposicion fiscal estimada</p>
            <div className="grid grid-cols-2 gap-3">
              {[
                { label: 'Base de ajuste', value: pyg(h.base_ajuste), bold: false, editField: 'base_ajuste' },
                { label: 'Impuesto omitido', value: pyg(h.impuesto_omitido), bold: false },
                { label: 'Multa (50%)', value: pyg(h.multa_estimada), bold: false },
                { label: 'Intereses (1%/mes)', value: pyg(h.intereses_estimados), bold: false },
                { label: 'Total contingencia', value: pyg(h.total_contingencia), bold: true },
              ].map(item => (
                <div key={item.label}>
                  <p className="text-[10px] uppercase tracking-wider text-gray-500">{item.label}</p>
                  <p className={`text-sm mt-0.5 ${item.bold ? 'font-black text-gray-900 dark:text-white' : 'font-bold text-gray-700 dark:text-gray-300'}`}>{item.value}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Descripcion editable */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <p className="section-label mb-0">Descripcion del hallazgo</p>
              {puedeEditar && !editando && (
                <button onClick={() => setEditando(true)} className="text-[10px] font-bold text-primary uppercase">Editar</button>
              )}
            </div>
            {editando ? (
              <textarea className="input-field text-sm resize-none" rows={3} value={editDesc} onChange={e => setEditDesc(e.target.value)} />
            ) : (
              <p className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-line">{h.descripcion}</p>
            )}

            {editando && (
              <div className="grid grid-cols-3 gap-3 mt-3">
                <div>
                  <label className="text-[10px] font-bold text-gray-500 uppercase">Base ajuste</label>
                  <input className="input-field text-sm" value={editBase} onChange={e => setEditBase(e.target.value)} />
                </div>
                <div>
                  <label className="text-[10px] font-bold text-gray-500 uppercase">Impuesto omitido</label>
                  <input className="input-field text-sm" value={editImpuesto} onChange={e => setEditImpuesto(e.target.value)} />
                </div>
                <div>
                  <label className="text-[10px] font-bold text-gray-500 uppercase">Riesgo</label>
                  <select className="input-field text-sm" value={editRiesgo} onChange={e => setEditRiesgo(e.target.value as 'alto' | 'medio' | 'bajo')}>
                    <option value="alto">Alto</option>
                    <option value="medio">Medio</option>
                    <option value="bajo">Bajo</option>
                  </select>
                </div>
              </div>
            )}
          </div>

          {/* IA Narrative */}
          <div className="space-y-2">
            <button onClick={async () => {
              setGenerandoNarrativa(true)
              try {
                const res = await api.post<{ ok: boolean; narrativa: string }>(`/auditorias/${auditoriaId}/hallazgos/${h.id}/generar-narrativa`)
                onUpdated({ ...h, descripcion: res.narrativa, sugerencia_ai: true })
                success('Narrativa generada')
              } catch (e: unknown) {
                error(e instanceof Error ? e.message : 'Error')
              }
              setGenerandoNarrativa(false)
            }} disabled={generandoNarrativa}
              className="w-full py-2.5 rounded-xl text-xs font-bold flex items-center justify-center gap-2 bg-gradient-to-r from-purple-500 to-blue-600 text-white hover:opacity-90 transition-opacity disabled:opacity-50">
              {generandoNarrativa ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              {generandoNarrativa ? 'Generando narrativa...' : 'Generar narrativa con IA'}
            </button>
            {h.sugerencia_ai && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 text-[10px] font-bold border border-purple-200 dark:border-purple-800/30">
                <Sparkles size={10} /> Generado por IA
              </span>
            )}
          </div>

          {/* Marco legal */}
          <div className="p-4 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800/30 rounded-xl">
            <p className="section-label text-blue-600 dark:text-blue-400 mb-1">Marco legal aplicable</p>
            <p className="text-sm text-blue-700 dark:text-blue-300 font-medium">{h.articulo_legal}</p>
          </div>

          {/* Evidencias */}
          <div>
            <p className="section-label">Evidencias vinculadas</p>
            {evidencias.length > 0 ? (
              <div className="space-y-2 mt-2">
                {evidencias.map((ev, i) => (
                  <div key={i} className="flex items-center gap-2 px-3 py-2 rounded-xl bg-gray-50 dark:bg-gray-800/50 text-xs">
                    <FileText size={12} className="text-gray-400 shrink-0" />
                    <span className="font-bold text-gray-600 dark:text-gray-400 capitalize">{ev.tipo}</span>
                    <span className="text-gray-500 font-mono">{ev.ref || ev.id || ''}</span>
                    {ev.desc && <span className="text-gray-400 ml-auto">{ev.desc}</span>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-400 mt-1">Sin evidencias vinculadas</p>
            )}
            {puedeEditar && (
              <div className="flex gap-2 mt-3">
                <input className="input-field flex-1 text-xs" placeholder="ID del comprobante (rg90_id)" value={nuevaEvidencia} onChange={e => setNuevaEvidencia(e.target.value)} />
                <button onClick={agregarEvidencia} disabled={!nuevaEvidencia.trim()} className="btn-outline text-xs"><ExternalLink size={12} /> Vincular</button>
              </div>
            )}
          </div>

          {/* Notas */}
          <div>
            <label className="section-label">Notas del auditor</label>
            <textarea className="input-field resize-none text-sm" rows={4}
              placeholder="Agregar notas, observaciones o justificaciones..."
              value={notas} onChange={e => setNotas(e.target.value)}
              disabled={h.estado === 'descartado' && !puedeEditar} />
          </div>

          {/* Audit trail */}
          <div>
            <button onClick={() => setShowTrail(!showTrail)} className="flex items-center gap-2 text-xs font-bold text-gray-500 hover:text-gray-700">
              <History size={12} /> Historial de cambios ({trail.length})
            </button>
            {showTrail && trail.length > 0 && (
              <div className="mt-2 space-y-2 max-h-40 overflow-y-auto">
                {trail.map((t, i) => (
                  <div key={i} className="flex items-start gap-2 text-[10px] text-gray-500">
                    <span className="w-1.5 h-1.5 rounded-full bg-gray-300 mt-1 shrink-0" />
                    <div>
                      <p className="font-bold text-gray-600">{t.accion}</p>
                      <p>{t.timestamp ? new Date(t.timestamp).toLocaleString('es-PY') : ''}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Meta */}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div><p className="text-gray-400">Creado por</p><p className="font-bold text-gray-700 dark:text-gray-300 capitalize">{h.creado_por}</p></div>
            <div><p className="text-gray-400">Fecha</p><p className="font-bold text-gray-700">{fecha(h.creado_en)}</p></div>
          </div>
        </div>

        {/* Actions footer */}
        <div className="p-5 border-t border-gray-100 dark:border-gray-700 space-y-3 shrink-0">
          <button onClick={guardar} disabled={saving} className="btn-outline w-full text-sm py-2.5 flex items-center justify-center gap-2">
            <Save size={14} /> {saving ? 'Guardando...' : 'Guardar cambios'}
          </button>

          {accs.map(acc => (
            <button key={acc.action} onClick={() => setConfirmAction(acc.action)}
              className={`${acc.color} w-full text-sm py-2.5 flex items-center justify-center gap-2`}>
              <acc.icon size={15} /> {acc.label}
            </button>
          ))}
        </div>
      </div>

      <ConfirmModal open={!!confirmAction} onClose={() => setConfirmAction(null)}
        onConfirm={cambiarEstado} loading={actionLoading}
        title={`${confirmAction === 'descartado' ? 'Descartar' : confirmAction === 'revisado' ? 'Revisar' : confirmAction === 'aceptado' ? 'Aceptar' : confirmAction === 'regularizado' ? 'Regularizar' : 'Reabrir'} hallazgo`}
        message={`Confirmas cambiar el estado a "${confirmAction}"?`}
        confirmLabel="Confirmar"
        danger={confirmAction === 'descartado'} />
    </>
  )
}
