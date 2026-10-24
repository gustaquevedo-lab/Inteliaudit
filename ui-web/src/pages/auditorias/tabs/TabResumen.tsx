import { useState, useEffect } from 'react'
import { pyg, rangoPeríodos } from '../../../utils/formatters'
import { BadgeRiesgo, BadgeImpuesto } from '../../../components/Badge'
import RiskMatrix from '../../../components/RiskMatrix'
import KPICard from '../../../components/KPICard'
import { AlertTriangle, TrendingUp, FileSearch, CheckCircle, Clock } from 'lucide-react'
import { api } from '../../../api/client'
import type { Auditoria, Cliente, Hallazgo } from '../../../api/types'

interface AlertaPlazo {
  tipo: string
  nivel: string
  periodo: string
  mensaje: string
  dias_restantes?: number
}

interface PlazosData {
  fecha_calculo: string
  alertas: AlertaPlazo[]
}

interface Props {
  auditoria: Auditoria
  cliente: Cliente
  hallazgos: Hallazgo[]
}

export default function TabResumen({ auditoria, cliente, hallazgos }: Props) {
  const [plazos, setPlazos] = useState<PlazosData | null>(null)

  useEffect(() => {
    api.get<PlazosData>(`/auditorias/${auditoria.id}/plazos`)
      .then(setPlazos)
      .catch(() => {})
  }, [auditoria.id])

  const activos = hallazgos.filter(h => h.estado !== 'descartado')
  const altos = activos.filter(h => h.nivel_riesgo === 'alto')
  const confirmados = activos.filter(h => h.estado === 'confirmado')
  const totalContingencia = activos.reduce((s, h) => s + h.total_contingencia, 0)
  const totalImpuesto = activos.reduce((s, h) => s + h.impuesto_omitido, 0)
  const topHallazgos = [...activos].sort((a, b) => b.total_contingencia - a.total_contingencia).slice(0, 5)

  return (
    <div className="space-y-6">
      {/* Alertas de Prescripción Fiscal (Ley 125/1991) */}
      {plazos && plazos.alertas && plazos.alertas.length > 0 && (
        <div className="card p-4 border-l-4 border-amber-500 bg-amber-50/40 dark:bg-amber-950/20">
          <div className="flex items-center justify-between mb-2.5">
            <div className="flex items-center gap-2">
              <Clock className="text-amber-600 dark:text-amber-400" size={17} />
              <p className="text-xs font-bold uppercase tracking-wider text-amber-900 dark:text-amber-200">
                Control de Prescripción Tributaria (Ley 125/1991 Art. 219)
              </p>
            </div>
            <span className="text-[10px] text-gray-500">Cálculo: {plazos.fecha_calculo}</span>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {plazos.alertas.slice(0, 4).map((alerta, i) => (
              <div
                key={i}
                className="flex items-start gap-2 p-2 rounded-lg bg-white dark:bg-gray-800 border border-amber-200 dark:border-amber-900/40 shadow-xs"
              >
                <span
                  className={`mt-0.5 px-1.5 py-0.5 text-[9px] font-black rounded uppercase ${
                    alerta.nivel === 'alto'
                      ? 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
                      : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'
                  }`}
                >
                  {alerta.periodo}
                </span>
                <p className="text-xs text-gray-700 dark:text-gray-200 leading-snug">
                  {alerta.mensaje}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}
      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard
          label="Contingencia total"
          value={pyg(totalContingencia)}
          icon={<TrendingUp size={20} className="text-red-500" />}
          iconBg="bg-red-50 dark:bg-red-900/20"
        />
        <KPICard
          label="Impuesto omitido"
          value={pyg(totalImpuesto)}
          icon={<AlertTriangle size={20} className="text-amber-500" />}
          iconBg="bg-amber-50 dark:bg-amber-900/20"
        />
        <KPICard
          label="Hallazgos alto riesgo"
          value={altos.length}
          icon={<AlertTriangle size={20} className="text-red-600" />}
          iconBg="bg-red-50 dark:bg-red-900/20"
          subtitle={`de ${activos.length} hallazgos activos`}
        />
        <KPICard
          label="Confirmados"
          value={confirmados.length}
          icon={<CheckCircle size={20} className="text-green-600" />}
          iconBg="bg-green-50 dark:bg-green-900/20"
          subtitle={`de ${activos.length} activos`}
        />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Datos del encargo */}
        <div className="card p-5">
          <p className="section-label">Datos del encargo</p>
          <div className="space-y-3">
            {[
              { label: 'Cliente', value: cliente.razon_social },
              { label: 'RUC', value: cliente.ruc, mono: true },
              { label: 'Período', value: rangoPeríodos(auditoria.periodo_desde, auditoria.periodo_hasta) },
              { label: 'Auditor', value: auditoria.auditor ?? '—' },
              { label: 'Materialidad', value: auditoria.materialidad > 0 ? pyg(auditoria.materialidad) : 'Sin umbral' },
            ].map(row => (
              <div key={row.label} className="flex justify-between gap-3">
                <span className="text-xs text-gray-500 dark:text-gray-400 shrink-0">{row.label}</span>
                <span className={`text-xs font-bold text-gray-800 dark:text-gray-200 text-right ${row.mono ? 'font-mono' : ''}`}>{row.value}</span>
              </div>
            ))}
            <div>
              <span className="text-xs text-gray-500 dark:text-gray-400 block mb-2">Impuestos en alcance</span>
              <div className="flex flex-wrap gap-1">
                {auditoria.impuestos.map(i => <BadgeImpuesto key={i} impuesto={i} />)}
              </div>
            </div>
          </div>
        </div>

        {/* Top hallazgos */}
        <div className="xl:col-span-2 card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
            <p className="section-label mb-0">Top hallazgos por contingencia</p>
          </div>
          {topHallazgos.length === 0 ? (
            <div className="py-12 flex flex-col items-center gap-2 text-gray-400">
              <FileSearch size={28} />
              <p className="text-sm font-bold">Sin hallazgos activos</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-700/50">
              {topHallazgos.map((h, idx) => (
                <div key={h.id} className="px-5 py-3.5 flex items-center gap-3">
                  <span className="w-6 h-6 rounded-lg bg-gray-100 dark:bg-gray-800 flex items-center justify-center text-xs font-black text-gray-500 shrink-0">
                    {idx + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <BadgeImpuesto impuesto={h.impuesto} />
                      <BadgeRiesgo nivel={h.nivel_riesgo} />
                    </div>
                    <p className="text-xs font-bold text-gray-800 dark:text-gray-200 truncate">{h.tipo_hallazgo}</p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-sm font-black text-gray-900 dark:text-white">{pyg(h.total_contingencia)}</p>
                    <p className="text-[10px] text-gray-400">contingencia total</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Matriz de riesgo */}
      {activos.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 dark:border-gray-700">
            <p className="section-label mb-0">Matriz de riesgo por impuesto</p>
          </div>
          <div className="p-2">
            <RiskMatrix hallazgos={hallazgos} />
          </div>
        </div>
      )}
    </div>
  )
}
