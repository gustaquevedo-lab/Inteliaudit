import { useState, useEffect } from 'react'
import {
  Play, Pause, RefreshCw, CheckCircle, XCircle, Clock,
  Download, AlertTriangle, Bookmark, Zap, Key, Copy, Check,
  ShieldCheck, ArrowRight, Database
} from 'lucide-react'
import { api } from '../../../api/client'
import { useToast } from '../../../components/Toaster'

interface Job {
  id: string
  tipo: string
  estado: 'pendiente' | 'ejecutando' | 'completado' | 'error' | 'cancelado'
  progreso: number
  creado_en: string
  iniciado_en: string | null
  completado_en: string | null
  error_msg: string | null
  reintentos: number
  params: {
    cliente_ruc: string
    periodo_desde?: string
    periodo_hasta?: string
  } | null
  resultado: {
    archivos?: string[]
    total_registros?: number
  } | null
}

interface Props {
  auditoriaId: string
  clienteRuc: string
}

export default function TabAutomatizacion({ auditoriaId, clienteRuc }: Props) {
  const { success, error } = useToast()
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [encolando, setEncolando] = useState(false)
  const [tipoJob, setTipoJob] = useState('scraper_rg90')
  const [periodoDesde, setPeriodoDesde] = useState('2024-01')
  const [periodoHasta, setPeriodoHasta] = useState('2024-12')

  // Estado para la integración REA Marangatú
  const [sessionCookie, setSessionCookie] = useState('')
  const [verificandoSesion, setVerificandoSesion] = useState(false)
  const [sesionInfo, setSesionInfo] = useState<{
    verificada: boolean
    activa: boolean
    ruc?: string | null
    mensaje?: string
  } | null>(null)
  const [sincronizandoRea, setSincronizandoRea] = useState(false)
  const [resultadoSync, setResultadoSync] = useState<{
    total_importados: number
    importados_compras: number
    importados_ventas: number
    cdcs_validados: number
    mensaje: string
  } | null>(null)
  const [copiadoBookmarklet, setCopiadoBookmarklet] = useState(false)

  // Extraer sync_cookie si vino por querystring
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const cookieParam = params.get('sync_cookie')
    if (cookieParam) {
      setSessionCookie(cookieParam)
      // Auto-verificar si viene desde el bookmarklet
      verificarSesionHttp(cookieParam)
    }
  }, [])

  const loadJobs = async () => {
    try {
      const data = await api.get<Job[]>('/jobs')
      setJobs(data)
    } catch (e) {
      console.error('Error cargando jobs:', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadJobs()
    const interval = setInterval(loadJobs, 5000)
    return () => clearInterval(interval)
  }, [])

  const encolarJob = async () => {
    setEncolando(true)
    try {
      await api.post('/jobs/encolar', {
        tipo: tipoJob,
        cliente_ruc: clienteRuc,
        periodo_desde: periodoDesde,
        periodo_hasta: periodoHasta,
      })
      success('Job encolado correctamente')
      loadJobs()
    } catch (e: any) {
      error(e.message || 'Error al encolar job')
    } finally {
      setEncolando(false)
    }
  }

  const cancelarJob = async (jobId: string) => {
    try {
      await api.post(`/jobs/${jobId}/cancelar`)
      success('Job cancelado')
      loadJobs()
    } catch (e: any) {
      error(e.message || 'Error al cancelar job')
    }
  }

  // --- REA Marangatú Actions ---

  const verificarSesionHttp = async (cookieOverride?: string) => {
    const cookieAUsar = cookieOverride || sessionCookie
    if (!cookieAUsar.trim()) {
      error('Ingrese una cookie de sesión o use el Bookmarklet')
      return
    }

    setVerificandoSesion(true)
    setSesionInfo(null)
    try {
      const res = await api.post<{
        ok: boolean
        activa: boolean
        ruc: string | null
        mensaje: string
      }>(`/auditorias/${auditoriaId}/marangatu/verificar`, {
        cookie: cookieAUsar,
      })
      setSesionInfo({
        verificada: true,
        activa: res.activa,
        ruc: res.ruc,
        mensaje: res.mensaje,
      })
      if (res.activa) {
        success(`Sesión activa para RUC ${res.ruc || clienteRuc}`)
      } else {
        error(res.mensaje || 'La sesión en Marangatú ha expirado')
      }
    } catch (e: any) {
      setSesionInfo({
        verificada: true,
        activa: false,
        mensaje: e.message || 'Error de conexión con Marangatú',
      })
      error(e.message || 'Error al verificar sesión')
    } finally {
      setVerificandoSesion(false)
    }
  }

  const sincronizarMarangatuHttp = async () => {
    if (!sessionCookie.trim()) {
      error('Ingrese una cookie de sesión activa')
      return
    }

    setSincronizandoRea(true)
    setResultadoSync(null)
    try {
      const res = await api.post<{
        ok: boolean
        mensaje: string
        importados_compras: number
        importados_ventas: number
        total_importados: number
        cdcs_validados: number
      }>(`/auditorias/${auditoriaId}/marangatu/sync`, {
        cookie: sessionCookie,
        periodo_desde: periodoDesde,
        periodo_hasta: periodoHasta,
        tipo: 'ambos',
      })

      setResultadoSync(res)
      success(res.mensaje || 'Comprobantes sincronizados exitosamente')
    } catch (e: any) {
      error(e.message || 'Error al sincronizar con Marangatú')
    } finally {
      setSincronizandoRea(false)
    }
  }

  // Código javascript del bookmarklet
  const bookmarkletCode = `javascript:(function(){const c=document.cookie;if(!window.location.hostname.includes('marangatu')){alert('Por favor ejecute este marcador dentro del portal Marangatú (marangatu.set.gov.py)');return;}const u=window.location.origin.includes('localhost')?'http://localhost:5173':'https://inteliaudit.intellihouse.lat';const target=u+'/auditorias/${auditoriaId}?sync_cookie='+encodeURIComponent(c);if(confirm('Sesión Marangatú detectada. ¿Sincronizar comprobantes con Inteliaudit?')){window.open(target,'_blank');}})();`

  const copiarCodigoBookmarklet = () => {
    navigator.clipboard.writeText(bookmarkletCode)
    setCopiadoBookmarklet(true)
    success('Código del Bookmarklet copiado al portapapeles')
    setTimeout(() => setCopiadoBookmarklet(false), 3000)
  }

  const getEstadoIcon = (estado: string) => {
    switch (estado) {
      case 'pendiente':
        return <Clock size={16} className="text-gray-400" />
      case 'ejecutando':
        return <RefreshCw size={16} className="text-blue-500 animate-spin" />
      case 'completado':
        return <CheckCircle size={16} className="text-green-500" />
      case 'error':
        return <XCircle size={16} className="text-red-500" />
      case 'cancelado':
        return <Pause size={16} className="text-gray-400" />
      default:
        return null
    }
  }

  const getEstadoColor = (estado: string) => {
    switch (estado) {
      case 'pendiente':
        return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
      case 'ejecutando':
        return 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
      case 'completado':
        return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
      case 'error':
        return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
      case 'cancelado':
        return 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
      default:
        return 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300'
    }
  }

  return (
    <div className="space-y-6">
      {/* SECCIÓN 1: REA 1-CLIC BOOKMARKLET & SINCRONIZACIÓN DIRECTA */}
      <div className="card p-6 border border-primary/20 bg-gradient-to-br from-white to-blue-50/40 dark:from-gray-900 dark:to-blue-950/20">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-5 pb-4 border-b border-gray-100 dark:border-gray-800">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-lg bg-primary/10 text-primary">
                <Zap size={20} />
              </span>
              <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                Sincronizador Directo Marangatú (Protocolo REA)
              </h3>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Descarga directa de comprobantes RG90 vía HTTP en segundos sin esperas ni navegadores virtuales pesados.
            </p>
          </div>
          <span className="self-start md:self-auto px-3 py-1 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800 flex items-center gap-1.5">
            <ShieldCheck size={14} />
            DNIT REA v2.0 Activo
          </span>
        </div>

        {/* Pasos y Bookmarklet */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-1 p-4 rounded-xl bg-white dark:bg-gray-800/80 border border-gray-200/80 dark:border-gray-700/80 flex flex-col justify-between shadow-sm">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Bookmark size={18} className="text-primary" />
                <h4 className="text-sm font-bold text-gray-900 dark:text-white">
                  Conector 1-Clic
                </h4>
              </div>
              <p className="text-xs text-gray-600 dark:text-gray-300 mb-3 leading-relaxed">
                Arrastrá este botón a tu barra de marcadores del navegador para sincronizar con 1 solo clic desde Marangatú:
              </p>

              <div className="my-3 text-center">
                <a
                  href={bookmarkletCode}
                  onClick={(e) => {
                    e.preventDefault()
                    copiarCodigoBookmarklet()
                  }}
                  title="Arrastrar a la barra de marcadores o hacer clic para copiar"
                  className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-white font-bold text-xs shadow-md hover:bg-primary/90 transition-all cursor-grab active:cursor-grabbing border border-primary/30"
                >
                  <Bookmark size={14} />
                  ⚡ Inteliaudit 1-Clic
                </a>
              </div>
            </div>

            <button
              type="button"
              onClick={copiarCodigoBookmarklet}
              className="mt-2 w-full flex items-center justify-center gap-1.5 py-1.5 text-[11px] font-semibold text-gray-600 dark:text-gray-300 bg-gray-100 dark:bg-gray-700 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
            >
              {copiadoBookmarklet ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />}
              {copiadoBookmarklet ? '¡Copiado!' : 'Copiar script JS'}
            </button>
          </div>

          <div className="lg:col-span-2 p-4 rounded-xl bg-white dark:bg-gray-800/80 border border-gray-200/80 dark:border-gray-700/80 shadow-sm space-y-3">
            <h4 className="text-xs font-bold text-gray-800 dark:text-gray-200 uppercase tracking-wider">
              Instrucciones de Uso
            </h4>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900/50 border border-gray-100 dark:border-gray-800 text-xs">
                <span className="inline-block w-5 h-5 rounded-full bg-primary/10 text-primary font-bold text-center leading-5 mb-1.5">1</span>
                <p className="font-semibold text-gray-800 dark:text-gray-200">Instalá el marcador</p>
                <p className="text-[11px] text-gray-500 mt-1">Arrastrá el botón azul a tu barra de favoritos o copiá el código.</p>
              </div>
              <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900/50 border border-gray-100 dark:border-gray-800 text-xs">
                <span className="inline-block w-5 h-5 rounded-full bg-primary/10 text-primary font-bold text-center leading-5 mb-1.5">2</span>
                <p className="font-semibold text-gray-800 dark:text-gray-200">Iniciá Marangatú</p>
                <p className="text-[11px] text-gray-500 mt-1">Accedé normalmente con el RUC y clave de tu cliente en DNIT.</p>
              </div>
              <div className="p-3 rounded-lg bg-gray-50 dark:bg-gray-900/50 border border-gray-100 dark:border-gray-800 text-xs">
                <span className="inline-block w-5 h-5 rounded-full bg-primary/10 text-primary font-bold text-center leading-5 mb-1.5">3</span>
                <p className="font-semibold text-gray-800 dark:text-gray-200">1 Clic y listo</p>
                <p className="text-[11px] text-gray-500 mt-1">Presioná el marcador: captura la sesión y descarga los datos en segundos.</p>
              </div>
            </div>
          </div>
        </div>

        {/* Formulario de Sincronización Manual / Confirmación */}
        <div className="p-4 rounded-xl bg-white dark:bg-gray-800/80 border border-gray-200/80 dark:border-gray-700/80 shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-gray-700 dark:text-gray-300 flex items-center gap-1.5">
              <Key size={14} className="text-primary" />
              Token / Cookie de Sesión Marangatú
            </span>
            {sesionInfo && (
              <span className={`px-2 py-0.5 text-[11px] font-bold rounded-md ${
                sesionInfo.activa
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-400'
                  : 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
              }`}>
                {sesionInfo.activa ? `Sesión Activa: ${sesionInfo.ruc || clienteRuc}` : 'Sesión Expirada'}
              </span>
            )}
          </div>

          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Pegar JSESSIONID o cookie de Marangatú (ej: JSESSIONID=abc123xyz...)"
              value={sessionCookie}
              onChange={(e) => setSessionCookie(e.target.value)}
              className="flex-1 px-3 py-2 text-xs border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 font-mono"
            />
            <button
              type="button"
              onClick={() => verificarSesionHttp()}
              disabled={verificandoSesion || !sessionCookie.trim()}
              className="px-3 py-2 text-xs font-bold rounded-lg border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-600 disabled:opacity-50 flex items-center gap-1.5 transition-colors"
            >
              {verificandoSesion ? <RefreshCw size={12} className="animate-spin" /> : <ShieldCheck size={14} />}
              Verificar
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                Período desde
              </label>
              <input
                type="month"
                value={periodoDesde}
                onChange={(e) => setPeriodoDesde(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
                Período hasta
              </label>
              <input
                type="month"
                value={periodoHasta}
                onChange={(e) => setPeriodoHasta(e.target.value)}
                className="w-full px-3 py-2 text-xs border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>
          </div>

          <button
            type="button"
            onClick={sincronizarMarangatuHttp}
            disabled={sincronizandoRea || !sessionCookie.trim()}
            className="w-full py-2.5 px-4 bg-primary text-white font-bold text-xs rounded-xl shadow hover:bg-primary/90 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
          >
            {sincronizandoRea ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
                Sincronizando comprobantes vía protocolo REA...
              </>
            ) : (
              <>
                <Zap size={14} />
                Sincronizar Comprobantes RG90 Ahora
                <ArrowRight size={14} />
              </>
            )}
          </button>

          {resultadoSync && (
            <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800 text-emerald-900 dark:text-emerald-300 text-xs">
              <div className="flex items-center gap-2 font-bold mb-1">
                <CheckCircle size={15} className="text-emerald-600" />
                {resultadoSync.mensaje}
              </div>
              <div className="grid grid-cols-3 gap-2 mt-2 pt-2 border-t border-emerald-200/60 dark:border-emerald-800/60 text-center">
                <div>
                  <p className="text-[10px] text-emerald-600 uppercase font-semibold">Total Importados</p>
                  <p className="text-base font-black text-emerald-700">{resultadoSync.total_importados}</p>
                </div>
                <div>
                  <p className="text-[10px] text-emerald-600 uppercase font-semibold">Compras</p>
                  <p className="text-base font-black text-emerald-700">{resultadoSync.importados_compras}</p>
                </div>
                <div>
                  <p className="text-[10px] text-emerald-600 uppercase font-semibold">Ventas</p>
                  <p className="text-base font-black text-emerald-700">{resultadoSync.importados_ventas}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* SECCIÓN 2: WORKER DE BACKGROUND Y TAREAS EN COLA */}
      <div className="card p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Download size={18} className="text-primary" />
            Descargas Programadas y Workers en Background
          </h3>
          <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400">
            Batch Asíncrono
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              Tipo de descarga
            </label>
            <select
              value={tipoJob}
              onChange={(e) => setTipoJob(e.target.value)}
              className="w-full px-3 py-2 text-xs border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            >
              <option value="scraper_rg90">RG90 (Comprobantes IVA)</option>
              <option value="scraper_hechauka">HECHAUKA (Información de terceros)</option>
              <option value="scraper_dj">Declaraciones Juradas (Form. 120 / 500)</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1">
              Cliente RUC
            </label>
            <input
              type="text"
              value={clienteRuc}
              disabled
              className="w-full px-3 py-2 text-xs border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400"
            />
          </div>
        </div>

        <button
          onClick={encolarJob}
          disabled={encolando}
          className="w-full px-4 py-2 bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 text-gray-800 dark:text-gray-200 text-xs font-bold rounded-lg border border-gray-300 dark:border-gray-700 flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
        >
          {encolando ? <RefreshCw size={14} className="animate-spin" /> : <Play size={14} />}
          Encolar Tarea en Worker de Background
        </button>
      </div>

      {/* SECCIÓN 3: LISTA DE JOBS EN COLA */}
      <div className="card">
        <div className="p-5 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-bold text-gray-900 dark:text-white">
            Historial de Jobs en Cola
          </h3>
        </div>

        {loading ? (
          <div className="p-12 text-center">
            <RefreshCw size={24} className="animate-spin text-gray-400 mx-auto mb-2" />
            <p className="text-xs text-gray-500">Cargando tareas...</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-8 text-center text-xs text-gray-500">
            No hay tareas en segundo plano registradas.
          </div>
        ) : (
          <div className="divide-y divide-gray-100 dark:divide-gray-800">
            {jobs.slice(0, 10).map((job) => (
              <div key={job.id} className="p-4 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  {getEstadoIcon(job.estado)}
                  <div>
                    <p className="text-xs font-bold text-gray-800 dark:text-gray-200">{job.tipo}</p>
                    <p className="text-[10px] text-gray-400">
                      Creado: {new Date(job.creado_en).toLocaleString('es-PY')}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className={`px-2 py-0.5 text-[10px] font-bold rounded-full ${getEstadoColor(job.estado)}`}>
                    {job.estado}
                  </span>
                  {job.estado === 'pendiente' && (
                    <button
                      onClick={() => cancelarJob(job.id)}
                      className="text-xs text-red-500 hover:text-red-700"
                    >
                      Cancelar
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
