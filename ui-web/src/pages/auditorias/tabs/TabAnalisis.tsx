import { useState } from 'react'
import { Zap, CheckCircle2, AlertTriangle, Loader2, BarChart3, Database, FileSearch, TrendingUp, ChevronRight, Sparkles, BrainCircuit } from 'lucide-react'
import { api } from '../../../api/client'
import { useToast } from '../../../components/Toaster'
import { useNavigate } from 'react-router-dom'
import { pyg } from '../../../utils/formatters'

interface Props {
  auditoriaId: string
}

interface AnalisisResult {
  ok: boolean
  periodos_analizados?: number
  cruces_ejecutados?: number
  hallazgos_generados: number
  monto_ajuste_total?: number
  ejercicio_analizado?: string
  advertencias?: string[]
  errores?: string[]
}

interface RG90Resumen {
  resumen: {
    total_compras: number
    total_ventas: number
    credito_fiscal_total: number
    debito_fiscal_total: number
    comprobantes_sin_cdc: number
  }
}

const ANALISIS = [
  {
    id: 'iva',
    endpoint: 'ejecutar-analisis-iva',
    label: 'Análisis IVA Completo',
    desc: '5 cruces: RG90 vs Form.120, RG90 vs SIFEN, RG90 vs HECHAUKA, validación RUC proveedores',
    icon: BarChart3,
    color: 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400',
    accent: 'border-blue-200 dark:border-blue-800',
  },
  {
    id: 'ire',
    endpoint: 'ejecutar-analisis-ire',
    label: 'Análisis IRE',
    desc: 'Depreciaciones, gastos sin comprobante, conciliación resultado contable vs Form.500',
    icon: TrendingUp,
    color: 'bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400',
    accent: 'border-purple-200 dark:border-purple-800',
  },
  {
    id: 'ret',
    endpoint: 'ejecutar-analisis-retenciones',
    label: 'Análisis Retenciones',
    desc: 'Cruce HECHAUKA vs declaraciones Forms. 800/820/830 — retenciones practicadas y depositadas',
    icon: FileSearch,
    color: 'bg-amber-50 dark:bg-amber-900/20 text-amber-600 dark:text-amber-400',
    accent: 'border-amber-200 dark:border-amber-800',
  },
]

interface ClaudeResult {
  ok: boolean
  mensaje?: string
  hallazgos_analizados?: number
  total_contingencia?: number
  narrativa?: string
  conclusion?: string
  procedimientos?: string[]
}

