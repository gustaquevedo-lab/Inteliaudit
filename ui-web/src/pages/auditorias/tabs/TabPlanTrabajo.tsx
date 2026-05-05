import { CheckCircle2, Circle, Info, Gavel, FileText, Settings } from 'lucide-react'
import { api } from '../../../api/client'
import type { Auditoria, Tarea } from '../../../api/types'
import { useState } from 'react'

interface Props {
  auditoria: Auditoria
  onUpdate: (updated: Auditoria) => void
}

export default function TabPlanTrabajo({ auditoria, onUpdate }: Props) {
  const [toggling, setToggling] = useState<string | null>(null)

  const handleToggle = async (tareaId: string) => {
    setToggling(tareaId)
    try {
      await api.post(`/auditorias/${auditoria.id}/tareas/${tareaId}/toggle`)
      // Recargar datos de la auditoría para refrescar el checklist
      const res = await api.get<Auditoria>(`/auditorias/${auditoria.id}`)
      onUpdate(res)
    } catch (err) {
      console.error("Error toggling tarea:", err)
    } finally {
      setToggling(null)
    }
  }

  const tareas = auditoria.tareas || []
  const completadas = tareas.filter(t => t.completada).length
  const porcentaje = tareas.length > 0 ? Math.round((completadas / tareas.length) * 100) : 0

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
            <div 
              className="h-full bg-primary transition-all duration-500" 
              style={{ width: `${porcentaje}%` }} 
            />
          </div>
        </div>
      </div>

      {/* Checklist */}
      <div className="space-y-3">
        {tareas.length === 0 ? (
          <div className="py-20 text-center text-gray-400">
            <Info size={40} className="mx-auto mb-4 opacity-20" />
            <p className="text-sm font-bold uppercase tracking-widest">No hay tareas programadas</p>
          </div>
        ) : (
          tareas.sort((a, b) => a.orden - b.orden).map((tarea) => (
            <div 
              key={tarea.id}
              className={`card p-4 flex items-start gap-4 transition-all ${
                tarea.completada ? 'opacity-60 bg-gray-50/50 dark:bg-gray-800/20' : 'hover:border-primary/30'
              }`}
            >
              <button 
                onClick={() => handleToggle(tarea.id)}
                disabled={toggling === tarea.id}
                className="mt-0.5 shrink-0"
              >
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
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-1 leading-relaxed">
                    {tarea.descripcion}
                  </p>
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
