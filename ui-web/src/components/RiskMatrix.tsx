import { pyg } from '../utils/formatters'
import type { Hallazgo } from '../api/types'

interface RiskMatrixProps {
  hallazgos: Hallazgo[]
}

const IMPUESTOS = ['IVA', 'IRE', 'RET_IVA', 'RET_IRE', 'IRP', 'IDU', 'OTRO']
const RIESGOS = ['alto', 'medio', 'bajo'] as const

export default function RiskMatrix({ hallazgos }: RiskMatrixProps) {
  const activos = hallazgos.filter(h => h.estado !== 'descartado')

  const cell = (impuesto: string, riesgo: string) => {
    const items = activos.filter(h => h.impuesto === impuesto && h.nivel_riesgo === riesgo)
    if (!items.length) return null
    const total = items.reduce((s, h) => s + h.total_contingencia, 0)
    return { count: items.length, total }
  }

  const bgRiesgo = { alto: 'bg-red-50 dark:bg-red-900/10', medio: 'bg-amber-50 dark:bg-amber-900/10', bajo: 'bg-green-50 dark:bg-green-900/10' }
  const textRiesgo = { alto: 'text-red-700 dark:text-red-400', medio: 'text-amber-700 dark:text-amber-400', bajo: 'text-green-700 dark:text-green-400' }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="table-header">
            <th className="table-cell w-24">Impuesto</th>
            {RIESGOS.map(r => (
              <th key={r} className={`table-cell text-center ${textRiesgo[r]}`}>
                {r === 'alto' ? '🔴 Alto' : r === 'medio' ? '🟡 Medio' : '🟢 Bajo'}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {IMPUESTOS.map(imp => {
            const hasAny = RIESGOS.some(r => cell(imp, r))
            if (!hasAny) return null
            return (
              <tr key={imp} className="table-row">
                <td className="table-td font-bold text-gray-700 dark:text-gray-200">{imp.replace('_', ' ')}</td>
                {RIESGOS.map(r => {
                  const data = cell(imp, r)
                  return (
                    <td key={r} className="table-td text-center">
                      {data ? (
                        <div className={`inline-flex flex-col items-center px-3 py-1.5 rounded-lg ${bgRiesgo[r]}`}>
                          <span className={`font-black text-[11px] ${textRiesgo[r]}`}>{data.count} hallazgo{data.count > 1 ? 's' : ''}</span>
                          <span className="text-[10px] text-gray-500 dark:text-gray-400">{pyg(data.total)}</span>
                        </div>
                      ) : (
                        <span className="text-gray-300 dark:text-gray-600">—</span>
                      )}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