export default function TabAnalisis({ auditoriaId }: Props) {
  const { success, error } = useToast()
  const navigate = useNavigate()
  const [running, setRunning] = useState<string | null>(null)
  const [results, setResults] = useState<Record<string, AnalisisResult>>({})
  const [rg90, setRg90] = useState<RG90Resumen | null>(null)
  const [loadingRg90, setLoadingRg90] = useState(false)
  const [claudeResult, setClaudeResult] = useState<ClaudeResult | null>(null)
  const [runningClaude, setRunningClaude] = useState(false)

  const ejecutar = async (a: typeof ANALISIS[0]) => {
    setRunning(a.id)
    try {
      const res = await api.post<AnalisisResult>(`/auditorias/${auditoriaId}/${a.endpoint}`)
      setResults(r => ({ ...r, [a.id]: res }))
      if (res.hallazgos_generados > 0) {
        success(`${a.label}: ${res.hallazgos_generados} hallazgos generados`)
      } else {
        success(`${a.label} completado. Sin hallazgos nuevos.`)
      }
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : `Error en ${a.label}`)
    } finally {
      setRunning(null)
    }
  }

  const ejecutarClaudeIA = async () => {
    setRunningClaude(true)
    try {
      const res = await api.post<ClaudeResult>(`/auditorias/${auditoriaId}/analisis-claude`)
      setClaudeResult(res)
      if (res.ok) {
        success(`Análisis IA completado — ${res.hallazgos_analizados} hallazgos interpretados`)
      }
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error en el análisis IA')
    } finally {
      setRunningClaude(false)
    }
  }

  const cargarRg90 = async () => {
    setLoadingRg90(true)
    try {
      const data = await api.get<RG90Resumen>(`/auditorias/${auditoriaId}/rg90`)
      setRg90(data)
    } catch {
      error('No se pudo cargar RG90')
    } finally {
      setLoadingRg90(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* RG90 Summary */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Database size={16} className="text-primary" />
            <h3 className="text-sm font-black text-gray-900 dark:text-white uppercase tracking-tight">Estado RG90 Importado</h3>
          </div>
          <button
            onClick={cargarRg90}
            disabled={loadingRg90}
            className="btn-ghost text-xs flex items-center gap-1.5"
          >
            {loadingRg90 ? <Loader2 size={12} className="animate-spin" /> : <Database size={12} />}
            Actualizar
          </button>
        </div>

        {rg90 ? (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
            {[
              { label: 'Compras', val: rg90.resumen.total_compras.toLocaleString('es-PY'), color: 'text-blue-600' },
              { label: 'Ventas', val: rg90.resumen.total_ventas.toLocaleString('es-PY'), color: 'text-green-600' },
              { label: 'CF Total', val: pyg(rg90.resumen.credito_fiscal_total), color: 'text-primary' },
              { label: 'DF Total', val: pyg(rg90.resumen.debito_fiscal_total), color: 'text-secondary' },
              { label: 'Sin CDC', val: rg90.resumen.comprobantes_sin_cdc.toString(), color: rg90.resumen.comprobantes_sin_cdc > 0 ? 'text-red-500' : 'text-gray-400' },
            ].map(stat => (
              <div key={stat.label} className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center">
                <p className="text-[10px] text-gray-400 uppercase font-bold mb-1">{stat.label}</p>
                <p className={`text-sm font-black ${stat.color}`}>{stat.val}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-6 text-center text-gray-400">
            <Database size={28} className="opacity-30 mx-auto mb-2" />
            <p className="text-xs font-bold uppercase tracking-wide">
              Importá archivos RG90 en la pestaña <strong className="text-gray-600 dark:text-gray-300">Archivos</strong> para ver el resumen
            </p>
            <button onClick={cargarRg90} className="mt-3 btn-ghost text-xs">
              {loadingRg90 ? 'Cargando...' : 'Verificar datos'}
            </button>
          </div>
        )}
      </div>

      {/* Módulos de Análisis */}
      <div className="space-y-3">
        <div className="flex items-center justify-between px-1">
          <h3 className="text-sm font-black text-gray-900 dark:text-white uppercase tracking-tight flex items-center gap-2">
            <Zap size={16} className="text-primary" /> Motores de Análisis Automático
          </h3>
        </div>

        {ANALISIS.map(a => {
          const res = results[a.id]
          const isRunning = running === a.id
          return (
            <div key={a.id} className={`card p-5 border ${a.accent} transition-all`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex items-start gap-3 flex-1">
                  <div className={`p-2.5 rounded-xl ${a.color} shrink-0 mt-0.5`}>
                    <a.icon size={18} />
                  </div>
                  <div className="flex-1">
                    <p className="font-black text-gray-900 dark:text-white text-sm">{a.label}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 leading-relaxed">{a.desc}</p>

                    {/* Result */}
                    {res && (
                      <div className={`mt-3 flex flex-wrap gap-3 items-center p-3 rounded-xl ${
                        res.hallazgos_generados > 0
                          ? 'bg-red-50 dark:bg-red-900/10 border border-red-100 dark:border-red-900/20'
                          : 'bg-green-50 dark:bg-green-900/10 border border-green-100 dark:border-green-900/20'
                      }`}>
                        {res.hallazgos_generados > 0 ? (
                          <AlertTriangle size={14} className="text-red-500 shrink-0" />
                        ) : (
                          <CheckCircle2 size={14} className="text-green-500 shrink-0" />
                        )}
                        <span className={`text-xs font-bold ${res.hallazgos_generados > 0 ? 'text-red-700 dark:text-red-300' : 'text-green-700 dark:text-green-300'}`}>
                          {res.hallazgos_generados > 0
                            ? `${res.hallazgos_generados} hallazgos generados${res.monto_ajuste_total ? ` · ${pyg(res.monto_ajuste_total)} contingencia` : ''}`
                            : 'Sin hallazgos detectados'
                          }
                        </span>
                        {res.periodos_analizados && (
                          <span className="text-[10px] text-gray-400">{res.periodos_analizados} períodos</span>
                        )}
                        {(res.advertencias?.length ?? 0) > 0 && (
                          <div className="w-full mt-1">
                            {res.advertencias!.slice(0, 3).map((adv, i) => (
                              <p key={i} className="text-[10px] text-amber-600 dark:text-amber-400">{adv}</p>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>

                <button
                  onClick={() => ejecutar(a)}
                  disabled={isRunning || running !== null}
                  className={`btn-primary py-2 px-4 text-xs flex items-center gap-1.5 shrink-0 ${running !== null && !isRunning ? 'opacity-50' : ''}`}
                >
                  {isRunning ? (
                    <><Loader2 size={13} className="animate-spin" /> Ejecutando...</>
                  ) : (
                    <><Zap size={13} /> Ejecutar</>
                  )}
                </button>
              </div>
            </div>
          )
        })}
      </div>

      {/* Análisis IA con Claude */}
      <div className="card p-5 border border-purple-200 dark:border-purple-800/40">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 flex-1">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-purple-500 to-blue-600 shrink-0 mt-0.5">
              <BrainCircuit size={18} className="text-white" />
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <p className="font-black text-gray-900 dark:text-white text-sm">Análisis con Inteligencia Artificial</p>
                <span className="px-1.5 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 text-[9px] font-black uppercase rounded-full">Claude</span>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-400 leading-relaxed">
                Claude interpreta los hallazgos existentes y redacta narrativa profesional, conclusión ejecutiva y procedimientos adicionales recomendados.
              </p>

              {claudeResult && (
                <div className="mt-4 space-y-4">
                  {!claudeResult.ok && claudeResult.mensaje && (
                    <div className="p-3 bg-amber-50 dark:bg-amber-900/10 border border-amber-200 dark:border-amber-800/30 rounded-xl text-xs text-amber-700 dark:text-amber-400">
                      {claudeResult.mensaje}
                    </div>
                  )}

                  {claudeResult.narrativa && (
                    <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-100 dark:border-gray-700">
                      <p className="text-[10px] font-black uppercase tracking-widest text-gray-400 mb-2 flex items-center gap-1.5">
                        <Sparkles size={10} /> Observaciones de Auditoría
                      </p>
                      <p className="text-xs text-gray-700 dark:text-gray-300 leading-relaxed whitespace-pre-wrap">{claudeResult.narrativa}</p>
                    </div>
                  )}

                  {claudeResult.conclusion && (
                    <div className="p-4 bg-blue-50 dark:bg-blue-900/10 rounded-xl border border-blue-100 dark:border-blue-800/30">
                      <p className="text-[10px] font-black uppercase tracking-widest text-blue-400 mb-2 flex items-center gap-1.5">
                        <CheckCircle2 size={10} /> Conclusión Ejecutiva
                      </p>
                      <p className="text-xs text-blue-800 dark:text-blue-300 leading-relaxed italic">{claudeResult.conclusion}</p>
                    </div>
                  )}

                  {claudeResult.procedimientos && claudeResult.procedimientos.length > 0 && (
                    <div className="p-4 bg-amber-50 dark:bg-amber-900/10 rounded-xl border border-amber-100 dark:border-amber-800/30">
                      <p className="text-[10px] font-black uppercase tracking-widest text-amber-500 mb-2 flex items-center gap-1.5">
                        <AlertTriangle size={10} /> Procedimientos Adicionales Recomendados
                      </p>
                      <ul className="space-y-1">
                        {claudeResult.procedimientos.map((p, i) => (
                          <li key={i} className="text-xs text-amber-800 dark:text-amber-300 leading-relaxed">{p}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <button
            onClick={ejecutarClaudeIA}
            disabled={runningClaude || running !== null}
            className="btn-primary py-2 px-4 text-xs flex items-center gap-1.5 shrink-0 bg-gradient-to-r from-purple-600 to-blue-600 border-0"
          >
            {runningClaude ? (
              <><Loader2 size={13} className="animate-spin" /> Analizando...</>
            ) : (
              <><Sparkles size={13} /> Analizar con IA</>
            )}
          </button>
        </div>
      </div>

      {/* Link a Evidence Explorer */}
      <div
        onClick={() => navigate(`/auditorias/${auditoriaId}/evidencia`)}
        className="card p-5 flex items-center justify-between cursor-pointer hover:border-primary/50 transition-colors group"
      >
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-primary/10 rounded-xl">
            <FileSearch className="text-primary" size={18} />
          </div>
          <div>
            <p className="font-black text-gray-900 dark:text-white text-sm">Evidence Explorer</p>
            <p className="text-xs text-gray-500 mt-0.5">Explorar hallazgos con evidencias detalladas, papeles de trabajo y documentación DNIT</p>
          </div>
        </div>
        <ChevronRight size={18} className="text-gray-300 group-hover:text-primary transition-colors" />
      </div>
    </div>
  )
}
