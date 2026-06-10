import { useState, useEffect } from 'react'
import { CheckCircle2, Circle, Info, Gavel, FileText, Settings, Sparkles, Plus, AlertTriangle, Loader2 } from 'lucide-react'
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts'
import { api } from '../../../api/client'
import { useToast } from '../../../components/Toaster'
import { pyg } from '../../../utils/formatters'
import type { Auditoria, Tarea } from '../../../api/types'

interface Props {
  auditoria: Auditoria
  onUpdate: (updated: Auditoria) => void
}

interface Sugerencia {
  prioridad: string; titulo: string; descripcion: string
  patron_relacionado: string; riesgo: string
}

interface Patron {
  tipo: string; severidad: string; titulo: string
  descripcion: string; monto?: number; cantidad?: number
  porcentaje?: number; proveedor_nombre?: string
  proveedores?: { ruc: string; nombre: string; monto_max: number; veces: number }[]
  ejemplos?: { nro: string; monto: number; proveedor: string }[]
  periodo?: string
}

const COLORS_RISK: Record<string, string> = { alto: '#E53E3E', medio: '#D97706', bajo: '#22C47E' }
const COLORS_SEV: Record<string, string> = { alta: '#E53E3E', media: '#D97706', baja: '#22C47E' }

export default function TabPlanTrabajo({ auditoria, onUpdate }: Props) {
  const { success, error } = useToast()
  const [toggling, setToggling] = useState<string | null>(null)
  const [sugerenciasData, setSugerenciasData] = useState<{ patrones: Patron[]; sugerencias: Sugerencia[] } | null>(null)
  const [loadingSugerencias, setLoadingSugerencias] = useState(false)
  const [cargandoTarea, setCargandoTarea] = useState<string | null>(null)

  useEffect(() => {
    api.get(`/auditorias/${auditoria.id}/sugerencias-ia`)
      .then(setSugerenciasData)
      .catch(() => {})
  }, [auditoria.id])

  const cargarSugerencias = async () => {
    setLoadingSugerencias(true)
    try {
      setSugerenciasData(await api.get(`/auditorias/${auditoria.id}/sugerencias-ia?force=true`))
    } catch { error('Error al cargar sugerencias') }
    setLoadingSugerencias(false)
  }

  const agregarTareaDesdeSugerencia = async (s: Sugerencia) => {
    setCargandoTarea(s.titulo)
    try {
      await api.post(`/auditorias/${auditoria.id}/tareas`, {
        titulo: s.titulo, descripcion: s.descripcion,
        categoria: 'impositivo', orden: 99,
      })
      const res = await api.get<Auditoria>(`/auditorias/${auditoria.id}`)
      onUpdate(res)
      success('Tarea agregada al plan')
    } catch (e: unknown) { error(e instanceof Error ? e.message : 'Error') }
    setCargandoTarea(null)
  }

  const handleToggle = async (tareaId: string) => {
    setToggling(tareaId)
    try {
      await api.post(`/auditorias/${auditoria.id}/tareas/${tareaId}/toggle`)
      const res = await api.get<Auditoria>(`/auditorias/${auditoria.id}`)
      onUpdate(res)
    } catch { error('Error al actualizar') }
    setToggling(null)
  }

  const tareas = auditoria.tareas || []
  const completadas = tareas.filter(t => t.completada).length
  const porcentaje = tareas.length > 0 ? Math.round((completadas / tareas.length) * 100) : 0
  const sugerencias = sugerenciasData?.sugerencias ?? []
  const patrones = sugerenciasData?.patrones ?? []

  // Datos para pie chart de concentracion
  const proveedorData = patrones.filter(p => p.tipo === 'CONCENTRACION_PROVEEDOR').map(p => ({
    name: p.proveedor_nombre || 'Principal', value: p.monto || 0,
  }))
  const otrosMonto = proveedorData.length > 0 ? Math.max(0, 100 - proveedorData[0].value / 1000000) : 0
  if (proveedorData.length > 0) {
    proveedorData.push({ name: 'Otros', value: otrosMonto })
  }

  const getIcon = (cat: string) => {
    switch (cat) {
      case 'legal': return <Gavel size={14} className="text-purple-500" />
      case 'impositivo': return <FileText size={14} className="text-blue-500" />
      default: return <Settings size={14} className="text-gray-400" />
    }
  }

  return (
    <div className="space-y-6 animate-fade-in pb-10">
      {/* Progress Header */}
      <div className="card p-6 flex items-center justify-between bg-gradient-to-r from-gray-50 to-white dark:from-gray-800/50 dark:to-gray-900/50">
        <div>
          <h3 className="text-sm font-black text-gray-900 dark:text-white uppercase tracking-widest">Progreso del Encargo</h3>
          <p className="text-xs text-gray-500 mt-1">{completadas} de {tareas.length} tareas completadas</p>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <span className="text-2xl font-black text-primary">{porcentaje}%</span>
          </div>
          <div className="w-32 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
            <div className="h-full bg-primary transition-all duration-500" style={{ width: `${porcentaje}%` }} />
          </div>
        </div>
      </div>

      {/* Sugerencias IA */}
      <div className="card p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-purple-500" />
            <p className="font-black text-sm uppercase tracking-wide">Sugerencias de IA</p>
          </div>
          <button onClick={cargarSugerencias} disabled={loadingSugerencias}
            className="btn-ghost text-xs flex items-center gap-1">
            {loadingSugerencias ? <Loader2 size={12} className="animate-spin" /> : null}
            {loadingSugerencias ? 'Analizando...' : 'Actualizar'}
          </button>
        </div>

        {sugerencias.length === 0 && !loadingSugerencias && (
          <p className="text-xs text-gray-400 text-center py-4">Sin sugerencias. Haz clic en "Actualizar" para analizar los datos.</p>
        )}

        {loadingSugerencias && (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin text-primary" />
            <span className="ml-2 text-xs text-gray-500">Analizando patrones con IA...</span>
          </div>
        )}

        {sugerencias.length > 0 && (
          <div className="space-y-3">
            {sugerencias.map((s, i) => (
              <div key={i} className={`p-4 rounded-xl border-2 ${
                s.prioridad === 'alta' ? 'border-red-200 dark:border-red-800/40 bg-red-50/50 dark:bg-red-900/5' :
                s.prioridad === 'media' ? 'border-amber-200 dark:border-amber-800/40 bg-amber-50/50 dark:bg-amber-900/5' :
                'border-green-200 dark:border-green-800/40 bg-green-50/50 dark:bg-green-900/5'
              }`}>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                        s.prioridad === 'alta' ? 'bg-red-100 text-red-700' :
                        s.prioridad === 'media' ? 'bg-amber-100 text-amber-700' :
                        'bg-green-100 text-green-700'
                      }`}>{s.prioridad}</span>
                      <span className={`px-2 py-0.5 rounded text-[9px] font-black uppercase ${
                        s.riesgo === 'alto' ? 'bg-red-100 text-red-700' :
                        s.riesgo === 'medio' ? 'bg-amber-100 text-amber-700' :
                        'bg-green-100 text-green-700'
                      }`}>Riesgo {s.riesgo}</span>
                    </div>
                    <p className="text-sm font-bold text-gray-800 dark:text-gray-200">{s.titulo}</p>
                    <p className="text-xs text-gray-500 mt-1">{s.descripcion}</p>
                    {s.patron_relacionado && (
                      <p className="text-[10px] text-purple-600 dark:text-purple-400 mt-1">Patron: {s.patron_relacionado}</p>
                    )}
                  </div>
                  <button onClick={() => agregarTareaDesdeSugerencia(s)} disabled={cargandoTarea === s.titulo}
                    className="btn-primary text-[10px] py-1.5 px-3 shrink-0 flex items-center gap-1">
                    {cargandoTarea === s.titulo ? <Loader2 size={10} className="animate-spin" /> : <Plus size={10} />}
                    Agregar
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Patrones detectados */}
      {patrones.length > 0 && (
        <div className="card p-5 space-y-4">
          <div className="flex items-center gap-2">
            <AlertTriangle size={16} className="text-amber-500" />
            <p className="font-black text-sm uppercase tracking-wide">Patrones detectados ({patrones.length})</p>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Pie chart: concentracion */}
            {proveedorData.length > 1 && (
              <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-800/50">
                <p className="text-xs font-bold text-gray-500 mb-3 uppercase">Concentracion de proveedores</p>
                <div className="flex items-center gap-4">
                  <div className="w-28 h-28 shrink-0">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={proveedorData} cx="50%" cy="50%" innerRadius={25} outerRadius={40} dataKey="value" paddingAngle={3}>
                          {proveedorData.map((_, i) => (
                            <Cell key={i} fill={i === 0 ? '#E53E3E' : '#CBD5E1'} />
                          ))}
                        </Pie>
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="text-xs text-gray-600 dark:text-gray-400">
                    <p className="font-bold text-red-500">{proveedorData[0].name}</p>
                    <p>Representa {patrones.find(p => p.tipo === 'CONCENTRACION_PROVEEDOR')?.descripcion.split('representa')[1]?.split('.')[0] || '>20%'}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Facturas sospechosas */}
            {patrones.filter(p => p.tipo === 'FACTURAS_REDONDAS').length > 0 && (
              <div className="p-4 rounded-xl bg-gray-50 dark:bg-gray-800/50">
                <p className="text-xs font-bold text-gray-500 mb-3 uppercase">Facturas sospechosas</p>
                {patrones.filter(p => p.tipo === 'FACTURAS_REDONDAS')[0]?.ejemplos?.map((ex, i) => (
                  <div key={i} className="flex items-center justify-between py-1.5 text-xs border-b border-gray-100 dark:border-gray-700 last:border-0">
                    <span className="font-mono text-gray-600 dark:text-gray-400">{ex.nro}</span>
                    <span className="font-bold text-gray-800 dark:text-gray-200">{pyg(ex.monto)}</span>
                    <span className="text-gray-400 truncate max-w-[120px]">{ex.proveedor}</span>
                  </div>
                )) || null}
              </div>
            )}
          </div>

          {/* Todos los patrones */}
          <div className="space-y-2">
            {patrones.map((p, i) => (
              <div key={i} className="flex items-start gap-3 p-3 rounded-xl bg-gray-50 dark:bg-gray-800/50 text-xs">
                <span className="w-2 h-2 rounded-full mt-1 shrink-0" style={{ background: COLORS_SEV[p.severidad] || '#94a3b8' }} />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-bold text-gray-700 dark:text-gray-300">{p.titulo}</p>
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${
                      p.severidad === 'alta' ? 'bg-red-100 text-red-600' :
                      p.severidad === 'media' ? 'bg-amber-100 text-amber-600' :
                      'bg-green-100 text-green-600'
                    }`}>{p.severidad}</span>
                  </div>
                  <p className="text-gray-500 dark:text-gray-400 mt-0.5">{p.descripcion}</p>
                  {p.monto && <p className="text-gray-400 mt-0.5">Monto: {pyg(p.monto)}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Checklist */}
      <div className="space-y-3">
        {tareas.length === 0 ? (
          <div className="py-20 text-center text-gray-400">
            <Info size={40} className="mx-auto mb-4 opacity-20" />
            <p className="text-sm font-bold uppercase tracking-widest">No hay tareas programadas</p>
          </div>
        ) : (
          tareas.sort((a, b) => a.orden - b.orden).map((tarea) => (
            <div key={tarea.id} className={`card p-4 flex items-start gap-4 transition-all ${
              tarea.completada ? 'opacity-60 bg-gray-50/50 dark:bg-gray-800/20' : 'hover:border-primary/30'
            }`}>
              <button onClick={() => handleToggle(tarea.id)} disabled={toggling === tarea.id} className="mt-0.5 shrink-0">
                {tarea.completada ? (
                  <CheckCircle2 size={22} className="text-green-500 fill-green-50/20" />
                ) : (
                  <Circle size={22} className="text-gray-300 dark:text-gray-600 hover:text-primary transition-colors" />
                )}
              </button>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  {getIcon(tarea.categoria)}
                  <span className="text-[10px] font-black uppercase tracking-widest text-gray-400">{tarea.categoria}</span>
                </div>
                <h4 className={`text-sm font-bold ${tarea.completada ? 'line-through text-gray-500' : 'text-gray-900 dark:text-white'}`}>
                  {tarea.titulo}
                </h4>
                {tarea.descripcion && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-relaxed">{tarea.descripcion}</p>
                )}
              </div>
              {tarea.fecha_completado && (
                <div className="text-[9px] font-bold text-gray-400 uppercase mt-1">
                  Listo el {new Date(tarea.fecha_completado).toLocaleDateString()}
                </div>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
