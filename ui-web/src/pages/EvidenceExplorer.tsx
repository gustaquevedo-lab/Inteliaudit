import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  ShieldAlert, 
  FileText, 
  Search, 
  ExternalLink, 
  CheckCircle2, 
  XCircle, 
  ChevronRight, 
  Filter,
  Eye,
  Download,
  Database
} from 'lucide-react'
import { api } from '../api/client'
import { BadgeRiesgo } from '../components/Badge'
import { pyg, fecha } from '../utils/formatters'
import type { Auditoria, Hallazgo, Cliente } from '../api/types'

export default function EvidenceExplorer() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  
  const [auditoria, setAuditoria] = useState<Auditoria | null>(null)
  const [cliente, setCliente] = useState<Cliente | null>(null)
  const [hallazgos, setHallazgos] = useState<Hallazgo[]>([])
  const [selectedHallazgo, setSelectedHallazgo] = useState<Hallazgo | null>(null)
  const [loading, setLoading] = useState(true)
  const [validating, setValidating] = useState(false)
  const [filterImpuesto, setFilterImpuesto] = useState<string>('TODOS')

  const handleValidarSifen = async () => {
    if (!id) return
    setValidating(true)
    try {
      await api.post(`/auditorias/${id}/validar-sifen`)
      // Recargar hallazgos para ver cambios si los hay
      const hallData = await api.get<Hallazgo[]>(`/auditorias/${id}/hallazgos`)
      setHallazgos(hallData)
      alert("Validación SIFEN completada con éxito.")
    } catch (err) {
      console.error("Error validando SIFEN:", err)
    } finally {
      setValidating(false)
    }
  }

  const handleGenerarInforme = async () => {
    if (!id) return
    try {
      const blob = await api.postBlob(`/auditorias/${id}/informes/word`, {})
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `informe_auditoria_${id.slice(0,8)}.docx`)
      document.body.appendChild(link)
      link.click()
    } catch (err) {
      console.error("Error generando informe:", err)
      alert("No se pudo generar el informe.")
    }
  }

  useEffect(() => {
    if (!id) return
    
    const loadData = async () => {
      try {
        const [audData, hallData] = await Promise.all([
          api.get<Auditoria>(`/auditorias/${id}`),
          api.get<Hallazgo[]>(`/auditorias/${id}/hallazgos`)
        ])
        
        setAuditoria(audData)
        setHallazgos(hallData)
        
        const cliData = await api.get<Cliente>(`/clientes/${audData.cliente_id}`)
        setCliente(cliData)
        
        if (hallData.length > 0) {
          setSelectedHallazgo(hallData[0])
        }
      } catch (err) {
        console.error("Error cargando evidencia:", err)
      } finally {
        setLoading(false)
      }
    }
    
    loadData()
  }, [id])

  if (loading) return (
    <div className="flex flex-col items-center justify-center py-32 space-y-4">
      <div className="w-10 h-10 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      <p className="text-xs font-bold text-gray-500 uppercase tracking-widest">Cargando Evidencia Explorer...</p>
    </div>
  )

  const filteredHallazgos = filterImpuesto === 'TODOS' 
    ? hallazgos 
    : hallazgos.filter(h => h.impuesto === filterImpuesto)

  return (
    <div className="h-[calc(100vh-120px)] flex flex-col gap-4 animate-fade-in">
      {/* Header / Toolbar */}
      <div className="flex items-center justify-between bg-white dark:bg-gray-900 p-4 rounded-2xl border border-gray-100 dark:border-gray-800 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="p-2.5 bg-primary/10 rounded-xl">
            <ShieldAlert className="text-primary" size={20} />
          </div>
          <div>
            <h1 className="text-lg font-black text-gray-900 dark:text-white leading-none">Evidence Explorer</h1>
            <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-1 uppercase font-bold tracking-wider">
              {cliente?.razon_social} • {auditoria?.periodo_desde} al {auditoria?.periodo_hasta}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <button 
            onClick={handleGenerarInforme}
            className="btn-ghost text-[10px] py-2 flex items-center gap-2 border border-gray-100 dark:border-gray-800"
          >
            <FileText size={14} className="text-gray-400" />
            Generar Informe
          </button>

          <button 
            onClick={handleValidarSifen}
            disabled={validating}
            className={`btn-secondary text-[10px] py-2 flex items-center gap-2 ${validating ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {validating ? (
              <div className="w-3 h-3 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            ) : (
              <Database size={14} />
            )}
            {validating ? 'Validando...' : 'Validar SIFEN'}
          </button>

          <div className="flex bg-gray-100 dark:bg-gray-800 p-1 rounded-xl">
            {['TODOS', 'IVA', 'IRE', 'IRP'].map(t => (
              <button
                key={t}
                onClick={() => setFilterImpuesto(t)}
                className={`px-3 py-1.5 text-[10px] font-black rounded-lg transition-all ${
                  filterImpuesto === t 
                    ? 'bg-white dark:bg-gray-700 text-primary shadow-sm' 
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Split View */}
      <div className="flex-1 flex gap-4 overflow-hidden">
        
        {/* Left Panel: Findings List */}
        <div className="w-1/3 flex flex-col gap-2 overflow-y-auto pr-2 custom-scrollbar">
          {filteredHallazgos.map(h => (
            <div
              key={h.id}
              onClick={() => setSelectedHallazgo(h)}
              className={`p-4 rounded-2xl border transition-all cursor-pointer group ${
                selectedHallazgo?.id === h.id
                  ? 'bg-primary/5 border-primary shadow-md'
                  : 'bg-white dark:bg-gray-900 border-gray-100 dark:border-gray-800 hover:border-primary/50'
              }`}
            >
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${
                    h.nivel_riesgo === 'alto' ? 'bg-red-500' : h.nivel_riesgo === 'medio' ? 'bg-amber-500' : 'bg-green-500'
                  }`} />
                  <span className="text-[10px] font-black text-primary uppercase">{h.impuesto}</span>
                </div>
                <BadgeRiesgo nivel={h.nivel_riesgo} />
              </div>
              <h3 className="text-sm font-bold text-gray-800 dark:text-gray-200 line-clamp-2 leading-tight">
                {h.tipo_hallazgo}
              </h3>
              <div className="mt-3 flex items-center justify-between">
                <span className="text-[11px] font-bold text-gray-900 dark:text-white">
                  {pyg(h.total_contingencia)}
                </span>
                <ChevronRight size={14} className={`transition-transform ${selectedHallazgo?.id === h.id ? 'translate-x-1 text-primary' : 'text-gray-300'}`} />
              </div>
            </div>
          ))}
        </div>

        {/* Right Panel: Finding Details & Evidence */}
        <div className="flex-1 bg-white dark:bg-gray-900 rounded-3xl border border-gray-100 dark:border-gray-800 flex flex-col overflow-hidden shadow-xl">
          {selectedHallazgo ? (
            <div className="flex-1 flex flex-col">
              {/* Finding Header */}
              <div className="p-8 border-b border-gray-50 dark:border-gray-800">
                <div className="flex justify-between items-start mb-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-800 rounded text-[9px] font-black text-gray-500 uppercase tracking-tighter">REF: {selectedHallazgo.id.slice(0,8)}</span>
                      <span className="px-2 py-0.5 bg-secondary/10 rounded text-[9px] font-black text-secondary uppercase tracking-tighter">{selectedHallazgo.periodo}</span>
                    </div>
                    <h2 className="text-xl font-black text-gray-900 dark:text-white tracking-tight">{selectedHallazgo.tipo_hallazgo}</h2>
                  </div>
                  <div className="flex gap-2">
                    <button className="p-2 rounded-xl bg-green-50 dark:bg-green-900/20 text-green-600 hover:bg-green-100 transition-colors">
                      <CheckCircle2 size={18} />
                    </button>
                    <button className="p-2 rounded-xl bg-red-50 dark:bg-red-900/20 text-red-600 hover:bg-red-100 transition-colors">
                      <XCircle size={18} />
                    </button>
                  </div>
                </div>
                
                <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                  {selectedHallazgo.descripcion}
                </p>
                
                <div className="mt-6 p-4 bg-amber-50 dark:bg-amber-900/10 rounded-2xl border border-amber-100/50 dark:border-amber-900/20">
                  <div className="flex items-center gap-2 text-amber-700 dark:text-amber-500 mb-1">
                    <FileText size={14} />
                    <span className="text-[10px] font-black uppercase tracking-wider">Base Legal</span>
                  </div>
                  <p className="text-xs font-bold text-amber-900 dark:text-amber-200 italic">
                    "{selectedHallazgo.articulo_legal}"
                  </p>
                </div>
              </div>

              {/* Tabs / Evidence Section */}
              <div className="flex-1 flex flex-col min-h-0">
                <div className="px-8 border-b border-gray-50 dark:border-gray-800 flex gap-6">
                  {['Hallazgo Detallado', 'Papeles de Trabajo', 'Documentación DNIT'].map((tab, i) => (
                    <button key={tab} className={`py-4 text-xs font-black uppercase tracking-widest relative ${i === 0 ? 'text-primary' : 'text-gray-400'}`}>
                      {tab}
                      {i === 0 && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />}
                    </button>
                  ))}
                </div>

                <div className="flex-1 p-8 overflow-y-auto bg-gray-50/50 dark:bg-gray-950/30">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="card p-6 bg-white dark:bg-gray-900 shadow-sm border-gray-50">
                      <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-4">Cálculo de Contingencia</h4>
                      <div className="space-y-3">
                        {[
                          { label: 'Impuesto Omitido', val: selectedHallazgo.impuesto_omitido },
                          { label: 'Multa Estimada (50%)', val: selectedHallazgo.multa_estimada },
                          { label: 'Intereses', val: selectedHallazgo.intereses_estimados },
                        ].map((row, i) => (
                          <div key={i} className="flex justify-between items-center pb-2 border-b border-gray-50 dark:border-gray-800 last:border-0">
                            <span className="text-xs text-gray-500 font-medium">{row.label}</span>
                            <span className="text-xs font-bold text-gray-900 dark:text-white">{pyg(row.val)}</span>
                          </div>
                        ))}
                        <div className="flex justify-between items-center pt-2">
                          <span className="text-xs font-black text-primary">TOTAL ESTIMADO</span>
                          <span className="text-sm font-black text-primary">{pyg(selectedHallazgo.total_contingencia)}</span>
                        </div>
                      </div>
                    </div>

                    <div className="card p-6 bg-white dark:bg-gray-900 shadow-sm border-gray-50 flex flex-col justify-center items-center gap-4 text-center relative overflow-hidden">
                      {/* SIFEN Badge Overlay */}
                      <div className="absolute -top-1 -right-1">
                        <div className="bg-green-500 text-white text-[8px] font-black px-2 py-1 rounded-bl-xl uppercase tracking-tighter">
                          SIFEN Ready
                        </div>
                      </div>
                      
                      <div className="w-12 h-12 bg-secondary/10 rounded-2xl flex items-center justify-center text-secondary">
                        <Database size={24} />
                      </div>
                      <div>
                        <h4 className="text-xs font-black text-gray-800 dark:text-white uppercase">Evidencia SIFEN/RG90</h4>
                        <p className="text-[10px] text-gray-500 mt-1 leading-tight">Acceso directo a los registros electrónicos vinculados a este hallazgo.</p>
                      </div>
                      <div className="flex gap-2 w-full">
                        <button className="btn-secondary flex-1 py-2 text-[10px]">
                          Ver RG90 <ExternalLink size={12} />
                        </button>
                        <button className="p-2 bg-gray-50 dark:bg-gray-800 rounded-xl text-primary hover:bg-primary/10 transition-colors">
                          <CheckCircle2 size={16} />
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Action Bar */}
              <div className="p-4 bg-gray-100/50 dark:bg-gray-800/50 border-t border-gray-100 dark:border-gray-800 flex justify-end gap-3">
                <button className="btn-ghost text-[10px]">Descargar Cédula</button>
                <button className="btn-primary py-2 px-6 text-[10px]">Guardar Resolución</button>
              </div>
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-400 gap-4">
              <Eye size={48} className="opacity-20" />
              <p className="text-sm font-bold uppercase tracking-widest opacity-50">Seleccione un hallazgo para explorar</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
