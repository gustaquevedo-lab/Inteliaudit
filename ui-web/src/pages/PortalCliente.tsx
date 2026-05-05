import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ShieldAlert, Building2, FileText, AlertTriangle, CheckCircle2, Clock, ExternalLink } from 'lucide-react'
import { api } from '../api/client'
import { pyg, fecha } from '../utils/formatters'

interface PortalData {
  firma: { nombre: string; eslogan: string | null }
  cliente: { razon_social: string; ruc: string }
  auditoria: {
    id: string
    periodo_desde: string
    periodo_hasta: string
    impuestos: string[]
    estado: string
    auditor?: string
  }
  resumen: {
    total_hallazgos: number
    total_contingencia: number
    por_riesgo: { alto: number; medio: number; bajo: number }
  }
  hallazgos: Array<{
    id: string
    impuesto: string
    periodo: string
    tipo_hallazgo: string
    descripcion: string
    articulo_legal: string
    impuesto_omitido: number
    multa_estimada: number
    intereses_estimados: number
    total_contingencia: number
    nivel_riesgo: 'alto' | 'medio' | 'bajo'
    estado: string
  }>
  token_expira: string
}

const RIESGO_STYLE = {
  alto:  'bg-red-50 border-red-200 text-red-700 dark:bg-red-900/10 dark:border-red-800 dark:text-red-300',
  medio: 'bg-amber-50 border-amber-200 text-amber-700 dark:bg-amber-900/10 dark:border-amber-800 dark:text-amber-300',
  bajo:  'bg-green-50 border-green-200 text-green-700 dark:bg-green-900/10 dark:border-green-800 dark:text-green-300',
}

