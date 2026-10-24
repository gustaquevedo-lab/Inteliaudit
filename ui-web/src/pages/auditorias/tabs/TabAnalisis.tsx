import { useState, useEffect, useCallback } from 'react'
import { Zap, CheckCircle, AlertTriangle, Loader2, BarChart3, FileSearch, TrendingUp, XCircle, Clock, ArrowRight, ChevronRight } from 'lucide-react'
import { api } from '../../../api/client'
import { useToast } from '../../../components/Toaster'
import { useNavigate } from 'react-router-dom'
import { pyg } from '../../../utils/formatters'

interface Props { auditoriaId: string }

interface RG90Resumen {
  resumen: {
    total_compras: number; total_ventas: number
    credito_fiscal_total: number; debito_fiscal_total: number
    comprobantes_sin_cdc: number
  }
}

interface CruceEstado {
  nombre: string; estado: string; hallazgos: number; error?: string
}

interface AnalisisEstado {
  estado: string; progreso: number; cruces: CruceEstado[]
  total_hallazgos: number; error?: string
  hallazgos_por_riesgo?: Record<string, number>
}

const IMPUESTOS = [
  { id: 'iva',         label: 'IVA',                         desc: '5 cruces: RG90 vs Form.120, SIFEN, HECHAUKA, RUC',                     icon: BarChart3 },
  { id: 'ire',         label: 'IRE (Art. 16)',               desc: 'Conciliación fiscal, depreciaciones, gastos sin comprobante',           icon: TrendingUp },
  { id: 'retenciones', label: 'Retenciones',                 desc: 'Cruce HECHAUKA vs Forms. 800/820, retenciones omitidas',               icon: FileSearch },
  { id: 'banco',       label: 'Conciliación Bancaria',        desc: 'Cruce extractos vs ventas RG90 y detección de gastos personales',       icon: ArrowRight },
  { id: 'analiticos',  label: 'Procedimientos Analíticos',    desc: 'NIA 520: Ratios, márgenes brutos, benchmarks Paraguay y desvíos >30%', icon: Zap },
]

const MESES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Setiembre','Octubre','Noviembre','Diciembre']

function getPeriodosRango(desde: string, hasta: string): string[] {
  const [a1, m1] = desde.split('-').map(Number)
  const [a2, m2] = hasta.split('-').map(Number)
  const ps: string[] = []
  let a = a1, m = m1
  while (a < a2 || (a === a2 && m <= m2)) {
    ps.push(`${a}-${String(m).padStart(2, '0')}`)
    m++; if (m > 12) { m = 1; a++ }
  }
  return ps
}

