import { useState, useEffect } from 'react'
import { Play, Pause, RefreshCw, CheckCircle, XCircle, Clock, Download, AlertTriangle } from 'lucide-react'
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
    // Polling cada 5 segundos
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
        return 'bg-gray-100 text-gray-700'
      case 'ejecutando':
        return 'bg-blue-100 text-blue-700'
      case 'completado':
        return 'bg-green-100 text-green-700'
      case 'error':
        return 'bg-red-100 text-red-700'
      case 'cancelado':
        return 'bg-gray-100 text-gray-500'
      default:
        return 'bg-gray-100 text-gray-700'
    }
  }

  const getTipoLabel = (tipo: string) => {
    switch (tipo) {
      case 'scraper_rg90':
        return 'Descargar RG90'
      case 'scraper_hechauka':
        return 'Descargar HECHAUKA'
      case 'scraper_dj':
        return 'Descargar Declaraciones'
      default:
        return tipo
    }
  }

  return (
    <div className="space-y-6">
      {/* Panel de encolamiento */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Download size={20} className="text-primary" />
          Descargar de Marangatú
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Tipo de descarga
            </label>
            <select
              value={tipoJob}
              onChange={(e) => setTipoJob(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            >
              <option value="scraper_rg90">RG90 (Comprobantes IVA)</option>
              <option value="scraper_hechauka">HECHAUKA (Información de terceros)</option>
              <option value="scraper_dj">Declaraciones Juradas</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Cliente
            </label>
            <input
              type="text"
              value={clienteRuc}
              disabled
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Período desde
            </label>
            <input
              type="month"
              value={periodoDesde}
              onChange={(e) => setPeriodoDesde(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Período hasta
            </label>
            <input
              type="month"
              value={periodoHasta}
              onChange={(e) => setPeriodoHasta(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            />
          </div>
        </div>

        <button
          onClick={encolarJob}
          disabled={encolando}
          className="w-full px-4 py-2 bg-primary text-white rounded-lg hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {encolando ? (
            <>
              <RefreshCw size={16} className="animate-spin" />
              Encolando...
            </>
          ) : (
            <>
              <Play size={16} />
              Encolar descarga
            </>
          )}
        </button>

        <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg">
          <p className="text-sm text-blue-700 dark:text-blue-300">
            <strong>Nota:</strong> Las descargas se ejecutan en background. El worker procesa un job a la vez.
            Podés ver el progreso en la lista de abajo.
          </p>
        </div>
      </div>

      {/* Lista de jobs */}
      <div className="card">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">
            Jobs en cola y ejecutados
          </h3>
        </div>

        {loading ? (
          <div className="p-12 text-center">
            <RefreshCw size={32} className="animate-spin text-gray-400 mx-auto mb-3" />
            <p className="text-gray-500">Cargando jobs...</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-12 text-center">
            <Clock size={32} className="text-gray-400 mx-auto mb-3" />
            <p className="text-gray-500">No hay jobs en cola</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-700">
            {jobs.map((job) => (
              <div key={job.id} className="p-6">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    {getEstadoIcon(job.estado)}
                    <div>
                      <p className="font-semibold text-gray-900 dark:text-white">
                        {getTipoLabel(job.tipo)}
                      </p>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {job.params?.cliente_ruc} • {job.params?.periodo_desde} a {job.params?.periodo_hasta}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${getEstadoColor(job.estado)}`}>
                      {job.estado}
                    </span>
                    {(job.estado === 'pendiente' || job.estado === 'ejecutando') && (
                      <button
                        onClick={() => cancelarJob(job.id)}
                        className="px-3 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium hover:bg-red-200"
                      >
                        Cancelar
                      </button>
                    )}
                  </div>
                </div>

                {/* Barra de progreso */}
                {job.estado === 'ejecutando' && (
                  <div className="mb-3">
                    <div className="flex items-center justify-between text-sm text-gray-600 dark:text-gray-400 mb-1">
                      <span>Progreso</span>
                      <span>{job.progreso}%</span>
                    </div>
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                      <div
                        className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${job.progreso}%` }}
                      />
                    </div>
                  </div>
                )}

                {/* Timestamps */}
                <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                  <p>Creado: {new Date(job.creado_en).toLocaleString('es-PY')}</p>
                  {job.iniciado_en && (
                    <p>Iniciado: {new Date(job.iniciado_en).toLocaleString('es-PY')}</p>
                  )}
                  {job.completado_en && (
                    <p>Completado: {new Date(job.completado_en).toLocaleString('es-PY')}</p>
                  )}
                  {job.reintentos > 0 && (
                    <p className="text-yellow-600">
                      <AlertTriangle size={12} className="inline" /> Reintentos: {job.reintentos}
                    </p>
                  )}
                </div>

                {/* Error message */}
                {job.error_msg && (
                  <div className="mt-3 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg">
                    <p className="text-sm text-red-700 dark:text-red-300">
                      <strong>Error:</strong> {job.error_msg}
                    </p>
                  </div>
                )}

                {/* Resultado */}
                {job.resultado && job.estado === 'completado' && (
                  <div className="mt-3 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                    <p className="text-sm text-green-700 dark:text-green-300">
                      <strong>Resultado:</strong>
                      {job.resultado.total_registros && (
                        <span> {job.resultado.total_registros} registros procesados</span>
                      )}
                      {job.resultado.archivos && (
                        <span> {job.resultado.archivos.length} archivos descargados</span>
                      )}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
