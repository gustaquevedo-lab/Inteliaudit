import { useEffect, useState } from 'react'
import { Activity, Play, XOctagon, RefreshCw, AlertCircle, CheckCircle, Loader } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import { fecha } from '../../utils/formatters'

interface Job {
  id: string
  tipo: string
  estado: string
  progreso: number
  creado_en: string
  iniciado_en: string | null
  completado_en: string | null
  error_msg: string | null
  reintentos: number
  params: any
  resultado: any
}

export default function JobsMonitor() {
  const { success, error } = useToast()
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [tipoFilter, setTipoFilter] = useState('')
  const [estadoFilter, setEstadoFilter] = useState('')

  const load = () => {
    api.get<Job[]>('/jobs')
      .then(setJobs)
      .catch(() => error('Error al cargar la cola de tareas'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    load()
    // Auto-refresh every 5 seconds if there are active running or pending jobs
    const interval = setInterval(() => {
      const active = jobs.some(j => ['pendiente', 'ejecutando', 'iniciando'].includes(j.estado))
      if (active) {
        load()
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [jobs])

  const cancelar = async (id: string) => {
    try {
      await api.post(`/jobs/${id}/cancelar`, {})
      success('Tarea cancelada correctamente')
      load()
    } catch (e: unknown) {
      error(e instanceof Error ? e.message : 'Error al cancelar la tarea')
    }
  }

  const filtered = jobs.filter(j => {
    if (tipoFilter && j.tipo !== tipoFilter) return false
    if (estadoFilter && j.estado !== estadoFilter) return false
    return true
  })

  const jobTipos = [...new Set(jobs.map(j => j.tipo))]

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-gray-900 dark:text-white uppercase tracking-tight flex items-center gap-2">
            <Activity size={24} className="text-primary" />
            Cola de Tareas
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Monitoreo en tiempo real de los procesos automatizados y descargas
          </p>
        </div>
        <button onClick={load} className="btn-outline py-2 px-3">
          <RefreshCw size={15} /> Actualizar
        </button>
      </div>

      {/* Filters */}
      <div className="card p-4 grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div>
          <label className="input-label">Tipo de Tarea</label>
          <select className="input-field" value={tipoFilter} onChange={e => setTipoFilter(e.target.value)}>
            <option value="">Todos los tipos</option>
            {jobTipos.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div>
          <label className="input-label">Estado</label>
          <select className="input-field" value={estadoFilter} onChange={e => setEstadoFilter(e.target.value)}>
            <option value="">Todos los estados</option>
            <option value="pendiente">Pendiente</option>
            <option value="ejecutando">Ejecutando</option>
            <option value="completado">Completado</option>
            <option value="error">Con Error</option>
            <option value="cancelado">Cancelado</option>
          </select>
        </div>
      </div>

      {/* Jobs list */}
      <div className="space-y-4">
        {loading && jobs.length === 0 ? (
          <div className="flex justify-center py-16">
            <div className="w-7 h-7 border-4 border-primary border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="card p-12 text-center text-gray-500">
            No se encontraron tareas registradas con los filtros actuales.
          </div>
        ) : (
          filtered.map(job => (
            <div key={job.id} className="card p-5 flex flex-col md:flex-row gap-4 justify-between items-start md:items-center">
              <div className="space-y-2 flex-1 min-w-0">
                <div className="flex items-center gap-3 flex-wrap">
                  <span className="font-mono font-bold text-sm text-gray-900 dark:text-white uppercase tracking-tight bg-gray-100 dark:bg-gray-800 px-2.5 py-1 rounded-lg">
                    {job.tipo.replace('scraper_', 'Descarga · ')}
                  </span>
                  
                  {job.estado === 'completado' && (
                    <span className="badge-bajo"><CheckCircle size={10} /> Completado</span>
                  )}
                  {job.estado === 'ejecutando' && (
                    <span className="badge-info animate-pulse"><Loader size={10} className="animate-spin" /> Ejecutando ({job.progreso}%)</span>
                  )}
                  {job.estado === 'pendiente' && (
                    <span className="badge-gray"><RefreshCw size={10} /> Pendiente</span>
                  )}
                  {job.estado === 'error' && (
                    <span className="badge-alto"><AlertCircle size={10} /> Error</span>
                  )}
                  {job.estado === 'cancelado' && (
                    <span className="px-2 py-1 rounded-lg text-[10px] font-bold bg-gray-100 text-gray-500">Cancelado</span>
                  )}

                  <span className="text-[10px] text-gray-400 font-mono">ID: {job.id.slice(0, 8)}</span>
                </div>

                <div className="text-xs text-gray-600 dark:text-gray-400 space-y-1">
                  <p>
                    <span className="font-bold">Creado:</span> {fecha(job.creado_en)}
                    {job.iniciado_en && <> | <span className="font-bold">Iniciado:</span> {fecha(job.iniciado_en)}</>}
                    {job.completado_en && <> | <span className="font-bold">Fin:</span> {fecha(job.completado_en)}</>}
                  </p>
                  
                  {job.params && (
                    <p className="font-mono text-[10px] bg-slate-50 dark:bg-slate-900/50 p-2 rounded-lg break-all">
                      <span className="font-sans font-bold">Parámetros:</span> {JSON.stringify(job.params)}
                    </p>
                  )}

                  {job.error_msg && (
                    <p className="text-red-500 font-mono text-[10px] bg-red-50 dark:bg-red-950/20 p-2 rounded-lg">
                      <span className="font-sans font-bold text-red-700 dark:text-red-400">Error:</span> {job.error_msg}
                    </p>
                  )}
                </div>
              </div>

              {/* Progress bar & control actions */}
              <div className="flex flex-col items-stretch md:items-end gap-3 w-full md:w-auto shrink-0">
                {job.estado === 'ejecutando' && (
                  <div className="w-full md:w-48 bg-gray-200 dark:bg-gray-700 h-2 rounded-full overflow-hidden">
                    <div className="bg-primary h-full transition-all duration-300" style={{ width: `${job.progreso}%` }} />
                  </div>
                )}

                {['pendiente', 'ejecutando'].includes(job.estado) && (
                  <button 
                    onClick={() => cancelar(job.id)} 
                    className="flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg border border-red-200 text-red-600 hover:bg-red-50 text-xs font-bold transition-all w-full md:w-auto"
                  >
                    <XOctagon size={13} /> Cancelar Tarea
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
