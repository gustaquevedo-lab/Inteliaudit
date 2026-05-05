import { useState, useEffect } from 'react'
import { useParams, useNavigate, NavLink } from 'react-router-dom'
import { ArrowLeft, Loader2, Calendar, User, Target, Settings, MoreVertical, CheckCircle2, Clock, XCircle, AlertCircle } from 'lucide-react'
import { api } from '../../api/client'
import { useToast } from '../../components/Toaster'
import { BadgeEstadoAuditoria, BadgeImpuesto } from '../../components/Badge'
import { rangoPeríodos, fecha, pyg } from '../../utils/formatters'
import type { Auditoria, Cliente, Hallazgo } from '../../api/types'
import TabResumen from './tabs/TabResumen'
import TabHallazgos from './tabs/TabHallazgos'
import TabArchivos from './tabs/TabArchivos'
import TabInformes from './tabs/TabInformes'
import TabPlanTrabajo from './tabs/TabPlanTrabajo'
import TabAnalisis from './tabs/TabAnalisis'

const TABS = [
  { id: 'resumen', label: 'Resumen', path: '' },
  { id: 'hallazgos', label: 'Hallazgos', path: 'hallazgos' },
  { id: 'analisis', label: 'Análisis', path: 'analisis' },
  { id: 'plan', label: 'Plan de Trabajo', path: 'plan-de-trabajo' },
  { id: 'archivos', label: 'Archivos', path: 'archivos' },
  { id: 'informes', label: 'Informes', path: 'informes' },
]

