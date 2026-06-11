import { useState, useEffect } from 'react'
import { FileText, Download, Loader2, FileCheck, Clock, AlertTriangle, Eye, CheckCircle, X, Sparkles, Share2, Copy } from 'lucide-react'
import { api } from '../../../api/client'
import { useToast } from '../../../components/Toaster'
import Modal from '../../../components/Modal'
import { pyg, fecha } from '../../../utils/formatters'
import type { Informe } from '../../../api/types'

interface Props { auditoriaId: string; clienteRuc: string }

interface GenerarResponse {
  informe_id: string; tipo: string
  archivo_docx?: string; archivo_pdf?: string
  hallazgos_incluidos: number; total_contingencia: number
}

const TIPOS = [
  { id: 'auditoria_completa', label: 'Auditoria completa', desc: 'Informe tecnico con todos los hallazgos, detalle de contingencias y base legal' },
  { id: 'carta_gerencia', label: 'Carta a la gerencia', desc: 'Resumen ejecutivo para el directorio del cliente con recomendaciones' },
  { id: 'resumen_ejecutivo', label: 'Resumen ejecutivo', desc: 'Una pagina con KPIs principales y hallazgos de alto riesgo' },
]

const FORMATOS = [
  { id: 'ambos', label: 'Word + PDF', icon: FileText },
  { id: 'docx', label: 'Solo Word', icon: FileText },
  { id: 'pdf', label: 'Solo PDF', icon: Download },
]