export default function PortalCliente() {
  const { token } = useParams<{ token: string }>()
  const [data, setData] = useState<PortalData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) return
    fetch(`/api/portal/${token}`)
      .then(r => {
        if (!r.ok) return r.json().then(b => { throw new Error(b.detail || `Error ${r.status}`) })
        return r.json()
      })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [token])

  if (loading) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center space-y-4">
        <div className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-sm font-bold text-gray-500 uppercase tracking-widest">Cargando portal...</p>
      </div>
    </div>
  )

  if (error || !data) return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center space-y-4 max-w-md px-6">
        <ShieldAlert size={48} className="text-red-400 mx-auto" />
        <h1 className="text-xl font-black text-gray-800">Acceso no disponible</h1>
        <p className="text-gray-500 text-sm">{error || 'El enlace no es válido o ha expirado.'}</p>
        <p className="text-xs text-gray-400">Contacte a su auditor para obtener un nuevo enlace de acceso.</p>
      </div>
    </div>
  )

  const { firma, cliente, auditoria, resumen, hallazgos } = data

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      {/* Top bar */}
      <div className="bg-gradient-to-r from-[#091624] to-[#1558B0] text-white px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-black tracking-tight">
            <span className="text-[#2E84F0]">Inteli</span><span className="text-[#22C47E]">audit</span>
          </span>
          <span className="text-white/40 text-xs">|</span>
          <span className="text-sm font-bold text-white/80">{firma.nombre}</span>
        </div>
        <div className="text-right">
          <p className="text-[10px] text-white/50 uppercase tracking-widest">Portal del Cliente</p>
          <p className="text-xs text-white/70 font-mono">Expira: {fecha(data.token_expira)}</p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">

        {/* Header cliente */}
        <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 p-6 shadow-sm">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-primary/10 rounded-xl">
              <Building2 className="text-primary" size={24} />
            </div>
            <div className="flex-1">
              <h1 className="text-2xl font-black text-gray-900 dark:text-white">{cliente.razon_social}</h1>
              <p className="text-sm text-gray-500 font-mono mt-0.5">RUC: {cliente.ruc}</p>
              <div className="flex flex-wrap gap-3 mt-3 text-xs text-gray-500">
                <span>📅 {auditoria.periodo_desde} — {auditoria.periodo_hasta}</span>
                <span>🧾 {auditoria.impuestos.join(', ')}</span>
                {auditoria.auditor && <span>👤 {auditoria.auditor}</span>}
              </div>
            </div>
          </div>
        </div>

        {/* KPIs */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-gradient-to-br from-primary to-[#1558B0] rounded-2xl p-5 text-white shadow-lg shadow-primary/20">
            <p className="text-[10px] font-black uppercase tracking-widest opacity-70 mb-1">Contingencia Total Estimada</p>
            <p className="text-2xl font-black">{pyg(resumen.total_contingencia)}</p>
            <p className="text-[10px] opacity-60 mt-1">{resumen.total_hallazgos} hallazgo{resumen.total_hallazgos !== 1 ? 's' : ''} identificado{resumen.total_hallazgos !== 1 ? 's' : ''}</p>
          </div>
          <div className={`rounded-2xl p-5 border ${resumen.por_riesgo.alto > 0 ? 'bg-red-50 border-red-100 dark:bg-red-900/10 dark:border-red-800' : 'bg-green-50 border-green-100 dark:bg-green-900/10 dark:border-green-800'}`}>
            <p className="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Riesgo Alto</p>
            <p className={`text-2xl font-black ${resumen.por_riesgo.alto > 0 ? 'text-red-600' : 'text-green-600'}`}>{resumen.por_riesgo.alto}</p>
          </div>
          <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-800 rounded-2xl p-5">
            <p className="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-1">Riesgo Medio</p>
            <p className="text-2xl font-black text-amber-600">{resumen.por_riesgo.medio}</p>
          </div>
        </div>

        {/* Hallazgos */}
        <div>
          <h2 className="text-sm font-black text-gray-900 dark:text-white uppercase tracking-widest mb-3 flex items-center gap-2">
            <FileText size={15} className="text-primary" /> Hallazgos Identificados
          </h2>

          {hallazgos.length === 0 ? (
            <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-100 dark:border-gray-800 p-12 text-center text-gray-400">
              <CheckCircle2 size={40} className="opacity-20 mx-auto mb-3" />
              <p className="font-bold text-sm uppercase tracking-wide opacity-50">Sin hallazgos registrados</p>
            </div>
          ) : (
            <div className="space-y-3">
              {hallazgos.map(h => (
                <div key={h.id} className={`bg-white dark:bg-gray-900 rounded-2xl border p-5 ${
                  h.nivel_riesgo === 'alto' ? 'border-l-4 border-l-red-500' :
                  h.nivel_riesgo === 'medio' ? 'border-l-4 border-l-amber-500' :
                  'border-l-4 border-l-green-500'
                } border-gray-100 dark:border-gray-800 shadow-sm`}>
                  <div className="flex items-start justify-between gap-4 mb-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-[10px] font-black text-primary uppercase">{h.impuesto}</span>
                        <span className="text-[10px] text-gray-400">·</span>
                        <span className="text-[10px] text-gray-400">{h.periodo}</span>
                      </div>
                      <h3 className="font-bold text-gray-900 dark:text-white text-sm">
                        {h.tipo_hallazgo.replace(/_/g, ' ')}
                      </h3>
                    </div>
                    <span className={`shrink-0 px-2 py-1 rounded-lg text-[10px] font-black uppercase border ${RIESGO_STYLE[h.nivel_riesgo]}`}>
                      {h.nivel_riesgo}
                    </span>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed mb-3">{h.descripcion}</p>
                  <div className="bg-amber-50 dark:bg-amber-900/10 border border-amber-100 dark:border-amber-900/20 rounded-xl p-3 mb-3">
                    <p className="text-xs text-amber-800 dark:text-amber-300 font-medium italic">{h.articulo_legal}</p>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { label: 'Impuesto omitido', val: pyg(h.impuesto_omitido) },
                      { label: 'Multa estimada', val: pyg(h.multa_estimada) },
                      { label: 'Total contingencia', val: pyg(h.total_contingencia), bold: true },
                    ].map(item => (
                      <div key={item.label} className="bg-gray-50 dark:bg-gray-800 rounded-xl p-3 text-center">
                        <p className="text-[9px] text-gray-400 uppercase font-bold mb-1">{item.label}</p>
                        <p className={`text-sm font-black ${item.bold ? 'text-primary' : 'text-gray-800 dark:text-white'}`}>{item.val}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Nota legal */}
        <div className="bg-gray-100 dark:bg-gray-800/50 rounded-2xl p-4 text-xs text-gray-500 dark:text-gray-400 text-center leading-relaxed">
          Este reporte es de carácter informativo y confidencial. Los montos reflejan contingencias estimadas al día de hoy
          y no constituyen deuda firme ante la SET. Los valores están expresados en Guaraníes (PYG).
          Informe generado por <strong>Inteliaudit</strong> — {firma.nombre}.
        </div>
      </div>
    </div>
  )
}