export default function AuditoriaDetail() {
  const { id, '*': splat } = useParams<{ id: string; '*': string }>()
  const navigate = useNavigate()
  const { error } = useToast()
  const [auditoria, setAuditoria] = useState<Auditoria | null>(null)
  const [cliente, setCliente] = useState<Cliente | null>(null)
  const [hallazgos, setHallazgos] = useState<Hallazgo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api.get<Auditoria>(`/auditorias/${id}`)
      .then(async (aud) => {
        setAuditoria(aud)
        const [cli, hall] = await Promise.all([
          api.get<Cliente>(`/clientes/${aud.cliente_id}`),
          api.get<Hallazgo[]>(`/auditorias/${id}/hallazgos`),
        ])
        setCliente(cli)
        setHallazgos(hall)
      })
      .catch(() => error('No se pudo cargar la auditoría'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 size={28} className="animate-spin text-primary" />
      </div>
    )
  }

  if (!auditoria || !cliente) {
    return (
      <div className="flex flex-col items-center justify-center h-96 gap-3 text-gray-400">
        <AlertCircle size={32} />
        <p className="font-bold text-sm">Auditoría no encontrada</p>
        <button onClick={() => navigate(-1)} className="btn-outline text-sm py-2">
          <ArrowLeft size={14} /> Volver
        </button>
      </div>
    )
  }

  const activos = hallazgos.filter(h => h.estado !== 'descartado')
  const totalContingencia = activos.reduce((s, h) => s + h.total_contingencia, 0)
  const pendientes = activos.filter(h => h.estado === 'pendiente').length

  const estadoIcon: Record<string, React.ReactNode> = {
    'en_progreso': <Clock size={14} className="text-amber-500" />,
    'revision': <Clock size={14} className="text-blue-500" />,
    'finalizada': <CheckCircle2 size={14} className="text-green-500" />,
    'cerrada': <CheckCircle2 size={14} className="text-green-600" />,
    'cancelada': <XCircle size={14} className="text-red-500" />,
    'borrador': <AlertCircle size={14} className="text-gray-400" />,
  }
  const icon = estadoIcon[auditoria.estado] ?? null

  return (
    <div className="space-y-0">
      {/* Header */}
      <div className="mb-6">
        <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400 hover:text-primary dark:hover:text-primary-light transition-colors mb-4">
          <ArrowLeft size={13} /> Volver a clientes
        </button>

        <div className="card p-5">
          <div className="flex flex-col lg:flex-row lg:items-start gap-4">
            {/* Info principal */}
            <div className="flex-1 min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <BadgeEstadoAuditoria estado={auditoria.estado} />
                {pendientes > 0 && (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-100 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border border-amber-200 dark:border-amber-800/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
                    {pendientes} pendiente{pendientes > 1 ? 's' : ''}
                  </span>
                )}
              </div>
              <h1 className="text-xl font-black text-gray-900 dark:text-white tracking-tight leading-tight">
                {cliente.razon_social}
              </h1>
              <p className="text-sm text-gray-500 dark:text-gray-400 font-mono mt-0.5">{cliente.ruc}</p>

              <div className="flex flex-wrap gap-4 mt-3">
                <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                  <Calendar size={13} className="text-gray-400" />
                  <span className="font-medium">{rangoPeríodos(auditoria.periodo_desde, auditoria.periodo_hasta)}</span>
                </div>
                {auditoria.auditor && (
                  <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                    <User size={13} className="text-gray-400" />
                    <span className="font-medium">{auditoria.auditor}</span>
                  </div>
                )}
                {auditoria.materialidad > 0 && (
                  <div className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-400">
                    <Target size={13} className="text-gray-400" />
                    <span className="font-medium">Mat. {pyg(auditoria.materialidad)}</span>
                  </div>
                )}
              </div>

              <div className="flex flex-wrap gap-1 mt-3">
                {auditoria.impuestos.map(i => <BadgeImpuesto key={i} impuesto={i} />)}
              </div>
            </div>

            {/* KPIs rápidos */}
            <div className="flex gap-3 shrink-0">
              <div className="text-center px-4 py-3 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-100 dark:border-gray-700/50">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">Hallazgos</p>
                <p className="text-2xl font-black text-gray-900 dark:text-white">{activos.length}</p>
              </div>
              <div className="text-center px-4 py-3 bg-red-50 dark:bg-red-900/10 rounded-xl border border-red-100 dark:border-red-800/20">
                <p className="text-[10px] font-bold text-red-400 uppercase tracking-wide mb-1">Contingencia</p>
                <p className="text-lg font-black text-red-700 dark:text-red-400 whitespace-nowrap">{pyg(totalContingencia)}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs nav */}
      <div className="border-b border-gray-200 dark:border-gray-700 mb-6">
        <nav className="flex gap-0 -mb-px">
          {TABS.map(tab => {
            const basePath = `/auditorias/${id}`
            const to = tab.path ? `${basePath}/${tab.path}` : basePath
            return (
              <NavLink
                key={tab.id}
                to={to}
                end={tab.path === ''}
                className={({ isActive }) =>
                  `px-5 py-3 text-sm font-bold border-b-2 transition-colors whitespace-nowrap ${
                    isActive
                      ? 'border-primary text-primary dark:text-primary-light'
                      : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:border-gray-300 dark:hover:border-gray-600'
                  }`
                }
              >
                {tab.label}
                {tab.id === 'hallazgos' && activos.length > 0 && (
                  <span className="ml-2 px-1.5 py-0.5 text-[10px] font-black rounded-full bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400">
                    {activos.length}
                  </span>
                )}
              </NavLink>
            )
          })}
        </nav>
      </div>

      {/* Tab content — resolved from URL splat */}
      {(() => {
        const activeTab = (splat || '').replace(/^\//, '').split('/')[0]
        switch (activeTab) {
          case 'hallazgos':
            return <TabHallazgos auditoriaId={id!} hallazgos={hallazgos} onUpdate={setHallazgos} />
          case 'analisis':
            return <TabAnalisis auditoriaId={id!} />
          case 'plan-de-trabajo':
            return <TabPlanTrabajo auditoria={auditoria} onUpdate={(updated) => setAuditoria(updated)} />
          case 'archivos':
            return <TabArchivos auditoriaId={id!} />
          case 'informes':
            return <TabInformes auditoriaId={id!} clienteRuc={cliente.ruc} />
          default:
            return <TabResumen auditoria={auditoria} cliente={cliente} hallazgos={hallazgos} />
        }
      })()}
    </div>
  )
}
