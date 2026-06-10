import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, Building2, FileSearch, Clock, ChevronRight, Plus, BarChart3, PieChart,
  TrendingUp, Users, Activity, Shield, XCircle, CreditCard,
} from 'lucide-react'
import {
  PieChart as RechartsPieChart, Pie, Cell, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
} from 'recharts'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import KPICard from '../components/KPICard'
import { pyg } from '../utils/formatters'
import type { Cliente, EstadoAuditoria } from '../api/types'

interface DashboardData {
  kpis: {
    total_contingencia: number
    auditorias_activas: number
    auditorias_cerradas: number
    hallazgos_pendientes: number
    hallazgos_alto_riesgo: number
    clientes_total: number
  }
  hallazgos_por_riesgo: { nivel: string; cantidad: number; monto: number }[]
  hallazgos_por_impuesto: { impuesto: string; cantidad: number }[]
  top_clientes_contingencia: { razon_social: string; ruc: string; contingencia: number }[]
  actividad_reciente: { accion: string; usuario: string; timestamp: string; auditoria: string; modulo: string }[]
  tendencia_mensual: { mes: string; hallazgos: number; contingencia: number }[]
}

const COLORS_RISK = { alto: '#E53E3E', medio: '#D97706', bajo: '#22C47E' }
const COLORS_IMP = ['#2E84F0', '#8B5CF6', '#22C47E', '#D97706', '#E53E3E', '#EC4899']