export default function TabAnalisis({ auditoriaId }: Props) {
  const { success, error: showError } = useToast()
  const navigate = useNavigate()
  const [rg90, setRg90] = useState<RG90Resumen | null>(null)
  const [loadingRg90, setLoadingRg90] = useState(false)
  const [selected, setSelected] = useState<string[]>(['iva'])
  const [periodoDesde, setPeriodoDesde] = useState('2024-01')
  const [periodoHasta, setPeriodoHasta] = useState('2024-12')
  const [jobId, setJobId] = useState<string | null>(null)
  const [estado, setEstado] = useState<AnalisisEstado | null>(null)
  const [running, setRunning] = useState(false)
  const [analiticos, setAnaliticos] = useState<any | null>(null)
  const [conciliacion, setConciliacion] = useState<any | null>(null)
  const [loadingExtras, setLoadingExtras] = useState(false)

  const loadExtras = useCallback(async () => {
    setLoadingExtras(true)
    try {
      const [an, cf] = await Promise.allSettled([
        api.get<any>(`/auditorias/${auditoriaId}/analiticos`),
        api.get<any>(`/auditorias/${auditoriaId}/conciliacion-fiscal`),
      ])
      if (an.status === 'fulfilled' && an.value?.ok) setAnaliticos(an.value)
      if (cf.status === 'fulfilled' && cf.value?.ok) setConciliacion(cf.value)
    } catch { /* ignore */ }
    setLoadingExtras(false)
  }, [auditoriaId])

  useEffect(() => {
    loadExtras()
  }, [loadExtras])

  const loadRg90 = useCallback(async () => {
    setLoadingRg90(true)
    try { setRg90(await api.get<RG90Resumen>(`/auditorias/${auditoriaId}/rg90`)) }
    catch { /* no data yet */ }
    setLoadingRg90(false)
  }, [auditoriaId])

  useEffect(() => { loadRg90() }, [loadRg90])

  // Polling de estado
  useEffect(() => {
    if (!jobId || !running) return
    const interval = setInterval(async () => {
      try {
        const e = await api.get<AnalisisEstado>(`/auditorias/${auditoriaId}/estado-analisis?job_id=${jobId}`)
        setEstado(e)
        if (e.estado === 'completado' || e.estado === 'error') {
          setRunning(false)
          clearInterval(interval)
          if (e.estado === 'completado') {
            success('Analisis completado')
            loadExtras()
          }
        }
      } catch { /* polling failed */ }
    }, 2000)
    return () => clearInterval(interval)
  }, [jobId, running, auditoriaId, success])

  const ejecutar = async () => {
    if (selected.length === 0) { showError('Selecciona al menos un impuesto'); return }
    setRunning(true)
    setJobId(null)
    setEstado(null)
    try {
      const periodos = getPeriodosRango(periodoDesde, periodoHasta)
      const res = await api.post<{ ok: boolean; job_id: string }>(
        `/auditorias/${auditoriaId}/ejecutar-analisis`,
        { impuestos: selected, periodos }
      )
      setJobId(res.job_id)
    } catch (e: unknown) {
      setRunning(false)
      showError(e instanceof Error ? e.message : 'Error al iniciar analisis')
    }
  }

  const toggleImpuesto = (id: string) => {
    setSelected(prev => prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id])
  }

  const hasData = rg90 && (rg90.resumen.total_compras > 0 || rg90.resumen.total_ventas > 0)

  const statusIcon = (s: string) => {
    switch (s) {
      case 'completado': return <CheckCircle size={14} className="text-green-500 shrink-0" />
      case 'ejecutando': return <Loader2 size={14} className="animate-spin text-primary shrink-0" />
      case 'error': return <XCircle size={14} className="text-red-500 shrink-0" />
      default: return <Clock size={14} className="text-gray-300 shrink-0" />
    }
  }

  return (
    <div className="space-y-5">
      {/* Resumen de datos disponibles */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-4">
          <p className="section-label mb-0 flex items-center gap-2">
            <BarChart3 size={16} className="text-primary" /> Datos disponibles
          </p>
          <button onClick={loadRg90} disabled={loadingRg90} className="btn-ghost text-xs">
            {loadingRg90 ? <Loader2 size={12} className="animate-spin" /> : null}
            Actualizar
          </button>
        </div>
        {rg90 ? (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center">
              <p className="text-[10px] text-gray-400 uppercase font-bold mb-1">RG90 Compras</p>
              <p className="text-sm font-black text-blue-600">{rg90.resumen.total_compras.toLocaleString('es-PY')}</p>
            </div>
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center">
              <p className="text-[10px] text-gray-400 uppercase font-bold mb-1">RG90 Ventas</p>
              <p className="text-sm font-black text-green-600">{rg90.resumen.total_ventas.toLocaleString('es-PY')}</p>
            </div>
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center">
              <p className="text-[10px] text-gray-400 uppercase font-bold mb-1">Credito Fiscal</p>
              <p className="text-xs font-black text-primary">{pyg(rg90.resumen.credito_fiscal_total)}</p>
            </div>
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center">
              <p className="text-[10px] text-gray-400 uppercase font-bold mb-1">Debito Fiscal</p>
              <p className="text-xs font-black text-secondary">{pyg(rg90.resumen.debito_fiscal_total)}</p>
            </div>
          </div>
        ) : (
          <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-6 text-center text-gray-400">
            <p className="text-xs font-bold uppercase tracking-wide">
              Importa archivos RG90 en la pestana <strong className="text-gray-600 dark:text-gray-300">Archivos</strong> primero
            </p>
            <button onClick={loadRg90} className="mt-3 btn-ghost text-xs">
              {loadingRg90 ? 'Cargando...' : 'Verificar datos'}
            </button>
          </div>
        )}
      </div>

      {/* Selector de impuestos + periodos */}
      <div className="card p-5 space-y-4">
        <p className="section-label mb-0 flex items-center gap-2">
          <Zap size={16} className="text-primary" /> Configurar analisis
        </p>

        <div>
          <p className="text-xs font-bold text-gray-600 dark:text-gray-400 mb-3 uppercase tracking-wide">Impuestos a analizar</p>
          <div className="flex flex-wrap gap-3">
            {IMPUESTOS.map(imp => {
              const isSelected = selected.includes(imp.id)
              return (
                <button
                  key={imp.id}
                  onClick={() => toggleImpuesto(imp.id)}
                  disabled={running}
                  className={`flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all text-left ${
                    isSelected
                      ? 'border-primary bg-primary/5 text-gray-900 dark:text-white'
                      : 'border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:border-gray-300'
                  } ${running ? 'opacity-50 cursor-not-allowed' : ''}`}
                >
                  <div className={`p-2 rounded-lg ${isSelected ? 'bg-primary text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-400'}`}>
                    <imp.icon size={16} />
                  </div>
                  <div>
                    <p className="text-xs font-bold">{imp.label}</p>
                    <p className="text-[10px] text-gray-400">{imp.desc}</p>
                  </div>
                  <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ml-auto transition-colors ${
                    isSelected ? 'border-primary bg-primary' : 'border-gray-300 dark:border-gray-600'
                  }`}>
                    {isSelected && <CheckCircle size={12} className="text-white" />}
                  </div>
                </button>
              )
            })}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="input-label">Periodo desde</label>
            <input type="month" className="input-field" value={periodoDesde} onChange={e => setPeriodoDesde(e.target.value)} disabled={running} />
          </div>
          <div>
            <label className="input-label">Periodo hasta</label>
            <input type="month" className="input-field" value={periodoHasta} onChange={e => setPeriodoHasta(e.target.value)} disabled={running} />
          </div>
        </div>

        <button onClick={ejecutar} disabled={running || selected.length === 0 || !hasData}
          className="btn-primary w-full py-3 text-sm flex items-center justify-center gap-2">
          {running ? <Loader2 size={16} className="animate-spin" /> : <Zap size={16} />}
          {running ? 'Ejecutando analisis...' : 'Ejecutar analisis'}
        </button>
        {!hasData && !loadingRg90 && (
          <p className="text-xs text-amber-600 text-center">Importa archivos RG90 y HECHAUKA primero</p>
        )}
      </div>

      {/* Progreso en vivo */}
      {estado && estado.estado !== 'idle' && (
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              {estado.estado === 'ejecutando' && <Loader2 size={16} className="animate-spin text-primary" />}
              {estado.estado === 'completado' && <CheckCircle size={16} className="text-green-500" />}
              {estado.estado === 'error' && <AlertTriangle size={16} className="text-red-500" />}
              <p className="font-bold text-sm uppercase">
                {estado.estado === 'ejecutando' ? 'Ejecutando...' :
                 estado.estado === 'completado' ? 'Analisis completado' : 'Error en analisis'}
              </p>
            </div>
            <span className="text-xs font-bold text-gray-500">{estado.progreso}%</span>
          </div>

          <div className="w-full h-2.5 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all duration-500 ${
              estado.estado === 'error' ? 'bg-red-500' : 'bg-primary'
            }`} style={{ width: `${estado.progreso}%` }} />
          </div>

          {estado.total_hallazgos > 0 && (
            <div className="px-4 py-3 rounded-xl bg-red-50 dark:bg-red-900/10 border border-red-100 dark:border-red-900/20 flex items-center gap-3">
              <AlertTriangle size={16} className="text-red-500 shrink-0" />
              <div>
                <p className="text-xs font-bold text-red-700 dark:text-red-300">
                  {estado.total_hallazgos} hallazgo{estado.total_hallazgos !== 1 ? 's' : ''} encontrado{estado.total_hallazgos !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
          )}

          {/* Lista de cruces */}
          <div className="space-y-2">
            {estado.cruces.map((cruce, i) => (
              <div key={i} className={`flex items-center gap-3 px-4 py-3 rounded-xl text-xs font-medium ${
                cruce.estado === 'completado' ? 'bg-green-50 dark:bg-green-900/10 text-green-700 dark:text-green-300' :
                cruce.estado === 'ejecutando' ? 'bg-blue-50 dark:bg-blue-900/10 text-blue-700 dark:text-blue-300' :
                cruce.estado === 'error' ? 'bg-red-50 dark:bg-red-900/10 text-red-700 dark:text-red-300' :
                'bg-gray-50 dark:bg-gray-800/50 text-gray-400'
              }`}>
                {statusIcon(cruce.estado)}
                <span className="flex-1">{cruce.nombre}</span>
                {cruce.hallazgos > 0 && (
                  <span className="px-2 py-0.5 rounded-full bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 text-[10px] font-bold">
                    {cruce.hallazgos} hallazgo{cruce.hallazgos !== 1 ? 's' : ''}
                  </span>
                )}
                {cruce.estado === 'completado' && cruce.hallazgos === 0 && (
                  <CheckCircle size={12} className="text-green-400" />
                )}
                {cruce.error && (
                  <span className="text-[10px] text-red-400 ml-2 truncate max-w-[200px]">{cruce.error}</span>
                )}
              </div>
            ))}
          </div>

          {estado.error && (
            <div className="px-4 py-3 rounded-xl bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400 text-xs">
              {estado.error}
            </div>
          )}
        </div>
      )}

      {/* Resultado final */}
      {estado && estado.estado === 'completado' && estado.total_hallazgos > 0 && (
        <div className="card p-5 space-y-4">
          <p className="section-label mb-0">Resumen de hallazgos</p>
          <div className="grid grid-cols-3 gap-3">
            {['alto', 'medio', 'bajo'].map(riesgo => {
              const count = estado.hallazgos_por_riesgo?.[riesgo] ?? 0
              const colors = { alto: 'bg-red-50 border-red-200 text-red-700', medio: 'bg-amber-50 border-amber-200 text-amber-700', bajo: 'bg-green-50 border-green-200 text-green-700' }
              const labels = { alto: 'Alto', medio: 'Medio', bajo: 'Bajo' }
              return (
                <div key={riesgo} className={`px-4 py-3 rounded-xl border ${colors[riesgo as keyof typeof colors]} text-center`}>
                  <p className="text-xs font-bold mb-1">{labels[riesgo as keyof typeof labels]}</p>
                  <p className="text-2xl font-black">{count}</p>
                </div>
              )
            })}
          </div>
          <button onClick={() => navigate(`/auditorias/${auditoriaId}`)}
            className="btn-primary w-full py-3 text-sm flex items-center justify-center gap-2">
            Ver hallazgos <ChevronRight size={14} />
          </button>
        </div>
      )}

      {/* Procedimientos Analíticos (NIA 520) */}
      {analiticos && analiticos.ratios && analiticos.ratios.length > 0 && (
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <p className="section-label mb-0 flex items-center gap-2">
              <Zap size={16} className="text-primary" /> Ratios y Benchmarks de Industria (NIA 520)
            </p>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">
              Período {analiticos.periodo} • {analiticos.actividad || 'General'}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {analiticos.ratios.map((r: any, idx: number) => (
              <div key={idx} className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 border border-gray-100 dark:border-gray-700">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[11px] font-bold text-gray-500">{r.nombre}</span>
                  {r.dentro_rango !== null && (
                    <span className={`text-[9px] font-bold px-1.5 py-0.5 rounded ${
                      r.dentro_rango ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                    }`}>
                      {r.dentro_rango ? 'En rango' : 'Desvío'}
                    </span>
                  )}
                </div>
                <p className="text-lg font-black text-gray-900 dark:text-white">
                  {typeof r.valor === 'number' ? r.valor.toLocaleString('es-PY') : r.valor} <span className="text-xs font-normal text-gray-400">{r.unidad}</span>
                </p>
                {r.benchmark_min !== null && r.benchmark_max !== null && (
                  <p className="text-[10px] text-gray-400 mt-1">
                    Benchmark: {r.benchmark_min} - {r.benchmark_max} {r.unidad}
                  </p>
                )}
                {r.observacion && (
                  <p className="text-[10px] text-gray-400 italic mt-0.5">{r.observacion}</p>
                )}
              </div>
            ))}
          </div>

          {analiticos.alertas && analiticos.alertas.length > 0 && (
            <div className="space-y-1.5 mt-2">
              <p className="text-[11px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400">Alertas Analíticas:</p>
              {analiticos.alertas.map((alt: string, i: number) => (
                <div key={i} className="text-xs p-2 rounded-lg bg-amber-50 dark:bg-amber-950/20 text-amber-800 dark:text-amber-300 flex items-center gap-2">
                  <AlertTriangle size={14} className="shrink-0 text-amber-500" />
                  <span>{alt}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Conciliación Contable → Fiscal (IRE Art. 16) */}
      {conciliacion && (conciliacion.resultado_contable !== 0 || (conciliacion.ajustes && conciliacion.ajustes.length > 0)) && (
        <div className="card p-5 space-y-4">
          <div className="flex items-center justify-between">
            <p className="section-label mb-0 flex items-center gap-2">
              <TrendingUp size={16} className="text-primary" /> Conciliación Fiscal IRE (Ley 6380 Art. 16)
            </p>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300">
              Ejercicio {conciliacion.ejercicio}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center">
              <p className="text-[10px] text-gray-400 uppercase font-bold mb-1">Resultado Contable</p>
              <p className="text-xs font-black text-gray-800 dark:text-gray-200">{pyg(conciliacion.resultado_contable)}</p>
            </div>
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center">
              <p className="text-[10px] text-gray-400 uppercase font-bold mb-1">Ajustes Art. 16 (+)</p>
              <p className="text-xs font-black text-amber-600">{pyg(conciliacion.ajustes_suma)}</p>
            </div>
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center">
              <p className="text-[10px] text-gray-400 uppercase font-bold mb-1">Renta Neta Imponible</p>
              <p className="text-xs font-black text-primary">{pyg(conciliacion.renta_neta_imponible)}</p>
            </div>
            <div className="bg-gray-50 dark:bg-gray-800/50 rounded-xl p-3 text-center">
              <p className="text-[10px] text-gray-400 uppercase font-bold mb-1">Diferencia IRE (10%)</p>
              <p className={`text-xs font-black ${conciliacion.diferencia !== 0 ? 'text-red-600' : 'text-green-600'}`}>
                {pyg(conciliacion.diferencia)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
