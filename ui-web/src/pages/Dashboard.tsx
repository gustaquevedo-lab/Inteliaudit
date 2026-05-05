import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Building2, FileSearch, TrendingUp, Clock, ChevronRight, Plus, Zap } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import KPICard from '../components/KPICard'
import { BadgeEstadoAuditoria, BadgeRiesgo } from '../components/Badge'
import { pyg, rangoPeríodos, fecha } from '../utils/formatters'
import type { Cliente, EstadoAuditoria } from '../api/types'

interface AuditoriaResumen {
  id: string
  cliente_id: string
  cliente_nombre: string
  periodo_desde: string
  periodo_hasta: string
  tipo_encargo: string
  impuestos: string[]
  estado: EstadoAuditoria
  auditor?: string
  fecha_inicio?: string
}

interface GlobalStats {
  auditorias_totales: number
  auditorias_activas: number
  riesgo_total_detectado: number
  total_hallazgos: number
  distribucion_impuestos: Record<string, number>
}

interface DashboardData {
  clientes: Cliente[]
  auditorias: AuditoriaResumen[]
  stats: GlobalStats
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      api.get<Cliente[]>('/clientes'),
      api.get<AuditoriaResumen[]>('/auditorias'),
      api.get<GlobalStats>('/auditorias/stats/global')
    ]).then(([clientes, auditorias, stats]) => {
      setData({ clientes, auditorias, stats })
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
  )

  const recientes = [...(data?.auditorias ?? [])].sort((a, b) =>
    (b.fecha_inicio ?? '').localeCompare(a.fecha_inicio ?? '')
  ).slice(0, 8)

  return (
    <div className="space-y-8 animate-fade-in pb-12">
      {/* Welcome & Firm Branding */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
             <span className="px-2 py-0.5 bg-primary/10 text-primary text-[10px] font-black rounded uppercase tracking-widest">
               {user?.firma_plan}
             </span>
             <span className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">
               {user?.firma_nombre}
             </span>
          </div>
          <h1 className="text-3xl font-black text-gray-900 dark:text-white uppercase tracking-tighter">
            Consola de Control
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/clientes')} className="btn-ghost border-gray-100 dark:border-gray-800">
            Gestionar Clientes
          </button>
          <button onClick={() => navigate('/auditorias/nueva')} className="btn-primary shadow-lg shadow-primary/20">
            <Plus size={16} />
            Nueva auditoría
          </button>
        </div>
      </div>

      {/* Advanced KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card p-6 bg-gradient-to-br from-primary to-primary-dark text-white border-0 shadow-xl shadow-primary/20">
           <p className="text-[10px] font-black uppercase tracking-widest opacity-80 mb-1">Riesgo Fiscal Detectado</p>
           <h3 className="text-3xl font-black tracking-tighter mb-4">{pyg(data?.stats.riesgo_total_detectado ?? 0)}</h3>
           <div className="flex items-center gap-2 text-[10px] font-bold bg-white/10 w-fit px-2 py-1 rounded-lg">
             <AlertTriangle size={12} /> {data?.stats.total_hallazgos} hallazgos activos
           </div>
        </div>

        <KPICard
          label="Auditorías en Curso"
          value={data?.stats.auditorias_activas ?? 0}
          icon={<FileSearch size={22} className="text-secondary" />}
          iconBg="bg-secondary/10 dark:bg-secondary/20"
        />

        <KPICard
          label="Cartera de Clientes"
          value={data?.clientes.length ?? 0}
          icon={<Building2 size={22} className="text-accent" />}
          iconBg="bg-accent/10 dark:bg-accent/20"
          onClick={() => navigate('/clientes')}
        />

        <div className="card p-6 flex flex-col justify-between">
           <p className="section-label mb-2">Distribución de Riesgo</p>
           <div className="flex gap-1 h-3 rounded-full overflow-hidden bg-gray-100 dark:bg-gray-800">
             {Object.entries(data?.stats.distribucion_impuestos ?? {}).map(([imp, cant], i) => (
               <div 
                 key={imp}
                 title={`${imp}: ${cant}`}
                 className={`h-full ${['bg-primary', 'bg-secondary', 'bg-accent', 'bg-amber-500'][i % 4]}`}
                 style={{ width: `${(cant / (data?.stats.total_hallazgos || 1)) * 100}%` }}
               />
             ))}
           </div>
           <div className="flex flex-wrap gap-x-3 gap-y-1 mt-3">
             {Object.keys(data?.stats.distribucion_impuestos ?? {}).slice(0,3).map((imp, i) => (
                <div key={imp} className="flex items-center gap-1.5">
                   <span className={`w-1.5 h-1.5 rounded-full ${['bg-primary', 'bg-secondary', 'bg-accent', 'bg-amber-500'][i % 4]}`} />
                   <span className="text-[9px] font-black text-gray-500 uppercase">{imp}</span>
                </div>
             ))}
           </div>
        </div>
      </div>

      {/* Main Content Split */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        
        {/* Recent Audits Table */}
        <div className="xl:col-span-2 space-y-4">
           <div className="flex items-center justify-between px-2">
             <h2 className="text-sm font-black text-gray-900 dark:text-white uppercase tracking-widest flex items-center gap-2">
               <Clock size={16} className="text-primary" /> Actividad Reciente
             </h2>
           </div>
           
           <div className="card overflow-hidden border-gray-100 dark:border-gray-800">
             {recientes.length === 0 ? (
               <div className="py-20 flex flex-col items-center text-gray-400">
                  <FileSearch size={40} className="opacity-20 mb-4" />
                  <p className="text-sm font-bold uppercase tracking-widest">Sin actividad aún</p>
               </div>
             ) : (
               <div className="overflow-x-auto">
                 <table className="w-full">
                    <thead className="bg-gray-50 dark:bg-gray-800/50">
                       <tr>
                          <th className="px-6 py-4 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest">Cliente</th>
                          <th className="px-6 py-4 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest">Período</th>
                          <th className="px-6 py-4 text-left text-[10px] font-black text-gray-400 uppercase tracking-widest">Estado</th>
                          <th className="px-6 py-4"></th>
                       </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-50 dark:divide-gray-800">
                       {recientes.map(a => (
                         <tr 
                           key={a.id} 
                           className="hover:bg-gray-50 dark:hover:bg-gray-800/30 transition-colors cursor-pointer group"
                           onClick={() => navigate(`/auditorias/${a.id}`)}
                         >
                            <td className="px-6 py-4 font-bold text-gray-900 dark:text-white text-sm">{a.cliente_nombre || a.cliente_id.slice(0,8)}</td>
                            <td className="px-6 py-4 text-xs text-gray-500">{rangoPeríodos(a.periodo_desde, a.periodo_hasta)}</td>
                            <td className="px-6 py-4">
                               <BadgeEstadoAuditoria estado={a.estado} />
                            </td>
                            <td className="px-6 py-4 text-right">
                               <ChevronRight size={16} className="text-gray-300 group-hover:text-primary transition-colors" />
                            </td>
                         </tr>
                       ))}
                    </tbody>
                 </table>
               </div>
             )}
           </div>
        </div>

        {/* Sidebar: Intelligent Insights */}
        <div className="space-y-6">
           <div className="card p-6 bg-gray-900 text-white border-0 shadow-2xl relative overflow-hidden">
              {/* Decorative Glow */}
              <div className="absolute -top-10 -right-10 w-32 h-32 bg-primary/20 rounded-full blur-3xl" />
              
              <div className="relative z-10">
                 <h3 className="text-xs font-black uppercase tracking-[0.2em] text-primary mb-4 flex items-center gap-2">
                   <Zap size={14} /> AI Insights
                 </h3>
                 <div className="space-y-4">
                    <div className="p-4 bg-white/5 rounded-2xl border border-white/10">
                       <p className="text-[11px] leading-relaxed text-gray-300 italic">
                         "Se ha detectado un incremento del 24% en discrepancias de IVA en el último trimestre. Se sugiere revisar proveedores con RUC bloqueado."
                       </p>
                    </div>
                    <button className="w-full btn-primary py-3 text-[10px]">
                       Ejecutar Análisis Predictivo
                    </button>
                 </div>
              </div>
           </div>

           {/* Legal Framework Status */}
           <div className="card p-6">
              <h3 className="section-label mb-4">Marco Legal & Cumplimiento</h3>
              <div className="space-y-3">
                 {[
                   { label: 'NIA 230', status: 'Cumplido', color: 'text-green-500' },
                   { label: 'NIA 500', status: 'Cumplido', color: 'text-green-500' },
                   { label: 'COSO 2013', status: 'Activo', color: 'text-blue-500' },
                   { label: 'SIFEN v.2.0', status: 'Sincronizado', color: 'text-primary' },
                 ].map(item => (
                   <div key={item.label} className="flex justify-between items-center py-2 border-b border-gray-50 dark:border-gray-800 last:border-0">
                      <span className="text-xs font-bold text-gray-700 dark:text-gray-300">{item.label}</span>
                      <span className={`text-[10px] font-black uppercase ${item.color}`}>{item.status}</span>
                   </div>
                 ))}
              </div>
           </div>
        </div>

      </div>
    </div>
  )
}