export default function Dashboard() {
  const { user, planInfo } = useAuth()
  const navigate = useNavigate()
  const [data, setData] = useState<DashboardData | null>(null)
  const [clientes, setClientes] = useState<Cliente[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [suscripcion, setSuscripcion] = useState<{ plan_actual: string; en_trial: boolean; trial_expirado: boolean; suscripcion_activa: boolean; dias_restantes: number } | null>(null)

  useEffect(() => {
    Promise.all([
      api.get<DashboardData>('/dashboard'),
      api.get<Cliente[]>('/clientes'),
      api.get('/suscripciones/mi-plan').then(setSuscripcion).catch(() => {}),
    ])
      .then(([d, c]) => { setData(d); setClientes(c) })
      .catch(e => setError(e instanceof Error ? e.message : 'Error al cargar'))
      .finally(() => setLoading(false))
  }, [])

  const isTrial = user?.en_trial
  const diasRestantes = user?.dias_trial_restantes ?? 0
  const trialExpirado = isTrial && diasRestantes <= 0

  if (loading) return (
    <div className="flex items-center justify-center py-24">
      <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
    </div>
  )

  if (error) return (
    <div className="card p-6 text-center text-red-500 text-sm font-bold">{error}</div>
  )

  const kpis = data?.kpis
  const hasData = kpis && (kpis.clientes_total > 0 || kpis.auditorias_activas > 0 || kpis.total_contingencia > 0)
  const maxContingencia = data?.top_clientes_contingencia?.[0]?.contingencia ?? 1
  const riesgoData = data?.hallazgos_por_riesgo?.map(r => ({
    name: r.nivel.charAt(0).toUpperCase() + r.nivel.slice(1),
    value: r.cantidad,
    monto: r.monto,
  })) ?? []
  const impuestoData = data?.hallazgos_por_impuesto?.map(r => ({
    name: r.impuesto,
    cantidad: r.cantidad,
  })) ?? []

  return (
    <div className="space-y-6 pb-12 animate-fade-in">
      {/* Header */}
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
            Dashboard
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/clientes')} className="btn-ghost border-gray-100 dark:border-gray-800">
            <Building2 size={14} /> Clientes
          </button>
          <button onClick={() => navigate('/auditorias/nueva')} className="btn-primary shadow-lg shadow-primary/20">
            <Plus size={16} /> Nueva auditoria
          </button>
        </div>
      </div>

      {/* Trial Banner */}
      {isTrial && (
        <div className={`p-4 rounded-2xl border flex items-center justify-between gap-4 ${
          trialExpirado
            ? 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800'
            : 'bg-gradient-to-r from-blue-50 to-green-50 dark:from-blue-900/10 dark:to-green-900/10 border-blue-200 dark:border-blue-800/40'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-xl ${trialExpirado ? 'bg-red-100 dark:bg-red-900/20' : 'bg-primary/10'}`}>
              {trialExpirado ? <XCircle size={18} className="text-red-500" /> : <Clock size={18} className="text-primary" />}
            </div>
            <div>
              <p className={`text-sm font-bold ${trialExpirado ? 'text-red-700 dark:text-red-300' : 'text-gray-900 dark:text-white'}`}>
                {trialExpirado ? 'Trial expirado' : `Trial Pro — Te quedan ${diasRestantes} dia${diasRestantes !== 1 ? 's' : ''}`}
              </p>
              <p className={`text-xs ${trialExpirado ? 'text-red-600 dark:text-red-400' : 'text-gray-500 dark:text-gray-400'}`}>
                {trialExpirado ? 'Elegi un plan para continuar' : 'Disfruta del plan Pro durante tu prueba'}
              </p>
            </div>
          </div>
          <a href="https://inteliaudit.com/#precios" target="_blank" rel="noopener noreferrer"
            className={`py-2 px-4 rounded-xl text-xs font-bold whitespace-nowrap ${trialExpirado ? 'bg-red-500 text-white hover:bg-red-600' : 'btn-primary'}`}>
            Ver planes
          </a>
        </div>
      )}

      {/* Subscription alert */}
      {suscripcion && !suscripcion.en_trial && !suscripcion.suscripcion_activa && (
        <div className="p-4 rounded-2xl border bg-amber-50 dark:bg-amber-900/10 border-amber-200 dark:border-amber-800 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-amber-100 dark:bg-amber-900/20">
              <CreditCard size={18} className="text-amber-600" />
            </div>
            <div>
              <p className="text-sm font-bold text-amber-800 dark:text-amber-300">Sin suscripcion activa</p>
              <p className="text-xs text-amber-600 dark:text-amber-400">Elegi un plan para continuar usando Inteliaudit</p>
            </div>
          </div>
          <a href="/app/planes" className="py-2 px-4 rounded-xl bg-amber-500 text-white text-xs font-bold hover:bg-amber-600 shrink-0">Ver planes</a>
        </div>
      )}

      {!hasData ? (
        /* Empty State */
        <div className="card p-16 flex flex-col items-center text-center">
          <div className="w-20 h-20 rounded-2xl bg-gray-100 dark:bg-gray-800 flex items-center justify-center mb-6">
            <BarChart3 size={40} className="text-gray-300 dark:text-gray-600" />
          </div>
          <h2 className="text-xl font-black text-gray-900 dark:text-white mb-2">Bienvenido a Inteliaudit</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md mb-8">
            Crea tu primer cliente para empezar a auditar. Despues importa archivos RG90 y ejecuta los analisis automaticos.
          </p>
          <button onClick={() => navigate('/clientes')} className="btn-primary py-3 px-6 text-sm flex items-center gap-2">
            <Plus size={16} /> Crear mi primer cliente
          </button>
        </div>
      ) : (
        <>
          {/* KPI Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
            <KPICard
              label="Contingencia Total"
              value={pyg(kpis!.total_contingencia)}
              icon={<AlertTriangle size={20} className="text-red-500" />}
              iconBg="bg-red-50 dark:bg-red-900/10"
              subtitle="Hallazgos activos"
            />
            <KPICard
              label="Auditorias Activas"
              value={kpis!.auditorias_activas}
              icon={<Activity size={20} className="text-primary" />}
              iconBg="bg-primary/10"
              subtitle={`${kpis!.auditorias_cerradas} cerradas`}
            />
            <KPICard
              label="Hallazgos Pendientes"
              value={kpis!.hallazgos_pendientes}
              icon={<Clock size={20} className="text-amber-500" />}
              iconBg="bg-amber-50 dark:bg-amber-900/10"
              subtitle={`${kpis!.hallazgos_alto_riesgo} de alto riesgo`}
            />
            <KPICard
              label="Clientes"
              value={kpis!.clientes_total}
              icon={<Building2 size={20} className="text-green-500" />}
              iconBg="bg-green-50 dark:bg-green-900/10"
              onClick={() => navigate('/clientes')}
            />
            <KPICard
              label="Hallazgos Alto Riesgo"
              value={kpis!.hallazgos_alto_riesgo}
              icon={<Shield size={20} className="text-red-500" />}
              iconBg="bg-red-50 dark:bg-red-900/10"
            />
            <KPICard
              label="Total Hallazgos"
              value={(data!.hallazgos_por_riesgo?.reduce((s, r) => s + r.cantidad, 0) ?? 0)}
              icon={<FileSearch size={20} className="text-secondary" />}
              iconBg="bg-secondary/10"
            />
          </div>

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Doughnut: Hallazgos por riesgo */}
            <div className="card p-6">
              <div className="flex items-center gap-2 mb-6">
                <PieChart size={16} className="text-primary" />
                <p className="font-black text-sm uppercase tracking-wide">Hallazgos por nivel de riesgo</p>
              </div>
              {riesgoData.length > 0 ? (
                <div className="flex items-center gap-6">
                  <div className="w-48 h-48 shrink-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <RechartsPieChart>
                        <Pie data={riesgoData} cx="50%" cy="50%" innerRadius={55} outerRadius={80} dataKey="value" paddingAngle={3}>
                          {riesgoData.map((entry) => (
                            <Cell key={entry.name} fill={COLORS_RISK[entry.name.toLowerCase() as keyof typeof COLORS_RISK] || '#94a3b8'} />
                          ))}
                        </Pie>
                        <Tooltip formatter={(value: number, name: string) => [`${value} hallazgos`, name]} />
                      </RechartsPieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="space-y-3 flex-1">
                    {riesgoData.map(r => {
                      const total = riesgoData.reduce((s, x) => s + x.value, 0)
                      const pct = total > 0 ? Math.round((r.value / total) * 100) : 0
                      const color = COLORS_RISK[r.name.toLowerCase() as keyof typeof COLORS_RISK] || '#94a3b8'
                      return (
                        <div key={r.name} className="flex items-center gap-3">
                          <span className="w-3 h-3 rounded-full shrink-0" style={{ background: color }} />
                          <div className="flex-1">
                            <div className="flex justify-between items-center">
                              <span className="text-xs font-bold text-gray-700 dark:text-gray-300">{r.name}</span>
                              <span className="text-xs font-bold text-gray-500">{r.value} ({pct}%)</span>
                            </div>
                            <p className="text-[10px] text-gray-400">{pyg(r.monto)}</p>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ) : (
                <p className="text-sm text-gray-400 py-8 text-center">Sin hallazgos registrados</p>
              )}
            </div>

            {/* Bar chart: Hallazgos por impuesto */}
            <div className="card p-6">
              <div className="flex items-center gap-2 mb-6">
                <BarChart3 size={16} className="text-primary" />
                <p className="font-black text-sm uppercase tracking-wide">Hallazgos por impuesto</p>
              </div>
              {impuestoData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={impuestoData} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="name" tick={{ fontSize: 11, fontWeight: 700 }} axisLine={false} tickLine={false} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip />
                    <Bar dataKey="cantidad" radius={[6, 6, 0, 0]}>
                      {impuestoData.map((_, i) => (
                        <Cell key={i} fill={COLORS_IMP[i % COLORS_IMP.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <p className="text-sm text-gray-400 py-8 text-center">Sin hallazgos registrados</p>
              )}
            </div>
          </div>

          {/* Bottom row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top 5 clientes por contingencia */}
            <div className="card p-6">
              <div className="flex items-center gap-2 mb-4">
                <TrendingUp size={16} className="text-primary" />
                <p className="font-black text-sm uppercase tracking-wide">Top clientes por contingencia</p>
              </div>
              {data?.top_clientes_contingencia && data.top_clientes_contingencia.length > 0 ? (
                <div className="space-y-3">
                  {data.top_clientes_contingencia.map((c, i) => (
                    <div key={c.ruc} className="flex items-center gap-3">
                      <span className="w-6 h-6 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-xs font-bold text-gray-500 shrink-0">
                        {i + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="flex justify-between items-center mb-1">
                          <p className="text-xs font-bold text-gray-800 dark:text-gray-200 truncate">{c.razon_social}</p>
                          <span className="text-xs font-bold text-red-500 shrink-0 ml-2">{pyg(c.contingencia)}</span>
                        </div>
                        <div className="w-full h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all"
                            style={{
                              width: `${Math.min(100, (c.contingencia / maxContingencia) * 100)}%`,
                              background: i === 0 ? '#E53E3E' : i === 1 ? '#D97706' : '#22C47E',
                            }}
                          />
                        </div>
                        <p className="text-[10px] text-gray-400 mt-0.5">{c.ruc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-400 py-6 text-center">Sin datos de contingencias</p>
              )}
            </div>

            {/* Actividad reciente */}
            <div className="card p-6">
              <div className="flex items-center gap-2 mb-4">
                <Activity size={16} className="text-primary" />
                <p className="font-black text-sm uppercase tracking-wide">Actividad reciente</p>
              </div>
              {data?.actividad_reciente && data.actividad_reciente.length > 0 ? (
                <div className="space-y-1">
                  {data.actividad_reciente.map((a, i) => (
                    <div key={i} className="flex items-start gap-3 py-2 border-b border-gray-50 dark:border-gray-800 last:border-0">
                      <div className="w-2 h-2 rounded-full bg-green-500 mt-1.5 shrink-0" />
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-bold text-gray-700 dark:text-gray-300">{a.accion}</p>
                        <div className="flex items-center gap-2 text-[10px] text-gray-400 mt-0.5">
                          <span>{a.usuario}</span>
                          {a.timestamp && (
                            <>
                              <span>·</span>
                              <span>{new Date(a.timestamp).toLocaleDateString('es-PY', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' })}</span>
                            </>
                          )}
                          {a.modulo && <><span>·</span><span className="capitalize">{a.modulo}</span></>}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-gray-400 py-6 text-center">Sin actividad reciente</p>
              )}
            </div>
          </div>

          {/* Tendencia mensual */}
          {data?.tendencia_mensual && data.tendencia_mensual.length > 0 && (
            <div className="card p-6">
              <div className="flex items-center gap-2 mb-6">
                <TrendingUp size={16} className="text-primary" />
                <p className="font-black text-sm uppercase tracking-wide">Tendencia mensual</p>
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={data.tendencia_mensual} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="mes" tick={{ fontSize: 10 }} axisLine={false} tickLine={false} />
                  <YAxis yAxisId="left" allowDecimals={false} tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip />
                  <Bar yAxisId="left" dataKey="hallazgos" fill="#2E84F0" radius={[4, 4, 0, 0]} name="Hallazgos" />
                  <Bar yAxisId="right" dataKey="contingencia" fill="#22C47E" radius={[4, 4, 0, 0]} name="Contingencia" opacity={0.6} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </div>
  )
}