export default function TabInformes({ auditoriaId, clienteRuc }: Props) {
  const { success, error } = useToast()
  const [informes, setInformes] = useState<Informe[]>([])
  const [loading, setLoading] = useState(true)
  const [tipo, setTipo] = useState('auditoria_completa')
  const [formato, setFormato] = useState('ambos')
  const [generando, setGenerando] = useState(false)
  const [previewHtml, setPreviewHtml] = useState<string | null>(null)
  const [showPreview, setShowPreview] = useState(false)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [downloads, setDownloads] = useState<Record<string, boolean>>({})
  const [resumenEjecutivo, setResumenEjecutivo] = useState<string | null>(null)
  const [generandoResumen, setGenerandoResumen] = useState(false)
  const [hallazgos, setHallazgos] = useState<any[]>([])
  const [hallazgosSeleccionados, setHallazgosSeleccionados] = useState<Set<string>>(new Set())
  const [portalLink, setPortalLink] = useState<string | null>(null)
  const [portalExpira, setPortalExpira] = useState<string | null>(null)
  const [generandoLink, setGenerandoLink] = useState(false)
  const [copiado, setCopiado] = useState(false)
  const [diasPortal, setDiasPortal] = useState(30)

  const loadInformes = () =>
    api.get<Informe[]>(`/auditorias/${auditoriaId}/informes`).then(setInformes).finally(() => setLoading(false))

  useEffect(() => { loadInformes() }, [auditoriaId])

  useEffect(() => {
    api.get<any[]>(`/auditorias/${auditoriaId}/hallazgos?estado=aceptado`)
      .then(setHallazgos)
      .catch(() => {})
  }, [auditoriaId])

  const generar = async () => {
    setGenerando(true)
    try {
      const res = await api.post<GenerarResponse>(`/auditorias/${auditoriaId}/informes/generar`, {
        tipo, formato, notas_auditor: null, incluir_descartados: false,
      })
      success(`Informe generado: ${res.hallazgos_incluidos} hallazgos incluidos`)
      loadInformes()
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al generar informe')
    }
    setGenerando(false)
  }

  const cargarPreview = async () => {
    setLoadingPreview(true)
    try {
      const html = await api.get<string>(`/auditorias/${auditoriaId}/informes/preview?tipo=${tipo}`)
      setPreviewHtml(html)
      setShowPreview(true)
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al cargar preview')
    }
    setLoadingPreview(false)
  }

  const descargar = async (inf: Informe, fmt: 'docx' | 'pdf') => {
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
      a.href = url; a.download = `informe_${inf.tipo}.${fmt}`; a.click()
      URL.revokeObjectURL(url)
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al descargar')
    }
    setDownloads(d => ({ ...d, [key]: false }))
  }

  const tieneHallazgos = false // placeholder

  const toggleHallazgo = (id: string) => {
    setHallazgosSeleccionados(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const generarLink = async () => {
    setGenerandoLink(true)
    try {
      const res = await api.post<{ token: string; url: string; expira: string }>('/portal/generar-link', {
        auditoria_id: auditoriaId,
        hallazgos_visibles: Array.from(hallazgosSeleccionados),
        expira_en_dias: diasPortal,
      })
      setPortalLink(`${window.location.origin}/portal/${res.token}`)
      setPortalExpira(res.expira)
      success('Link generado')
    } catch (e: unknown) { error(e instanceof Error ? e.message : 'Error') }
    setGenerandoLink(false)
  }

  return (
    <div className="space-y-5">
      {/* Tipo selector */}
      <div className="card p-5 space-y-4">
        <p className="font-black text-sm uppercase tracking-wide flex items-center gap-2">
          <FileText size={16} className="text-primary" /> Generar informe
        </p>

        <div>
          <p className="text-xs font-bold text-gray-500 uppercase mb-3">Tipo de informe</p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {TIPOS.map(t => (
              <button key={t.id} onClick={() => setTipo(t.id)}
                className={`p-4 rounded-xl border-2 text-left transition-all ${
                  tipo === t.id ? 'border-primary bg-primary/5' : 'border-gray-200 dark:border-gray-700 hover:border-gray-300'
                }`}>
                <p className="text-xs font-bold text-gray-800 dark:text-gray-200">{t.label}</p>
                <p className="text-[10px] text-gray-500 mt-1">{t.desc}</p>
              </button>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs font-bold text-gray-500 uppercase mb-3">Formato</p>
          <div className="flex gap-3">
            {FORMATOS.map(f => (
              <button key={f.id} onClick={() => setFormato(f.id)}
                className={`px-4 py-3 rounded-xl border-2 text-xs font-bold transition-all flex items-center gap-2 ${
                  formato === f.id ? 'border-primary bg-primary/5 text-primary' : 'border-gray-200 dark:border-gray-700 text-gray-500 hover:border-gray-300'
                }`}>
                <f.icon size={14} /> {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex gap-3">
          <button onClick={generar} disabled={generando}
            className="btn-primary flex-1 py-3 text-sm flex items-center justify-center gap-2">
            {generando ? <Loader2 size={15} className="animate-spin" /> : <FileText size={15} />}
            {generando ? 'Generando...' : 'Generar informe'}
          </button>
          <button onClick={cargarPreview} disabled={loadingPreview}
            className="btn-outline py-3 px-4 text-sm flex items-center gap-2">
            {loadingPreview ? <Loader2 size={15} className="animate-spin" /> : <Eye size={15} />}
            Preview
          </button>
        </div>
      </div>

      {/* Resumen Ejecutivo */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <p className="font-black text-sm uppercase tracking-wide flex items-center gap-2">
            <FileText size={16} className="text-primary" /> Resumen ejecutivo con IA
          </p>
          <button onClick={async () => {
            setGenerandoResumen(true)
            try {
              const res = await api.post<{ resumen: string; hallazgos_incluidos: number; total_contingencia: number }>(`/auditorias/${auditoriaId}/resumen-ejecutivo`)
              setResumenEjecutivo(res.resumen)
              success(`Resumen generado: ${res.hallazgos_incluidos} hallazgos incluidos`)
            } catch (e: unknown) { error(e instanceof Error ? e.message : 'Error') }
            setGenerandoResumen(false)
          }} disabled={generandoResumen}
            className="btn-primary py-2 px-4 text-xs flex items-center gap-1.5 bg-gradient-to-r from-purple-500 to-blue-600 border-0">
            {generandoResumen ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
            {generandoResumen ? 'Generando...' : 'Generar resumen ejecutivo'}
          </button>
        </div>
        <p className="text-xs text-gray-500">Usa IA para generar un resumen ejecutivo profesional de 3-4 parrafos para presentar al directorio del cliente.</p>

        {resumenEjecutivo !== null && (
          <div className="space-y-3">
            <textarea className="input-field resize-none text-sm" rows={8}
              value={resumenEjecutivo} onChange={e => setResumenEjecutivo(e.target.value)} />
            <div className="flex items-center gap-3">
              <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400 text-[10px] font-bold border border-green-200 dark:border-green-800/30">
                <CheckCircle size={10} /> Se incluira en el proximo informe
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Preview modal */}
      <Modal open={showPreview} onClose={() => setShowPreview(false)} title="Preview del informe" size="xl"
        footer={<button className="btn-primary" onClick={() => setShowPreview(false)}><X size={14} /> Cerrar</button>}>
        {previewHtml && (
          <iframe srcDoc={previewHtml} className="w-full h-[70vh] rounded-xl border border-gray-200" />
        )}
      </Modal>

      {/* Compartir con cliente */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center gap-2">
          <Share2 size={16} className="text-primary" />
          <p className="font-black text-sm uppercase tracking-wide">Compartir con el cliente</p>
        </div>
        <p className="text-xs text-gray-500">Genera un link seguro para que tu cliente vea los hallazgos seleccionados sin login.</p>
        <div className="flex items-center gap-3">
          <label className="text-xs font-bold text-gray-500 w-20">Expira en</label>
          <select className="input-field text-sm w-auto" value={diasPortal} onChange={e => setDiasPortal(Number(e.target.value))}>
            <option value={7}>7 dias</option>
            <option value={15}>15 dias</option>
            <option value={30}>30 dias</option>
            <option value={60}>60 dias</option>
            <option value={90}>90 dias</option>
          </select>
        </div>
        {hallazgos.length > 0 && (
          <div>
            <p className="text-xs font-bold text-gray-500 mb-2">Hallazgos ({hallazgosSeleccionados.size} seleccionados)</p>
            <div className="max-h-36 overflow-y-auto space-y-1">
              {hallazgos.map((h: any) => (
                <label key={h.id} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50 cursor-pointer text-xs">
                  <input type="checkbox" checked={hallazgosSeleccionados.has(h.id)} onChange={() => {
                    const next = new Set(hallazgosSeleccionados)
                    if (next.has(h.id)) next.delete(h.id); else next.add(h.id)
                    setHallazgosSeleccionados(next)
                  }} className="rounded border-gray-300 text-primary" />
                  <span className="font-bold text-gray-700 dark:text-gray-300 flex-1 truncate">{h.tipo_hallazgo}</span>
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${h.nivel_riesgo === 'alto' ? 'bg-red-100 text-red-600' : h.nivel_riesgo === 'medio' ? 'bg-amber-100 text-amber-600' : 'bg-green-100 text-green-600'}`}>{h.nivel_riesgo}</span>
                </label>
              ))}
            </div>
          </div>
        )}
        <button onClick={async () => {
          setGenerandoLink(true)
          try {
            const res = await api.post<{ token: string; url: string; expira: string }>('/portal/generar-link', { auditoria_id: auditoriaId, hallazgos_visibles: Array.from(hallazgosSeleccionados), expira_en_dias: diasPortal })
            setPortalLink(`${window.location.origin}/portal/${res.token}`)
            setPortalExpira(res.expira)
            success('Link generado')
          } catch (e: unknown) { error(e instanceof Error ? e.message : 'Error') }
          setGenerandoLink(false)
        }} disabled={generandoLink || hallazgosSeleccionados.size === 0}
          className="btn-primary text-sm py-2.5 flex items-center justify-center gap-2">
          {generandoLink ? <Loader2 size={14} className="animate-spin" /> : <Share2 size={14} />}
          {generandoLink ? 'Generando...' : 'Generar link de acceso'}
        </button>
        {portalLink && (
          <div className="p-4 rounded-xl bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800/30 space-y-3">
            <div className="flex items-center gap-2"><CheckCircle size={15} className="text-green-600 shrink-0" /><p className="text-xs font-bold text-green-700">Link generado</p></div>
            <div className="flex items-center gap-2 bg-white dark:bg-gray-800 border border-green-200 rounded-lg px-3 py-2">
              <span className="text-xs font-mono text-gray-600 truncate flex-1">{portalLink}</span>
              <button onClick={async () => { await navigator.clipboard.writeText(portalLink); setCopiado(true); setTimeout(() => setCopiado(false), 2000) }} className="text-xs font-bold text-primary shrink-0">{copiado ? 'Copiado' : <><Copy size={12} /> Copiar</>}</button>
            </div>
            {portalExpira && <p className="text-[10px] text-gray-400">Expira: {new Date(portalExpira).toLocaleDateString('es-PY')}</p>}
          </div>
        )}
      </div>

      {/* Lista de informes */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
          <p className="section-label mb-0">Informes generados ({informes.length})</p>
        </div>
        {loading ? (
          <div className="flex justify-center py-10"><Loader2 size={22} className="animate-spin text-gray-400" /></div>
        ) : informes.length === 0 ? (
          <div className="py-12 flex flex-col items-center gap-2 text-gray-400">
            <FileCheck size={28} />
            <p className="text-sm font-bold">Aun no se generaron informes</p>
            <p className="text-xs">Selecciona tipo y formato arriba y hace clic en Generar</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
            {informes.map(inf => (
              <div key={inf.id} className="px-5 py-4 flex items-center gap-4">
                <div className="p-2 rounded-lg shrink-0"
                  style={{ background: inf.tipo === 'auditoria_completa' ? 'rgba(46,132,240,0.1)' : 'rgba(34,196,126,0.1)' }}>
                  <FileText size={18} style={{ color: inf.tipo === 'auditoria_completa' ? '#2E84F0' : '#22C47E' }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-bold text-gray-800 dark:text-gray-200 capitalize">
                      {inf.tipo.replace(/_/g, ' ')}
                    </p>
                    {inf.version > 1 && <span className="badge-gray text-[10px]">v{inf.version}</span>}
                    <span className="badge-gray text-[10px]">{inf.estado}</span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <Clock size={11} className="text-gray-400" />
                    <p className="text-xs text-gray-500">{fecha(inf.generado_en)}</p>
                  </div>
                </div>
                <div className="flex gap-2">
                  {inf.archivo_docx && (
                    <button onClick={() => descargar(inf, 'docx')} disabled={downloads[`${inf.id}-docx`]}
                      className="btn-outline text-xs py-1.5 px-3 flex items-center gap-1">
                      {downloads[`${inf.id}-docx`] ? <Loader2 size={11} className="animate-spin" /> : null}
                      DOCX
                    </button>
                  )}
                  {inf.archivo_pdf && (
                    <button onClick={() => descargar(inf, 'pdf')} disabled={downloads[`${inf.id}-pdf`]}
                      className="btn-outline text-xs py-1.5 px-3 flex items-center gap-1">
                      {downloads[`${inf.id}-pdf`] ? <Loader2 size={11} className="animate-spin" /> : null}
                      PDF
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
