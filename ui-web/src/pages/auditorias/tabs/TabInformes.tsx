import { useState, useEffect } from 'react'
import { FileText, Download, Loader2, FileCheck, Clock, Share2, Copy, CheckCircle2, ExternalLink } from 'lucide-react'
import { api } from '../../../api/client'
import { useToast } from '../../../components/Toaster'
import { fecha, fechaHora } from '../../../utils/formatters'
import type { Informe } from '../../../api/types'

interface Props { auditoriaId: string; clienteRuc: string }

export default function TabInformes({ auditoriaId, clienteRuc }: Props) {
  const { success, error } = useToast()
  const [informes, setInformes] = useState<Informe[]>([])
  const [loading, setLoading] = useState(true)
  const [generandoWord, setGenerandoWord] = useState(false)
  const [generandoPdf, setGenerandoPdf] = useState(false)
  const [notasAuditor, setNotasAuditor] = useState('')
  const [incluirDescartados, setIncluirDescartados] = useState(false)
  const [portalToken, setPortalToken] = useState<{ token: string; url: string; expira: string } | null>(null)
  const [generandoToken, setGenerandoToken] = useState(false)
  const [copiado, setCopiado] = useState(false)

  const loadInformes = () =>
    api.get<Informe[]>(`/auditorias/${auditoriaId}/informes`).then(setInformes).finally(() => setLoading(false))

  useEffect(() => { loadInformes() }, [auditoriaId])

  const generarWord = async () => {
    setGenerandoWord(true)
    try {
      const res = await fetch(`/api/auditorias/${auditoriaId}/informes/word`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('ia_token') ?? ''}`,
        },
        body: JSON.stringify({ notas_auditor: notasAuditor || null, incluir_descartados: incluirDescartados }),
      })
      if (!res.ok) throw new Error('Error al generar el informe')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `informe_${clienteRuc}.docx`
      a.click()
      URL.revokeObjectURL(url)
      success('Informe Word generado y descargado')
      loadInformes()
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al generar informe')
    } finally {
      setGenerandoWord(false)
    }
  }

  const generarPdf = async () => {
    setGenerandoPdf(true)
    try {
      const res = await fetch(`/api/auditorias/${auditoriaId}/informes/pdf`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${localStorage.getItem('ia_token') ?? ''}`,
        },
        body: JSON.stringify({ notas_auditor: notasAuditor || null, incluir_descartados: incluirDescartados }),
      })
      if (!res.ok) throw new Error('Error al generar PDF')
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `informe_${clienteRuc}.pdf`
      a.click()
      URL.revokeObjectURL(url)
      success('Informe PDF generado y descargado')
      loadInformes()
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al generar PDF')
    } finally {
      setGenerandoPdf(false)
    }
  }

  const generarEnlacePortal = async () => {
    setGenerandoToken(true)
    try {
      const res = await api.post<{ token: string; url: string; expira: string }>(
        `/portal/auditorias/${auditoriaId}/generar-token`
      )
      setPortalToken(res)
      success('Enlace generado. Compartilo con tu cliente.')
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error generando enlace')
    } finally {
      setGenerandoToken(false)
    }
  }

  const copiarEnlace = async () => {
    if (!portalToken) return
    const url = `${window.location.origin}/app/portal/${portalToken.token}`
    await navigator.clipboard.writeText(url)
    setCopiado(true)
    setTimeout(() => setCopiado(false), 2000)
  }

  return (
    <div className="space-y-6">
      {/* Generador */}
      <div className="card p-6">
        <h3 className="text-sm font-black text-gray-800 dark:text-white uppercase tracking-tight mb-4">
          Generar informe de auditoría
        </h3>

        <div className="space-y-4 mb-6">
          <div>
            <label className="input-label">Notas del auditor (conclusiones generales)</label>
            <textarea
              className="input-field resize-none text-sm"
              rows={4}
              placeholder="Escribí las conclusiones generales, recomendaciones o comentarios para el cliente..."
              value={notasAuditor}
              onChange={e => setNotasAuditor(e.target.value)}
            />
          </div>
          <label className="flex items-center gap-3 cursor-pointer">
            <div className="relative">
              <input type="checkbox" className="sr-only" checked={incluirDescartados} onChange={e => setIncluirDescartados(e.target.checked)} />
              <div className={`w-10 h-5 rounded-full transition-colors ${incluirDescartados ? 'bg-primary' : 'bg-gray-300 dark:bg-gray-600'}`} />
              <div className={`absolute top-0.5 left-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${incluirDescartados ? 'translate-x-5' : ''}`} />
            </div>
            <span className="text-sm text-gray-700 dark:text-gray-300 font-medium">Incluir hallazgos descartados en el informe</span>
          </label>
        </div>

        <div className="flex flex-col sm:flex-row gap-3">
          <button onClick={generarWord} disabled={generandoWord || generandoPdf} className="btn-primary flex-1">
            {generandoWord
              ? <><Loader2 size={15} className="animate-spin" /> Generando Word...</>
              : <><FileText size={15} /> Descargar Word (.docx)</>
            }
          </button>
          <button onClick={generarPdf} disabled={generandoWord || generandoPdf} className="btn-outline flex-1">
            {generandoPdf
              ? <><Loader2 size={15} className="animate-spin" /> Generando PDF...</>
              : <><Download size={15} /> Descargar PDF</>
            }
          </button>
        </div>

        <div className="mt-4 p-3.5 bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800/30 rounded-xl text-xs text-blue-700 dark:text-blue-400 space-y-1">
          <p className="font-bold">El informe incluye:</p>
          <ul className="space-y-0.5 text-blue-600/80 dark:text-blue-400/80">
            <li>• Portada con logo del cliente y datos de la firma auditora</li>
            <li>• Resumen ejecutivo con KPIs de contingencia</li>
            <li>• Detalle de cada hallazgo con base legal (Ley 6380/2019, Ley 125/1991)</li>
            <li>• Matriz de riesgo por impuesto</li>
            <li>• Conclusiones y recomendaciones</li>
            <li>• Watermark Inteliaudit en pie de página</li>
          </ul>
        </div>
      </div>

      {/* Portal cliente */}
      <div className="card p-6">
        <h3 className="text-sm font-black text-gray-800 dark:text-white uppercase tracking-tight mb-1">
          Compartir con el cliente
        </h3>
        <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
          Generá un enlace de acceso temporal (30 días) para que tu cliente vea sus hallazgos sin necesidad de login.
        </p>

        <button
          onClick={generarEnlacePortal}
          disabled={generandoToken}
          className="btn-outline w-full sm:w-auto"
        >
          {generandoToken
            ? <><Loader2 size={15} className="animate-spin" /> Generando enlace...</>
            : <><Share2 size={15} /> Generar enlace de acceso</>
          }
        </button>

        {portalToken && (
          <div className="mt-4 p-4 bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800/30 rounded-xl space-y-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={15} className="text-green-600 dark:text-green-400 shrink-0" />
              <p className="text-xs font-bold text-green-700 dark:text-green-400">Enlace generado correctamente</p>
            </div>
            <div className="flex items-center gap-2 bg-white dark:bg-gray-800 border border-green-200 dark:border-green-800/40 rounded-lg px-3 py-2">
              <ExternalLink size={13} className="text-gray-400 shrink-0" />
              <span className="text-xs font-mono text-gray-600 dark:text-gray-300 truncate flex-1">
                {window.location.origin}/app/portal/{portalToken.token}
              </span>
              <button
                onClick={copiarEnlace}
                className="shrink-0 flex items-center gap-1 text-xs font-bold text-primary hover:text-primary/80 transition-colors"
              >
                {copiado ? <><CheckCircle2 size={13} className="text-green-500" /> Copiado</> : <><Copy size={13} /> Copiar</>}
              </button>
            </div>
            <p className="text-[10px] text-gray-400 dark:text-gray-500">
              Expira el {fecha(portalToken.expira)} · El cliente puede ver los hallazgos activos sin iniciar sesión.
            </p>
          </div>
        )}
      </div>

      {/* Historial */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
          <p className="section-label mb-0">Historial de informes generados</p>
        </div>
        {loading ? (
          <div className="flex justify-center py-10"><Loader2 size={22} className="animate-spin text-gray-400" /></div>
        ) : informes.length === 0 ? (
          <div className="py-12 flex flex-col items-center gap-2 text-gray-400">
            <FileCheck size={28} />
            <p className="text-sm font-bold">Aún no se generaron informes</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
            {informes.map(inf => (
              <div key={inf.id} className="px-5 py-4 flex items-center gap-4">
                <div className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
                  <FileText size={18} className="text-blue-500" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-bold text-gray-800 dark:text-gray-200">
                    Informe de auditoría impositiva
                    {inf.version > 1 && <span className="ml-1 badge-gray text-[10px]">v{inf.version}</span>}
                  </p>
                  <div className="flex items-center gap-2 mt-0.5">
                    <Clock size={11} className="text-gray-400" />
                    <p className="text-xs text-gray-500 dark:text-gray-400">{fechaHora(inf.generado_en)}</p>
                    <span className="badge-gray text-[10px]">{inf.estado}</span>
                  </div>
                </div>
                <div className="flex gap-2">
                  {inf.archivo_docx && (
                    <span className="badge-info text-[10px]">DOCX</span>
                  )}
                  {inf.archivo_pdf && (
                    <span className="badge-info text-[10px]">PDF</span>
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
